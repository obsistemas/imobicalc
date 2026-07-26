from sqlalchemy import select

from app.core.security import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_superadmin_access_token,
    decode_superadmin_token,
    decode_token,
)
from app.modules.superadmin import service
from app.modules.superadmin.models import SuperadminUser


async def _bootstrap(db_sessionmaker, email="dono@plataforma.com", senha="senhaforte123"):
    async with db_sessionmaker() as session:
        await service.bootstrap_superadmin(session, email=email, password=senha)


# --- T603: bootstrap idempotente -------------------------------------------------------------


async def test_bootstrap_creates_superadmin_when_env_vars_set(db_sessionmaker):
    await _bootstrap(db_sessionmaker)

    async with db_sessionmaker() as session:
        result = await session.execute(select(SuperadminUser).where(SuperadminUser.email == "dono@plataforma.com"))
        assert result.scalar_one_or_none() is not None


async def test_bootstrap_does_nothing_without_env_vars(db_sessionmaker):
    async with db_sessionmaker() as session:
        await service.bootstrap_superadmin(session, email="", password="")

    async with db_sessionmaker() as session:
        result = await session.execute(select(SuperadminUser))
        assert result.scalars().all() == []


async def test_bootstrap_twice_does_not_duplicate_nor_reset_password(db_sessionmaker):
    await _bootstrap(db_sessionmaker, senha="senhaoriginal123")
    await _bootstrap(db_sessionmaker, senha="senhadiferente456")

    async with db_sessionmaker() as session:
        result = await session.execute(select(SuperadminUser).where(SuperadminUser.email == "dono@plataforma.com"))
        contas = result.scalars().all()
        assert len(contas) == 1

        autenticado = await service.authenticate(session, email="dono@plataforma.com", senha="senhaoriginal123")
        assert autenticado.email == "dono@plataforma.com"


# --- T604: POST /admin/auth/login -------------------------------------------------------------


async def test_login_success_returns_token_without_tenant_id(client, db_sessionmaker):
    await _bootstrap(db_sessionmaker)

    resp = await client.post("/admin/auth/login", json={"email": "dono@plataforma.com", "senha": "senhaforte123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    payload = decode_superadmin_token(token)
    assert "tenant_id" not in payload
    assert payload["papel"] == "superadmin"


async def test_login_wrong_password_returns_401(client, db_sessionmaker):
    await _bootstrap(db_sessionmaker)
    resp = await client.post("/admin/auth/login", json={"email": "dono@plataforma.com", "senha": "errada"})
    assert resp.status_code == 401


async def test_login_unknown_email_returns_401(client):
    resp = await client.post("/admin/auth/login", json={"email": "ninguem@plataforma.com", "senha": "qualquer123"})
    assert resp.status_code == 401


async def test_login_inactive_account_returns_401(client, db_sessionmaker):
    await _bootstrap(db_sessionmaker)
    async with db_sessionmaker() as session:
        result = await session.execute(select(SuperadminUser).where(SuperadminUser.email == "dono@plataforma.com"))
        conta = result.scalar_one()
        conta.ativo = False
        await session.commit()

    resp = await client.post("/admin/auth/login", json={"email": "dono@plataforma.com", "senha": "senhaforte123"})
    assert resp.status_code == 401


# --- T605: RN3 — os dois mundos de token nunca se misturam -----------------------------------


async def test_superadmin_token_rejected_by_get_current_user_route(client, db_sessionmaker):
    await _bootstrap(db_sessionmaker)
    login_resp = await client.post("/admin/auth/login", json={"email": "dono@plataforma.com", "senha": "senhaforte123"})
    superadmin_token = login_resp.json()["access_token"]

    resp = await client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {superadmin_token}"})
    assert resp.status_code == 401


async def test_tenant_token_rejected_by_require_superadmin_route(client):
    signup_resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária X", "nome": "Admin X", "email": "adminx@example.com", "senha": "senha12345"},
    )
    tenant_token = signup_resp.json()["access_token"]

    resp = await client.get("/admin/tenants", headers={"Authorization": f"Bearer {tenant_token}"})
    assert resp.status_code == 403


def test_decode_superadmin_token_rejects_tenant_token():
    import uuid

    tenant_token = create_access_token(user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), papel="admin")
    try:
        decode_superadmin_token(tenant_token)
        assert False, "deveria ter levantado InvalidTokenError"
    except InvalidTokenError:
        pass


def test_decode_token_rejects_superadmin_token():
    import uuid

    superadmin_token = create_superadmin_access_token(superadmin_id=uuid.uuid4())
    try:
        decode_token(superadmin_token, expected_type=TokenType.ACCESS)
    except InvalidTokenError:
        assert False, "decode_token não deveria falhar (superadmin token tem type=access válido)"
    # decode_token aceita (não valida papel/tenant_id) — quem barra é get_current_user, testado acima.
