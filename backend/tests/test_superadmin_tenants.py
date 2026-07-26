from app.modules.superadmin import service


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


# --- T621: listagem cross-tenant ---------------------------------------------------------------


async def test_listar_tenants_shows_tenants_from_different_fixtures(client, db_sessionmaker):
    await _signup(client, "empresa-a@example.com", "Imobiliária A")
    await _signup(client, "empresa-b@example.com", "Imobiliária B")
    superadmin_token = await _bootstrap_and_login(client, db_sessionmaker)

    resp = await client.get("/admin/tenants", headers={"Authorization": f"Bearer {superadmin_token}"})
    assert resp.status_code == 200
    nomes = {t["nome"] for t in resp.json()}
    assert {"Imobiliária A", "Imobiliária B"}.issubset(nomes)


async def test_listar_tenants_requires_superadmin_token(client):
    admin_body = await _signup(client, "naosuper@example.com", "Imobiliária Comum")
    resp = await client.get("/admin/tenants", headers={"Authorization": f"Bearer {admin_body['access_token']}"})
    assert resp.status_code == 403


# --- T622: métricas individuais -----------------------------------------------------------------


async def test_metricas_tenant_reflects_fixture_state(client, db_sessionmaker):
    await _signup(client, "metricas@example.com", "Imobiliária Métricas")
    from sqlalchemy import select

    from app.core.tenant_context import system_scope
    from app.modules.tenancy.models import User

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == "metricas@example.com"))
            tenant_id = str(result.scalar_one().tenant_id)

    superadmin_token = await _bootstrap_and_login(client, db_sessionmaker)
    resp = await client.get(
        f"/admin/tenants/{tenant_id}/metricas", headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["usuarios_ativos"] == 1
    assert body["imoveis_ativos"] == 0
    assert body["leads_total"] == 0
    assert body["avaliacoes_mes"] == 0
    assert body["license"]["plano"] == "solo"
    assert body["license"]["status"] == "trial"


async def test_metricas_tenant_desconhecido_retorna_404(client, db_sessionmaker):
    import uuid

    superadmin_token = await _bootstrap_and_login(client, db_sessionmaker)
    resp = await client.get(
        f"/admin/tenants/{uuid.uuid4()}/metricas", headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    assert resp.status_code == 404


# --- T623/T624: suspender/reativar ---------------------------------------------------------------


async def test_suspender_tenant_blocks_access_and_grava_auditoria(client, db_sessionmaker):
    from sqlalchemy import select

    from app.core.tenant_context import system_scope
    from app.modules.auditoria.models import AuditLog
    from app.modules.tenancy.models import User

    signup_body = await _signup(client, "abuso@example.com", "Imobiliária Abuso")
    tenant_token = signup_body["access_token"]

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == "abuso@example.com"))
            tenant_id = str(result.scalar_one().tenant_id)

    superadmin_token = await _bootstrap_and_login(client, db_sessionmaker)
    suspender_resp = await client.post(
        f"/admin/tenants/{tenant_id}/suspender", headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    assert suspender_resp.status_code == 200

    bloqueado = await client.get("/imoveis", headers={"Authorization": f"Bearer {tenant_token}"})
    assert bloqueado.status_code == 403

    async with db_sessionmaker() as session:
        with system_scope():
            logs = (
                await session.execute(
                    select(AuditLog).where(AuditLog.acao == "tenant_suspenso_por_superadmin")
                )
            ).scalars().all()
            assert len(logs) == 1


async def test_reativar_tenant_restaura_acesso(client, db_sessionmaker):
    from sqlalchemy import select

    from app.core.tenant_context import system_scope
    from app.modules.tenancy.models import User

    signup_body = await _signup(client, "reativa@example.com", "Imobiliária Reativa")
    tenant_token = signup_body["access_token"]

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == "reativa@example.com"))
            tenant_id = str(result.scalar_one().tenant_id)

    superadmin_token = await _bootstrap_and_login(client, db_sessionmaker)
    await client.post(f"/admin/tenants/{tenant_id}/suspender", headers={"Authorization": f"Bearer {superadmin_token}"})
    reativar_resp = await client.post(
        f"/admin/tenants/{tenant_id}/reativar", headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    assert reativar_resp.status_code == 200

    restaurado = await client.get("/imoveis", headers={"Authorization": f"Bearer {tenant_token}"})
    assert restaurado.status_code == 200


async def test_suspender_tenant_desconhecido_retorna_404(client, db_sessionmaker):
    import uuid

    superadmin_token = await _bootstrap_and_login(client, db_sessionmaker)
    resp = await client.post(
        f"/admin/tenants/{uuid.uuid4()}/suspender", headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    assert resp.status_code == 404


async def test_reativar_tenant_desconhecido_retorna_404(client, db_sessionmaker):
    import uuid

    superadmin_token = await _bootstrap_and_login(client, db_sessionmaker)
    resp = await client.post(
        f"/admin/tenants/{uuid.uuid4()}/reativar", headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    assert resp.status_code == 404


async def test_suspender_requires_superadmin_not_tenant_admin(client, db_sessionmaker):
    from sqlalchemy import select

    from app.core.tenant_context import system_scope
    from app.modules.tenancy.models import User

    signup_body = await _signup(client, "naosuperadmin@example.com", "Imobiliária Não Super")
    tenant_admin_token = signup_body["access_token"]

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == "naosuperadmin@example.com"))
            tenant_id = str(result.scalar_one().tenant_id)

    resp = await client.post(
        f"/admin/tenants/{tenant_id}/suspender", headers={"Authorization": f"Bearer {tenant_admin_token}"}
    )
    assert resp.status_code == 403
