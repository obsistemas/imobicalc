import json
from urllib.parse import parse_qs, urlparse

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.tenant_context import system_scope
from app.main import app
from app.modules.imoveis.viacep_driver import FakeViaCepDriver, get_cep_driver
from app.modules.tenancy.models import Convite

CEP_PADRAO = "01310-100"

_IMOVEL_PAYLOAD = {
    "titulo": "Sala comercial",
    "cep": CEP_PADRAO,
    "bairro": "Centro",
    "cidade": "São Paulo",
    "estado": "sp",
    "tipo": "comercial",
    "area_total": 60,
}


def _override_cep_driver() -> None:
    driver = FakeViaCepDriver(sempre_falha=True)

    async def _get():
        return driver

    app.dependency_overrides[get_cep_driver] = _get


async def _signup(client, email):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Integração", "nome": "Admin", "email": email, "senha": "senha12345"},
    )
    return resp.json()["access_token"]


def _secret_from_url(url: str) -> str:
    return parse_qs(urlparse(url).query)["secret"][0]


async def _corretor_token(client, db_sessionmaker, admin_token, email):
    setup = await client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {admin_token}"})
    secret = _secret_from_url(setup.json()["secret_otpauth_url"])
    codigo = pyotp.TOTP(secret).now()
    await client.post("/auth/2fa/verify", json={"codigo": codigo}, headers={"Authorization": f"Bearer {admin_token}"})

    planos_resp = await client.get("/plans")
    plano_pro = next(p for p in planos_resp.json() if p["nome"] == "pro")
    await client.post(
        "/license/upgrade", json={"plan_id": plano_pro["id"]}, headers={"Authorization": f"Bearer {admin_token}"}
    )

    await client.post("/users/convites", json={"email": email}, headers={"Authorization": f"Bearer {admin_token}"})
    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Convite).where(Convite.email == email))
            token_convite = result.scalar_one().token
    resp = await client.post(f"/convites/{token_convite}/aceitar", json={"nome": "Corretor", "senha": "senha12345"})
    return resp.json()["access_token"]


async def _criar_imovel(client, token):
    resp = await client.post("/imoveis", json=_IMOVEL_PAYLOAD, headers={"Authorization": f"Bearer {token}"})
    return resp.json()["id"]


# --- Bloco D: gestão de API key ------------------------------------------------------------


async def test_gerar_api_key_retorna_texto_plano(client):
    token = await _signup(client, "apikey1@example.com")
    resp = await client.post("/leads/integracao/api-key", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["api_key"]) > 20


async def test_status_api_key_antes_e_depois_de_gerar(client):
    token = await _signup(client, "apikey2@example.com")

    antes = await client.get("/leads/integracao/api-key", headers={"Authorization": f"Bearer {token}"})
    assert antes.json() == {"existe": False, "created_at": None, "last_used_at": None}

    await client.post("/leads/integracao/api-key", headers={"Authorization": f"Bearer {token}"})
    depois = await client.get("/leads/integracao/api-key", headers={"Authorization": f"Bearer {token}"})
    assert depois.json()["existe"] is True
    assert "api_key" not in depois.json()


async def test_gerar_novamente_invalida_chave_anterior(client):
    token = await _signup(client, "apikey3@example.com")
    primeira = await client.post("/leads/integracao/api-key", headers={"Authorization": f"Bearer {token}"})
    chave_antiga = primeira.json()["api_key"]

    await client.post("/leads/integracao/api-key", headers={"Authorization": f"Bearer {token}"})

    resp = await client.post(
        "/webhooks/leads", json={"nome": "X", "telefone": "119"}, headers={"X-API-Key": chave_antiga}
    )
    assert resp.status_code == 401


async def test_corretor_nao_pode_gerenciar_api_key(client, db_sessionmaker):
    admin_token = await _signup(client, "apikeyadmin@example.com")
    corretor_token = await _corretor_token(client, db_sessionmaker, admin_token, "apikeycorretor@example.com")

    gerar = await client.post("/leads/integracao/api-key", headers={"Authorization": f"Bearer {corretor_token}"})
    status_resp = await client.get("/leads/integracao/api-key", headers={"Authorization": f"Bearer {corretor_token}"})
    assert gerar.status_code == 403
    assert status_resp.status_code == 403


# --- Bloco E: webhook -----------------------------------------------------------------------


async def test_webhook_com_chave_valida_cria_lead(client):
    token = await _signup(client, "webhook1@example.com")
    gerar = await client.post("/leads/integracao/api-key", headers={"Authorization": f"Bearer {token}"})
    chave = gerar.json()["api_key"]

    resp = await client.post(
        "/webhooks/leads", json={"nome": "Lead Externo", "email": "lead@externo.com"}, headers={"X-API-Key": chave}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["corretor_id"] is None
    assert body["origem"] == "outro"


async def test_webhook_sem_chave_retorna_401(client):
    resp = await client.post("/webhooks/leads", json={"nome": "X", "telefone": "119"})
    assert resp.status_code == 401


async def test_webhook_com_chave_invalida_retorna_401(client):
    resp = await client.post(
        "/webhooks/leads", json={"nome": "X", "telefone": "119"}, headers={"X-API-Key": "chave-que-nao-existe"}
    )
    assert resp.status_code == 401


async def test_webhook_respeita_origem_informada(client):
    token = await _signup(client, "webhook2@example.com")
    gerar = await client.post("/leads/integracao/api-key", headers={"Authorization": f"Bearer {token}"})
    chave = gerar.json()["api_key"]

    resp = await client.post(
        "/webhooks/leads",
        json={"nome": "Lead Campanha", "telefone": "11900001111", "origem": "redes_sociais"},
        headers={"X-API-Key": chave},
    )
    assert resp.json()["origem"] == "redes_sociais"


async def test_webhook_imovel_de_outro_tenant_retorna_400(client):
    _override_cep_driver()
    token_a = await _signup(client, "webhooktenanta@example.com")
    token_b = await _signup(client, "webhooktenantb@example.com")
    imovel_b = await _criar_imovel(client, token_b)

    gerar = await client.post("/leads/integracao/api-key", headers={"Authorization": f"Bearer {token_a}"})
    chave_a = gerar.json()["api_key"]

    resp = await client.post(
        "/webhooks/leads",
        json={"nome": "X", "telefone": "119", "imovel_id": imovel_b},
        headers={"X-API-Key": chave_a},
    )
    assert resp.status_code == 400


async def test_webhook_atualiza_last_used_at(client):
    token = await _signup(client, "webhooklastused@example.com")
    gerar = await client.post("/leads/integracao/api-key", headers={"Authorization": f"Bearer {token}"})
    chave = gerar.json()["api_key"]
    status_antes = await client.get("/leads/integracao/api-key", headers={"Authorization": f"Bearer {token}"})
    assert status_antes.json()["last_used_at"] is None

    await client.post("/webhooks/leads", json={"nome": "X", "telefone": "119"}, headers={"X-API-Key": chave})

    status_depois = await client.get("/leads/integracao/api-key", headers={"Authorization": f"Bearer {token}"})
    assert status_depois.json()["last_used_at"] is not None


async def test_webhook_emite_notificacao_no_canal_do_tenant(client, fake_redis):
    token = await _signup(client, "webhookws@example.com")
    gerar = await client.post("/leads/integracao/api-key", headers={"Authorization": f"Bearer {token}"})
    chave = gerar.json()["api_key"]

    with TestClient(app).websocket_connect(f"/api/v1/ws/notificacoes?token={token}") as ws:
        resp = await client.post(
            "/webhooks/leads", json={"nome": "Lead WS", "telefone": "11900002222"}, headers={"X-API-Key": chave}
        )
        assert resp.status_code == 201
        data = json.loads(ws.receive_text())

    assert data["tipo"] == "lead_novo"
    assert data["lead"]["nome"] == "Lead WS"
