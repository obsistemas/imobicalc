import json
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.tenant_context import system_scope
from app.main import app
from app.modules.imoveis.models import Imovel
from app.modules.imoveis.viacep_driver import FakeViaCepDriver, get_cep_driver
from app.modules.leads.models import Lead
from app.modules.tenancy.models import Tenant, User

CEP_PADRAO = "01310-100"

_IMOVEL_PAYLOAD = {
    "titulo": "Casa com quintal",
    "cep": CEP_PADRAO,
    "bairro": "Centro",
    "cidade": "São Paulo",
    "estado": "sp",
    "tipo": "casa",
    "area_total": 120,
}


def _override_cep_driver() -> None:
    driver = FakeViaCepDriver(sempre_falha=True)

    async def _get():
        return driver

    app.dependency_overrides[get_cep_driver] = _get


async def _signup_slug_and_imovel(client, db_sessionmaker, email):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Leads Público", "nome": "Admin", "email": email, "senha": "senha12345"},
    )
    token = resp.json()["access_token"]

    imovel_resp = await client.post("/imoveis", json=_IMOVEL_PAYLOAD, headers={"Authorization": f"Bearer {token}"})
    imovel_id = imovel_resp.json()["id"]

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            tenant_result = await session.execute(select(Tenant).where(Tenant.uuid == user.tenant_id))
            slug = tenant_result.scalar_one().slug

    return token, slug, imovel_id


def _host(slug: str) -> str:
    return f"{slug}.proptechavaliador.com.br"


async def test_lead_publico_criado_com_sucesso(client, db_sessionmaker):
    _override_cep_driver()
    _, slug, imovel_id = await _signup_slug_and_imovel(client, db_sessionmaker, "leadpub@example.com")

    resp = await client.post(
        "/leads/publico",
        json={"nome": "Interessado", "telefone": "11999990000", "imovel_id": imovel_id},
        headers={"Host": _host(slug)},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["corretor_id"] is None
    assert body["origem"] == "site"
    assert body["imovel_id"] == imovel_id


async def test_lead_publico_sem_telefone_nem_email_retorna_erro(client, db_sessionmaker):
    _override_cep_driver()
    _, slug, imovel_id = await _signup_slug_and_imovel(client, db_sessionmaker, "leadpubsemcontato@example.com")

    resp = await client.post(
        "/leads/publico",
        json={"nome": "Interessado", "imovel_id": imovel_id},
        headers={"Host": _host(slug)},
    )
    assert resp.status_code == 422


async def test_lead_publico_imovel_de_outro_tenant_retorna_404(client, db_sessionmaker):
    _override_cep_driver()
    _, _, imovel_a = await _signup_slug_and_imovel(client, db_sessionmaker, "leadpuba@example.com")
    _, slug_b, _ = await _signup_slug_and_imovel(client, db_sessionmaker, "leadpubb@example.com")

    resp = await client.post(
        "/leads/publico",
        json={"nome": "Interessado", "telefone": "11999990000", "imovel_id": imovel_a},
        headers={"Host": _host(slug_b)},
    )
    assert resp.status_code == 404


async def test_lead_publico_incrementa_contatos_do_imovel(client, db_sessionmaker):
    _override_cep_driver()
    _, slug, imovel_id = await _signup_slug_and_imovel(client, db_sessionmaker, "leadpubcontatos@example.com")

    await client.post(
        "/leads/publico",
        json={"nome": "Interessado", "email": "interessado@example.com", "imovel_id": imovel_id},
        headers={"Host": _host(slug)},
    )

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Imovel).where(Imovel.uuid == uuid.UUID(imovel_id)))
            assert result.scalar_one().contatos == 1


async def test_lead_publico_emite_notificacao_no_canal_do_tenant(client, db_sessionmaker, fake_redis):
    _override_cep_driver()
    token, slug, imovel_id = await _signup_slug_and_imovel(client, db_sessionmaker, "leadpubws@example.com")

    with TestClient(app).websocket_connect(f"/api/v1/ws/notificacoes?token={token}") as ws:
        resp = await client.post(
            "/leads/publico",
            json={"nome": "Interessado WS", "telefone": "11988887777", "imovel_id": imovel_id},
            headers={"Host": _host(slug)},
        )
        assert resp.status_code == 201
        data = json.loads(ws.receive_text())

    assert data["tipo"] == "lead_novo"
    assert data["lead"]["nome"] == "Interessado WS"


async def test_cadastro_manual_de_lead_tambem_incrementa_contatos(client, db_sessionmaker):
    """RN6/T724: fecha a lacuna original do RF006 — o incremento de contatos não é exclusivo
    dos caminhos automáticos."""
    _override_cep_driver()
    token, _, imovel_id = await _signup_slug_and_imovel(client, db_sessionmaker, "leadmanualcontatos@example.com")

    await client.post(
        "/leads",
        json={"nome": "Fulano", "origem": "indicacao", "imovel_id": imovel_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Imovel).where(Imovel.uuid == uuid.UUID(imovel_id)))
            assert result.scalar_one().contatos == 1


async def test_corretor_ve_lead_sem_dono_mas_nao_ve_lead_de_outro_corretor(db_sessionmaker, fake_redis):
    """RN7: lead sem dono (corretor_id=None) é visível a qualquer corretor do tenant, mas o
    isolamento entre corretores continua valendo para leads com dono."""
    from app.modules.leads import service
    from app.modules.leads.models import EstagioLead
    from app.modules.tenancy.models import Papel

    tenant_id = uuid.uuid4()
    corretor_a = User(tenant_id=tenant_id, nome="A", email="a@x.com", password_hash="x", papel=Papel.CORRETOR)
    corretor_b = User(tenant_id=tenant_id, nome="B", email="b@x.com", password_hash="x", papel=Papel.CORRETOR)
    corretor_a.uuid = uuid.uuid4()
    corretor_b.uuid = uuid.uuid4()

    async with db_sessionmaker() as session:
        with system_scope():
            session.add_all([corretor_a, corretor_b])
            await session.commit()

        lead_sem_dono = Lead(
            tenant_id=tenant_id, corretor_id=None, nome="Sem Dono", telefone="119", origem="site",
            estagio=EstagioLead.NOVO,
        )
        lead_do_b = Lead(
            tenant_id=tenant_id, corretor_id=corretor_b.uuid, nome="Do B", telefone="119", origem="indicacao",
            estagio=EstagioLead.NOVO,
        )
        with system_scope():
            session.add_all([lead_sem_dono, lead_do_b])
            await session.commit()

        leads_a = await service.listar_leads(session, tenant_id=tenant_id, user=corretor_a)
        nomes_a = {lead.nome for lead in leads_a}
        assert "Sem Dono" in nomes_a
        assert "Do B" not in nomes_a
