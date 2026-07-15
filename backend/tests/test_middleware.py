import uuid

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.core.tenant_context import current_tenant_id
from app.middleware.tenant import IdentifyTenantMiddleware


def _build_probe_app() -> FastAPI:
    """App mínima só com o middleware, para observar o contextvar setado durante a
    requisição sem depender de nenhuma rota de negócio já existir."""
    app = FastAPI()
    app.add_middleware(IdentifyTenantMiddleware)

    @app.get("/probe")
    async def probe():
        tenant_id = current_tenant_id.get()
        return {"tenant_id": str(tenant_id) if tenant_id else None}

    return app


async def test_middleware_sets_tenant_context_from_valid_jwt():
    tenant_id = uuid.uuid4()
    token = create_access_token(user_id=uuid.uuid4(), tenant_id=tenant_id, papel="admin")

    transport = ASGITransport(app=_build_probe_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        resp = await ac.get("/probe", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == str(tenant_id)


async def test_middleware_no_context_without_token_or_matching_subdomain():
    transport = ASGITransport(app=_build_probe_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        resp = await ac.get("/probe")

    assert resp.status_code == 200
    assert resp.json()["tenant_id"] is None


async def test_middleware_ignores_malformed_bearer_token():
    transport = ASGITransport(app=_build_probe_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        resp = await ac.get("/probe", headers={"Authorization": "Bearer isso-nao-e-um-jwt"})

    assert resp.status_code == 200
    assert resp.json()["tenant_id"] is None


async def test_middleware_does_not_leak_context_between_requests():
    tenant_id = uuid.uuid4()
    token = create_access_token(user_id=uuid.uuid4(), tenant_id=tenant_id, papel="admin")

    transport = ASGITransport(app=_build_probe_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        first = await ac.get("/probe", headers={"Authorization": f"Bearer {token}"})
        second = await ac.get("/probe")

    assert first.json()["tenant_id"] == str(tenant_id)
    assert second.json()["tenant_id"] is None
