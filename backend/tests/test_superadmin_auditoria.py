from sqlalchemy import select

from app.core.tenant_context import system_scope
from app.modules.superadmin import service
from app.modules.tenancy.models import User


async def _bootstrap_and_login(client, db_sessionmaker, email="dono@plataforma.com", senha="senhaforte123"):
    async with db_sessionmaker() as session:
        await service.bootstrap_superadmin(session, email=email, password=senha)
    resp = await client.post("/admin/auth/login", json={"email": email, "senha": senha})
    return resp.json()["access_token"]


async def _signup_and_tenant_id(client, db_sessionmaker, email, nome_tenant):
    await client.post(
        "/auth/signup", json={"nome_tenant": nome_tenant, "nome": "Admin", "email": email, "senha": "senha12345"}
    )
    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == email))
            return str(result.scalar_one().tenant_id)


# --- T641: auditoria cross-tenant ------------------------------------------------------------


async def test_auditoria_logs_mostra_entradas_de_tenants_diferentes(client, db_sessionmaker):
    tenant_a = await _signup_and_tenant_id(client, db_sessionmaker, "auditoria-a@example.com", "Tenant Auditoria A")
    tenant_b = await _signup_and_tenant_id(client, db_sessionmaker, "auditoria-b@example.com", "Tenant Auditoria B")

    superadmin_token = await _bootstrap_and_login(client, db_sessionmaker)
    await client.post(f"/admin/tenants/{tenant_a}/suspender", headers={"Authorization": f"Bearer {superadmin_token}"})
    await client.post(f"/admin/tenants/{tenant_b}/suspender", headers={"Authorization": f"Bearer {superadmin_token}"})

    resp = await client.get("/admin/auditoria/logs", headers={"Authorization": f"Bearer {superadmin_token}"})
    assert resp.status_code == 200
    tenant_ids_nos_logs = {log["tenant_id"] for log in resp.json()}
    assert tenant_a in tenant_ids_nos_logs
    assert tenant_b in tenant_ids_nos_logs


async def test_auditoria_logs_filtra_por_tenant_id(client, db_sessionmaker):
    tenant_a = await _signup_and_tenant_id(client, db_sessionmaker, "filtro-a@example.com", "Tenant Filtro A")
    tenant_b = await _signup_and_tenant_id(client, db_sessionmaker, "filtro-b@example.com", "Tenant Filtro B")

    superadmin_token = await _bootstrap_and_login(client, db_sessionmaker)
    await client.post(f"/admin/tenants/{tenant_a}/suspender", headers={"Authorization": f"Bearer {superadmin_token}"})
    await client.post(f"/admin/tenants/{tenant_b}/suspender", headers={"Authorization": f"Bearer {superadmin_token}"})

    resp = await client.get(
        "/admin/auditoria/logs",
        params={"tenant_id": tenant_a},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    assert all(log["tenant_id"] == tenant_a for log in logs)


async def test_auditoria_logs_filtra_por_acao_e_intervalo_de_data(client, db_sessionmaker):
    from datetime import date, timedelta

    tenant_a = await _signup_and_tenant_id(client, db_sessionmaker, "filtro-data-a@example.com", "Tenant Data A")
    superadmin_token = await _bootstrap_and_login(client, db_sessionmaker)
    await client.post(f"/admin/tenants/{tenant_a}/suspender", headers={"Authorization": f"Bearer {superadmin_token}"})

    hoje = date.today()
    resp = await client.get(
        "/admin/auditoria/logs",
        params={
            "acao": "tenant_suspenso_por_superadmin",
            "desde": (hoje - timedelta(days=1)).isoformat(),
            "ate": (hoje + timedelta(days=1)).isoformat(),
        },
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    assert all(log["acao"] == "tenant_suspenso_por_superadmin" for log in logs)

    resp_fora_do_intervalo = await client.get(
        "/admin/auditoria/logs",
        params={"desde": (hoje + timedelta(days=5)).isoformat()},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert resp_fora_do_intervalo.json() == []


async def test_auditoria_logs_requires_superadmin(client, db_sessionmaker):
    await _signup_and_tenant_id(client, db_sessionmaker, "naosuper3@example.com", "Tenant Não Super 3")

    login_resp = await client.post("/auth/login", json={"email": "naosuper3@example.com", "senha": "senha12345"})
    tenant_token = login_resp.json()["access_token"]

    resp = await client.get("/admin/auditoria/logs", headers={"Authorization": f"Bearer {tenant_token}"})
    assert resp.status_code == 403
