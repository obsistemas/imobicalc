import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.tenant_context import system_scope
from app.main import app
from app.modules.precos_mercado.service import ensure_custo_construcao_seeded, ensure_precos_mercado_seeded
from app.modules.tenancy.models import Tenant, User

_IMOVEL_PADRAO = {
    "titulo": "Apartamento subprecificado",
    "cep": "01310-100",
    "bairro": "Bairro Sem Dado Especifico",
    "cidade": "Cidade Sem Dado Especifico",
    "estado": "SP",
    "tipo": "apartamento",
    "area_total": 100,
}


async def _seed_precos(db_sessionmaker):
    async with db_sessionmaker() as session:
        await ensure_precos_mercado_seeded(session)
        await ensure_custo_construcao_seeded(session)


async def _signup(client, email):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": f"Imobiliária {email}", "nome": "Admin", "email": email, "senha": "senha12345"},
    )
    return resp.json()["access_token"]


async def _tenant_id_por_email(db_sessionmaker, email: str):
    async with db_sessionmaker() as session:
        with system_scope():
            user = (await session.execute(select(User).where(User.email == email))).scalar_one()
            tenant = (await session.execute(select(Tenant).where(Tenant.uuid == user.tenant_id))).scalar_one()
            return tenant.uuid


# --- T522/T523: alerta de subprecificação em tempo real -------------------------------------


async def test_criar_imovel_abaixo_do_mercado_publica_alerta(client, db_sessionmaker):
    token = await _signup(client, "alerta-abaixo@example.com")
    await _seed_precos(db_sessionmaker)

    with TestClient(app).websocket_connect(f"/api/v1/ws/notificacoes?token={token}") as ws:
        # fallback genérico de apartamento = 6000/m² * 100m² = 600.000 esperado; 400.000 é 33% abaixo (> 15%)
        resp = await client.post(
            "/imoveis",
            json={**_IMOVEL_PADRAO, "valor_anunciado": 400000},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = json.loads(ws.receive_text())

    assert data["tipo"] == "imovel_subprecificado"
    assert data["imovel"]["valor_anunciado"] == "400000"


async def test_criar_imovel_dentro_do_esperado_nao_publica_alerta(client, db_sessionmaker, fake_redis):
    token = await _signup(client, "alerta-dentro@example.com")
    await _seed_precos(db_sessionmaker)
    tenant_id = await _tenant_id_por_email(db_sessionmaker, "alerta-dentro@example.com")

    pubsub = fake_redis.pubsub()
    await pubsub.subscribe(f"tenant.{tenant_id}.notificacoes")

    resp = await client.post(
        "/imoveis",
        json={**_IMOVEL_PADRAO, "valor_anunciado": 590000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201

    mensagem = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
    assert mensagem is None


async def test_criar_imovel_sem_valor_anunciado_nao_publica_alerta(client, db_sessionmaker, fake_redis):
    token = await _signup(client, "alerta-sem-valor@example.com")
    await _seed_precos(db_sessionmaker)
    tenant_id = await _tenant_id_por_email(db_sessionmaker, "alerta-sem-valor@example.com")

    pubsub = fake_redis.pubsub()
    await pubsub.subscribe(f"tenant.{tenant_id}.notificacoes")

    resp = await client.post("/imoveis", json=_IMOVEL_PADRAO, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    assert resp.json()["valor_anunciado"] is None

    mensagem = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
    assert mensagem is None


async def test_criar_imovel_sem_preco_de_mercado_nao_publica_alerta_nem_quebra(client):
    # sem chamar _seed_precos — base de preços vazia, nem fallback existe
    token = await _signup(client, "alerta-sem-preco@example.com")

    resp = await client.post(
        "/imoveis",
        json={**_IMOVEL_PADRAO, "valor_anunciado": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


async def test_atualizar_imovel_abaixo_do_mercado_publica_alerta(client, db_sessionmaker):
    token = await _signup(client, "alerta-update@example.com")
    await _seed_precos(db_sessionmaker)

    criado = await client.post("/imoveis", json=_IMOVEL_PADRAO, headers={"Authorization": f"Bearer {token}"})
    imovel_id = criado.json()["id"]

    with TestClient(app).websocket_connect(f"/api/v1/ws/notificacoes?token={token}") as ws:
        resp = await client.put(
            f"/imoveis/{imovel_id}",
            json={**_IMOVEL_PADRAO, "valor_anunciado": 300000},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = json.loads(ws.receive_text())

    assert data["tipo"] == "imovel_subprecificado"
