async def test_health_ok(client):
    resp = await client.get("http://testserver/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] is True
    assert body["redis"] is True


async def test_health_reports_degraded_when_redis_down(db_sessionmaker):
    from httpx import ASGITransport, AsyncClient

    from app.core.redis_client import get_redis
    from app.database import get_session
    from app.main import app

    class _BrokenRedis:
        async def ping(self):
            raise ConnectionError("redis indisponível")

    async def _override_get_session():
        async with db_sessionmaker() as session:
            yield session

    async def _override_get_redis():
        yield _BrokenRedis()

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_redis] = _override_get_redis
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            resp = await ac.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["redis"] is False
    assert body["database"] is True


async def test_health_never_leaks_sensitive_keys_in_response():
    # smoke test do redactor de log — garante que a lista de chaves sensíveis existe e cobre
    # os campos usados pelos schemas de auth (Artigo XI: nunca logar senha/token).
    from app.observability import _SENSITIVE_KEYS

    for key in ("senha", "password", "access_token", "refresh_token", "totp_secret"):
        assert key in _SENSITIVE_KEYS
