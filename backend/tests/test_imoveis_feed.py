import uuid
from decimal import Decimal

from sqlalchemy import select

from app.core.tenant_context import system_scope
from app.main import app
from app.modules.imoveis.models import Finalidade, Imovel, ImovelStatus, ImovelTipo
from app.modules.imoveis.viacep_driver import FakeViaCepDriver, get_cep_driver
from app.modules.imoveis.vrsync_feed import gerar_feed_vrsync
from app.modules.tenancy.models import Tenant, User

CEP_PADRAO = "01310-100"

_IMOVEL_PAYLOAD = {
    "titulo": "Apartamento no centro",
    "descricao": "Bem localizado",
    "cep": CEP_PADRAO,
    "bairro": "Centro",
    "cidade": "São Paulo",
    "estado": "sp",
    "tipo": "apartamento",
    "area_total": 80,
    "valor_anunciado": 500000,
    "quartos": 2,
    "finalidade": "venda",
}


def _override_cep_driver() -> None:
    driver = FakeViaCepDriver(sempre_falha=True)

    async def _get():
        return driver

    app.dependency_overrides[get_cep_driver] = _get


async def _signup_and_slug(client, db_sessionmaker, email):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Feed", "nome": "Admin", "email": email, "senha": "senha12345"},
    )
    token = resp.json()["access_token"]
    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            tenant_result = await session.execute(select(Tenant).where(Tenant.uuid == user.tenant_id))
            slug = tenant_result.scalar_one().slug
    return token, slug


def _host(slug: str) -> str:
    return f"{slug}.proptechavaliador.com.br"


async def _criar_imovel(client, token, **overrides):
    payload = {**_IMOVEL_PAYLOAD, **overrides}
    resp = await client.post("/imoveis", json=payload, headers={"Authorization": f"Bearer {token}"})
    return resp.json()


def _imovel_fake(**overrides) -> Imovel:
    base = dict(
        tenant_id=uuid.uuid4(),
        corretor_id=uuid.uuid4(),
        uuid=uuid.uuid4(),
        titulo="Casa ampla",
        descricao="Descrição de teste",
        cep="01310-100",
        bairro="Centro",
        cidade="São Paulo",
        estado="SP",
        tipo=ImovelTipo.CASA,
        area_total=Decimal("120.00"),
        quartos=3,
        banheiros=2,
        suites=1,
        vagas=2,
        valor_anunciado=Decimal("600000.0000"),
        status=ImovelStatus.DISPONIVEL,
        finalidade=Finalidade.VENDA,
        fotos="[]",
        ativo=True,
        views=0,
        contatos=0,
    )
    base.update(overrides)
    return Imovel(**base)


# --- T811: gerar_feed_vrsync (função pura) ----------------------------------------------------


def test_feed_xml_bem_formado_com_namespace_correto():
    xml = gerar_feed_vrsync([_imovel_fake()], provider="Proptech", email="a@b.com", contact_name="Tenant X")
    assert "http://www.vivareal.com/schemas/1.0/VRSync" in xml
    assert "<ListingDataFeed" in xml
    assert "<Header>" in xml
    assert "<Listings>" in xml


def test_feed_xml_listing_id_e_o_uuid_do_imovel():
    imovel = _imovel_fake()
    xml = gerar_feed_vrsync([imovel], provider="P", email="a@b.com", contact_name="C")
    assert f"<ListingID>{imovel.uuid}</ListingID>" in xml


def test_feed_xml_transaction_type_conforme_finalidade():
    venda = gerar_feed_vrsync([_imovel_fake(finalidade=Finalidade.VENDA)], provider="P", email="a@b.com", contact_name="C")
    aluguel = gerar_feed_vrsync(
        [_imovel_fake(finalidade=Finalidade.ALUGUEL)], provider="P", email="a@b.com", contact_name="C"
    )
    assert "<TransactionType>For Sale</TransactionType>" in venda
    assert "<TransactionType>For Rent</TransactionType>" in aluguel
    assert "<RentalPrice" in aluguel
    assert "<ListPrice" in venda


def test_feed_xml_mapeamento_tipo_para_usage_e_property_type():
    xml = gerar_feed_vrsync(
        [_imovel_fake(tipo=ImovelTipo.GALPAO)], provider="P", email="a@b.com", contact_name="C"
    )
    assert "<UsageType>Commercial</UsageType>" in xml
    assert "<PropertyType>Commercial / Industrial</PropertyType>" in xml


def test_feed_xml_sem_imoveis_ainda_e_valido():
    xml = gerar_feed_vrsync([], provider="P", email="a@b.com", contact_name="C")
    assert "<Listings" in xml
    assert "<Listing>" not in xml


# --- T813: endpoint GET /imoveis/publico/feed.xml ---------------------------------------------


async def test_endpoint_feed_inclui_imovel_disponivel_com_finalidade(client, db_sessionmaker):
    _override_cep_driver()
    token, slug = await _signup_and_slug(client, db_sessionmaker, "feed1@example.com")
    imovel = await _criar_imovel(client, token)

    resp = await client.get("/imoveis/publico/feed.xml", headers={"Host": _host(slug)})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    assert imovel["id"] in resp.text


async def test_endpoint_feed_exclui_imovel_sem_finalidade(client, db_sessionmaker):
    _override_cep_driver()
    token, slug = await _signup_and_slug(client, db_sessionmaker, "feed2@example.com")
    payload = {k: v for k, v in _IMOVEL_PAYLOAD.items() if k != "finalidade"}
    resp_criar = await client.post("/imoveis", json=payload, headers={"Authorization": f"Bearer {token}"})
    imovel_id = resp_criar.json()["id"]

    resp = await client.get("/imoveis/publico/feed.xml", headers={"Host": _host(slug)})
    assert imovel_id not in resp.text


async def test_endpoint_feed_exclui_imovel_vendido(client, db_sessionmaker):
    _override_cep_driver()
    token, slug = await _signup_and_slug(client, db_sessionmaker, "feed3@example.com")
    imovel = await _criar_imovel(client, token)
    await client.put(
        f"/imoveis/{imovel['id']}",
        json={**_IMOVEL_PAYLOAD, "status": "vendido"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get("/imoveis/publico/feed.xml", headers={"Host": _host(slug)})
    assert imovel["id"] not in resp.text


async def test_endpoint_feed_nao_mistura_tenants(client, db_sessionmaker):
    _override_cep_driver()
    token_a, slug_a = await _signup_and_slug(client, db_sessionmaker, "feeda@example.com")
    token_b, slug_b = await _signup_and_slug(client, db_sessionmaker, "feedb@example.com")
    imovel_a = await _criar_imovel(client, token_a)
    imovel_b = await _criar_imovel(client, token_b)

    resp_a = await client.get("/imoveis/publico/feed.xml", headers={"Host": _host(slug_a)})
    assert imovel_a["id"] in resp_a.text
    assert imovel_b["id"] not in resp_a.text


async def test_endpoint_feed_host_nao_resolvido_retorna_feed_vazio_valido(client):
    resp = await client.get("/imoveis/publico/feed.xml")
    assert resp.status_code == 200
    assert "<Listings" in resp.text
    assert "<Listing>" not in resp.text
