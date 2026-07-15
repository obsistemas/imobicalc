from datetime import timedelta


async def test_signup_creates_tenant_and_admin(client):
    resp = await client.post(
        "/auth/signup",
        json={
            "nome_tenant": "Imobiliária Teste",
            "nome": "Ana Corretora",
            "email": "ana@example.com",
            "senha": "senha12345",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["email"] == "ana@example.com"
    assert body["user"]["papel"] == "admin"
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert "refresh_token" in resp.cookies


async def test_signup_duplicate_email_returns_409(client):
    payload = {
        "nome_tenant": "Imobiliária A",
        "nome": "Ana",
        "email": "dup@example.com",
        "senha": "senha12345",
    }
    first = await client.post("/auth/signup", json=payload)
    assert first.status_code == 201

    payload2 = {**payload, "nome_tenant": "Imobiliária B"}
    second = await client.post("/auth/signup", json=payload2)
    assert second.status_code == 409


async def test_signup_trial_termina_em_7_dias(client, db_sessionmaker):
    from sqlalchemy import select

    from app.core.tenant_context import system_scope
    from app.modules.tenancy.models import Tenant, TenantStatus

    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Trial", "nome": "Bia", "email": "bia@example.com", "senha": "senha12345"},
    )
    assert resp.status_code == 201

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Tenant).where(Tenant.slug.like("imobiliaria-trial%")))
            tenant = result.scalar_one()

    assert tenant.status == TenantStatus.TRIAL
    delta = tenant.trial_termina_em() - tenant.created_at
    assert delta == timedelta(days=7)


async def test_signup_slug_collision_generates_unique_suffix(client):
    payload = {"nome_tenant": "Imobiliária Dup", "nome": "Xavier", "email": "dup1@example.com", "senha": "senha12345"}
    first = await client.post("/auth/signup", json=payload)
    assert first.status_code == 201

    payload2 = {**payload, "email": "dup2@example.com"}
    second = await client.post("/auth/signup", json=payload2)
    assert second.status_code == 201
    # dois tenants distintos com o mesmo nome não podem colidir no slug (base de subdomínio).
    assert first.json()["user"]["id"] != second.json()["user"]["id"]
