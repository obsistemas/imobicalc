import json
import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.main import app

# --- T320/T322: WebSocket de notificações em tempo real ------------------------------------


async def test_ws_recebe_notificacao_publicada_no_canal_do_proprio_tenant(client, fake_redis):
    tenant_id = uuid.uuid4()
    token = create_access_token(user_id=uuid.uuid4(), tenant_id=tenant_id, papel="admin")

    with TestClient(app).websocket_connect(f"/api/v1/ws/notificacoes?token={token}") as ws:
        await fake_redis.publish(f"tenant.{tenant_id}.notificacoes", json.dumps({"tipo": "lead_novo"}))
        data = ws.receive_text()

    assert json.loads(data) == {"tipo": "lead_novo"}


async def test_ws_token_invalido_fecha_conexao(client):
    with pytest.raises(WebSocketDisconnect):
        with TestClient(app).websocket_connect("/api/v1/ws/notificacoes?token=invalido"):
            pass


async def test_ws_isolamento_entre_tenants(client, fake_redis):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    token_b = create_access_token(user_id=uuid.uuid4(), tenant_id=tenant_b, papel="admin")

    with TestClient(app).websocket_connect(f"/api/v1/ws/notificacoes?token={token_b}") as ws_b:
        await fake_redis.publish(f"tenant.{tenant_a}.notificacoes", json.dumps({"tipo": "lead_novo", "tenant": "a"}))
        await fake_redis.publish(f"tenant.{tenant_b}.notificacoes", json.dumps({"tipo": "lead_novo", "tenant": "b"}))
        data = ws_b.receive_text()

    assert json.loads(data)["tenant"] == "b"


async def test_leads_criar_lead_publica_notificacao_no_canal_do_tenant(client, fake_redis):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária WS", "nome": "Admin", "email": "ws-lead@example.com", "senha": "senha12345"},
    )
    token = resp.json()["access_token"]

    with TestClient(app).websocket_connect(f"/api/v1/ws/notificacoes?token={token}") as ws:
        criar_resp = await client.post(
            "/leads", json={"nome": "Fulano", "origem": "site"}, headers={"Authorization": f"Bearer {token}"}
        )
        assert criar_resp.status_code == 201
        data = json.loads(ws.receive_text())

    assert data["tipo"] == "lead_novo"
    assert data["lead"]["nome"] == "Fulano"
