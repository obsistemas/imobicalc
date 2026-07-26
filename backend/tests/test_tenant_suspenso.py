from sqlalchemy import select

from app.modules.tenancy.models import Tenant, TenantStatus


async def _signup_and_get_token(client, email="suspenso@example.com"):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Suspensa", "nome": "Admin", "email": email, "senha": "senha12345"},
    )
    body = resp.json()
    return body["access_token"], body["user"]["id"]


async def _set_tenant_status(db_sessionmaker, admin_email: str, status: TenantStatus) -> None:
    from app.core.tenant_context import system_scope
    from app.modules.tenancy.models import User

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == admin_email))
            user = result.scalar_one()
            tenant_result = await session.execute(select(Tenant).where(Tenant.uuid == user.tenant_id))
            tenant = tenant_result.scalar_one()
            tenant.status = status
            await session.commit()


# --- T611 ---------------------------------------------------------------------------------


async def test_suspended_tenant_user_is_blocked_even_if_ativo(client, db_sessionmaker):
    token, _ = await _signup_and_get_token(client)
    await _set_tenant_status(db_sessionmaker, "suspenso@example.com", TenantStatus.SUSPENDED)

    resp = await client.get("/imoveis", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_active_tenant_user_is_not_blocked(client, db_sessionmaker):
    token, _ = await _signup_and_get_token(client, email="ativo@example.com")
    await _set_tenant_status(db_sessionmaker, "ativo@example.com", TenantStatus.ACTIVE)

    resp = await client.get("/imoveis", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


async def test_past_due_tenant_user_is_not_blocked(client, db_sessionmaker):
    """PAST_DUE é o estado normal durante o fluxo automático de dunning (RQ12) — não deve
    virar bloqueio de acesso; só SUSPENDED bloqueia."""
    token, _ = await _signup_and_get_token(client, email="pastdue@example.com")
    await _set_tenant_status(db_sessionmaker, "pastdue@example.com", TenantStatus.PAST_DUE)

    resp = await client.get("/imoveis", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


async def test_reactivating_tenant_restores_access_without_new_login(client, db_sessionmaker):
    token, _ = await _signup_and_get_token(client, email="reativado@example.com")
    await _set_tenant_status(db_sessionmaker, "reativado@example.com", TenantStatus.SUSPENDED)
    blocked = await client.get("/imoveis", headers={"Authorization": f"Bearer {token}"})
    assert blocked.status_code == 403

    await _set_tenant_status(db_sessionmaker, "reativado@example.com", TenantStatus.ACTIVE)
    restored = await client.get("/imoveis", headers={"Authorization": f"Bearer {token}"})
    assert restored.status_code == 200
