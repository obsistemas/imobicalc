import base64

import pytest
from sqlalchemy import select

from app.config import settings
from app.core.tenant_context import system_scope
from app.modules.imoveis.models import Imovel
from app.modules.imoveis.viacep_driver import FakeViaCepDriver, get_cep_driver
from app.main import app

CEP_PADRAO = "01310-100"
_SECRET = "segredo-de-teste-canal-pro"

_IMOVEL_PAYLOAD = {
    "titulo": "Apartamento portal",
    "cep": CEP_PADRAO,
    "bairro": "Centro",
    "cidade": "São Paulo",
    "estado": "sp",
    "tipo": "apartamento",
    "area_total": 70,
    "finalidade": "venda",
}


def _override_cep_driver() -> None:
    driver = FakeViaCepDriver(sempre_falha=True)

    async def _get():
        return driver

    app.dependency_overrides[get_cep_driver] = _get


@pytest.fixture(autouse=True)
def _com_secret_configurada():
    original = settings.canal_pro_webhook_secret
    settings.canal_pro_webhook_secret = _SECRET
    yield
    settings.canal_pro_webhook_secret = original


def _basic_header(secret: str) -> dict:
    token = base64.b64encode(f"canalpro:{secret}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


async def _signup_and_imovel(client, token_email):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Portal", "nome": "Admin", "email": token_email, "senha": "senha12345"},
    )
    token = resp.json()["access_token"]
    imovel_resp = await client.post("/imoveis", json=_IMOVEL_PAYLOAD, headers={"Authorization": f"Bearer {token}"})
    return token, imovel_resp.json()["id"]


async def test_webhook_portal_com_secret_valida_cria_lead(client, db_sessionmaker):
    _override_cep_driver()
    _, imovel_id = await _signup_and_imovel(client, "portal1@example.com")

    resp = await client.post(
        "/webhooks/leads/portais",
        json={"clientListingId": imovel_id, "name": "Interessado Portal", "email": "x@y.com"},
        headers=_basic_header(_SECRET),
    )
    assert resp.status_code == 200

    async with db_sessionmaker() as session:
        with system_scope():
            from app.modules.leads.models import Lead

            result = await session.execute(select(Lead).where(Lead.nome == "Interessado Portal"))
            lead = result.scalar_one()
            assert lead.corretor_id is None
            assert lead.origem.value == "portal"


async def test_webhook_portal_sem_auth_retorna_401(client):
    resp = await client.post("/webhooks/leads/portais", json={"name": "X"})
    assert resp.status_code == 401


async def test_webhook_portal_secret_errada_retorna_401(client):
    resp = await client.post(
        "/webhooks/leads/portais", json={"name": "X"}, headers=_basic_header("secret-errada")
    )
    assert resp.status_code == 401


async def test_webhook_portal_secret_vazia_nas_settings_sempre_rejeita(client):
    settings.canal_pro_webhook_secret = ""
    resp = await client.post(
        "/webhooks/leads/portais", json={"name": "X"}, headers=_basic_header("qualquer-coisa")
    )
    assert resp.status_code == 401


async def test_webhook_portal_client_listing_id_desconhecido_retorna_200_sem_criar_lead(client, db_sessionmaker):
    import uuid

    resp = await client.post(
        "/webhooks/leads/portais",
        json={"clientListingId": str(uuid.uuid4()), "name": "Fantasma"},
        headers=_basic_header(_SECRET),
    )
    assert resp.status_code == 200

    async with db_sessionmaker() as session:
        with system_scope():
            from app.modules.leads.models import Lead

            result = await session.execute(select(Lead).where(Lead.nome == "Fantasma"))
            assert result.scalar_one_or_none() is None


async def test_webhook_portal_sem_client_listing_id_retorna_200_sem_criar_lead(client, db_sessionmaker):
    resp = await client.post(
        "/webhooks/leads/portais", json={"name": "MCMV sem imovel"}, headers=_basic_header(_SECRET)
    )
    assert resp.status_code == 200

    async with db_sessionmaker() as session:
        with system_scope():
            from app.modules.leads.models import Lead

            result = await session.execute(select(Lead).where(Lead.nome == "MCMV sem imovel"))
            assert result.scalar_one_or_none() is None


async def test_webhook_portal_incrementa_contatos_do_imovel(client, db_sessionmaker):
    _override_cep_driver()
    _, imovel_id = await _signup_and_imovel(client, "portalcontatos@example.com")

    await client.post(
        "/webhooks/leads/portais",
        json={"clientListingId": imovel_id, "name": "Fulano"},
        headers=_basic_header(_SECRET),
    )

    async with db_sessionmaker() as session:
        with system_scope():
            import uuid as uuid_pkg

            result = await session.execute(select(Imovel).where(Imovel.uuid == uuid_pkg.UUID(imovel_id)))
            assert result.scalar_one().contatos == 1
