from sqlalchemy import select

from app.core.tenant_context import system_scope
from app.modules.licenciamento.models import License, LicenseStatus
from app.modules.superadmin import service
from app.modules.tenancy.models import Tenant, TenantStatus, User


async def _bootstrap_and_login(client, db_sessionmaker, email="dono@plataforma.com", senha="senhaforte123"):
    async with db_sessionmaker() as session:
        await service.bootstrap_superadmin(session, email=email, password=senha)
    resp = await client.post("/admin/auth/login", json={"email": email, "senha": senha})
    return resp.json()["access_token"]


async def _signup(client, email, nome_tenant):
    resp = await client.post(
        "/auth/signup", json={"nome_tenant": nome_tenant, "nome": "Admin", "email": email, "senha": "senha12345"}
    )
    return resp.json()


# --- T631: uso da plataforma ---------------------------------------------------------------


async def test_uso_plataforma_conta_tenants_por_status(client, db_sessionmaker):
    await _signup(client, "trial1@example.com", "Tenant Trial 1")
    await _signup(client, "trial2@example.com", "Tenant Trial 2")
    email_ativo = "ativo@example.com"
    await _signup(client, email_ativo, "Tenant Ativo")

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == email_ativo))
            tenant_id = result.scalar_one().tenant_id
            tenant_result = await session.execute(select(Tenant).where(Tenant.uuid == tenant_id))
            tenant = tenant_result.scalar_one()
            tenant.status = TenantStatus.ACTIVE
            await session.commit()

    superadmin_token = await _bootstrap_and_login(client, db_sessionmaker)
    resp = await client.get("/admin/uso/plataforma", headers={"Authorization": f"Bearer {superadmin_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenants_por_status"]["trial"] == 2
    assert body["tenants_por_status"]["active"] == 1
    assert body["total_usuarios"] == 3


# --- T632: faturamento consolidado (RN4) -----------------------------------------------------


async def test_mrr_soma_so_licenses_ativas_com_preco_congelado(client, db_sessionmaker):
    email_ativo = "mrrativo@example.com"
    email_trial = "mrrtrial@example.com"
    await _signup(client, email_ativo, "Tenant MRR Ativo")
    await _signup(client, email_trial, "Tenant MRR Trial")

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == email_ativo))
            tenant_id = result.scalar_one().tenant_id
            license_result = await session.execute(select(License).where(License.tenant_id == tenant_id))
            license_ = license_result.scalar_one()
            license_.status = LicenseStatus.ACTIVE
            await session.commit()
            preco_esperado = license_.preco_congelado

    superadmin_token = await _bootstrap_and_login(client, db_sessionmaker)
    resp = await client.get("/admin/faturamento/consolidado", headers={"Authorization": f"Bearer {superadmin_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert float(body["mrr"]) == float(preco_esperado)


async def test_dashboard_endpoints_require_superadmin(client):
    signup_body = await _signup(client, "naosuper2@example.com", "Tenant Não Super")
    tenant_token = signup_body["access_token"]

    resp1 = await client.get("/admin/uso/plataforma", headers={"Authorization": f"Bearer {tenant_token}"})
    resp2 = await client.get("/admin/faturamento/consolidado", headers={"Authorization": f"Bearer {tenant_token}"})
    assert resp1.status_code == 403
    assert resp2.status_code == 403
