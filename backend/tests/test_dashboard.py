import uuid as uuid_pkg
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pyotp
from sqlalchemy import select

from app.core.tenant_context import system_scope, tenant_scope
from app.modules.dashboard.service import obter_leads_por_origem, obter_resumo, obter_vendas_por_mes
from app.modules.imoveis.models import Imovel
from app.modules.leads.models import Lead
from app.modules.tenancy.models import Convite, Tenant, User

_IMOVEL_PADRAO = {
    "titulo": "Apartamento dashboard",
    "cep": "01310-100",
    "bairro": "Centro",
    "cidade": "São Paulo",
    "estado": "SP",
    "tipo": "apartamento",
    "area_total": 100,
}


async def _signup(client, email="dash@example.com"):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": f"Imobiliária {email}", "nome": "Admin", "email": email, "senha": "senha12345"},
    )
    return resp.json()["access_token"]


async def _tenant_e_admin(db_sessionmaker, email: str) -> tuple[Tenant, User]:
    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            result = await session.execute(select(Tenant).where(Tenant.uuid == user.tenant_id))
            tenant = result.scalar_one()
            return tenant, user


async def _criar_imovel(client, token, **overrides):
    payload = {**_IMOVEL_PADRAO, **overrides}
    resp = await client.post("/imoveis", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    return resp.json()


async def _criar_lead(client, token, **overrides):
    payload = {"nome": "Lead dashboard", "origem": "site", **overrides}
    resp = await client.post("/leads", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    return resp.json()


# --- T411: obter_resumo -------------------------------------------------------------------


async def test_resumo_imoveis_por_status(client, db_sessionmaker):
    token = await _signup(client, email="resumo-status@example.com")
    tenant, admin = await _tenant_e_admin(db_sessionmaker, "resumo-status@example.com")

    imovel = await _criar_imovel(client, token)
    await _criar_imovel(client, token, titulo="Outro")
    await client.put(
        f"/imoveis/{imovel['id']}", json={**_IMOVEL_PADRAO, "status": "reservado"}, headers={"Authorization": f"Bearer {token}"}
    )

    async with db_sessionmaker() as session:
        resumo = await obter_resumo(session, tenant_id=tenant.uuid, user=admin)

    assert resumo["imoveis_por_status"]["reservado"] == 1
    assert resumo["imoveis_por_status"]["disponivel"] == 1


async def test_resumo_leads_ativos_e_taxa_conversao(client, db_sessionmaker):
    token = await _signup(client, email="resumo-leads@example.com")
    tenant, admin = await _tenant_e_admin(db_sessionmaker, "resumo-leads@example.com")

    lead1 = await _criar_lead(client, token)
    await _criar_lead(client, token)
    await client.put(f"/leads/{lead1['id']}/estagio", json={"estagio": "fechado"}, headers={"Authorization": f"Bearer {token}"})

    async with db_sessionmaker() as session:
        resumo = await obter_resumo(session, tenant_id=tenant.uuid, user=admin)

    assert resumo["leads_ativos"] == 1  # só o não-fechado
    assert resumo["taxa_conversao"] == 0.5  # 1 fechado de 2 criados


async def test_resumo_sem_leads_retorna_taxa_conversao_zero(client, db_sessionmaker):
    await _signup(client, email="resumo-sem-leads@example.com")
    tenant, admin = await _tenant_e_admin(db_sessionmaker, "resumo-sem-leads@example.com")

    async with db_sessionmaker() as session:
        resumo = await obter_resumo(session, tenant_id=tenant.uuid, user=admin)

    assert resumo["taxa_conversao"] == 0.0
    assert resumo["ticket_medio"] is None
    assert resumo["tempo_medio_venda_imovel_dias"] is None
    assert resumo["tempo_medio_fechamento_lead_dias"] is None


async def test_resumo_leads_sem_contato_respeita_parametro_dias(client, db_sessionmaker):
    token = await _signup(client, email="resumo-sem-contato@example.com")
    tenant, admin = await _tenant_e_admin(db_sessionmaker, "resumo-sem-contato@example.com")
    lead = await _criar_lead(client, token)

    antigo = datetime.now(timezone.utc) - timedelta(days=10)
    async with db_sessionmaker() as session:
        with tenant_scope(tenant.uuid):
            result = await session.execute(select(Lead).where(Lead.uuid == uuid_pkg.UUID(lead["id"])))
            registro = result.scalar_one()
            registro.created_at = antigo
            await session.commit()

    async with db_sessionmaker() as session:
        resumo_padrao = await obter_resumo(session, tenant_id=tenant.uuid, user=admin, dias_sem_contato=3)
        resumo_estrito = await obter_resumo(session, tenant_id=tenant.uuid, user=admin, dias_sem_contato=30)

    assert resumo_padrao["leads_sem_contato"] == 1
    assert resumo_estrito["leads_sem_contato"] == 0


async def test_resumo_ticket_medio_e_tempo_venda_apos_venda(client, db_sessionmaker):
    token = await _signup(client, email="resumo-venda@example.com")
    tenant, admin = await _tenant_e_admin(db_sessionmaker, "resumo-venda@example.com")
    imovel = await _criar_imovel(client, token, valor_anunciado=500000)

    await client.put(
        f"/imoveis/{imovel['id']}", json={**_IMOVEL_PADRAO, "status": "vendido", "valor_anunciado": 500000},
        headers={"Authorization": f"Bearer {token}"},
    )

    async with db_sessionmaker() as session:
        resumo = await obter_resumo(session, tenant_id=tenant.uuid, user=admin)

    assert resumo["ticket_medio"] == 500000
    # Regressão: imóvel vendido no mesmo dia do cadastro nunca pode dar tempo negativo.
    assert resumo["tempo_medio_venda_imovel_dias"] is not None
    assert resumo["tempo_medio_venda_imovel_dias"] >= 0


async def test_corretor_ve_so_propria_carteira_admin_ve_tudo(client, db_sessionmaker):
    admin_token = await _signup(client, email="resumo-visibilidade@example.com")
    tenant, admin = await _tenant_e_admin(db_sessionmaker, "resumo-visibilidade@example.com")

    setup = await client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {admin_token}"})
    secret = parse_qs(urlparse(setup.json()["secret_otpauth_url"]).query)["secret"][0]
    codigo = pyotp.TOTP(secret).now()
    await client.post("/auth/2fa/verify", json={"codigo": codigo}, headers={"Authorization": f"Bearer {admin_token}"})
    planos_resp = await client.get("/plans")
    plano_pro = next(p for p in planos_resp.json() if p["nome"] == "pro")
    await client.post("/license/upgrade", json={"plan_id": plano_pro["id"]}, headers={"Authorization": f"Bearer {admin_token}"})
    await client.post(
        "/users/convites", json={"email": "resumo-corretor@example.com"}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Convite).where(Convite.email == "resumo-corretor@example.com"))
            convite = result.scalar_one()
    aceitar = await client.post(f"/convites/{convite.token}/aceitar", json={"nome": "Corretor", "senha": "senha12345"})
    corretor_token = aceitar.json()["access_token"]
    async with db_sessionmaker() as session:
        with system_scope():
            corretor = (await session.execute(select(User).where(User.email == "resumo-corretor@example.com"))).scalar_one()

    await _criar_imovel(client, admin_token)
    await _criar_imovel(client, corretor_token)

    async with db_sessionmaker() as session:
        resumo_corretor = await obter_resumo(session, tenant_id=tenant.uuid, user=corretor)
        resumo_admin = await obter_resumo(session, tenant_id=tenant.uuid, user=admin)

    total_corretor = sum(resumo_corretor["imoveis_por_status"].values())
    total_admin = sum(resumo_admin["imoveis_por_status"].values())
    assert total_corretor == 1
    assert total_admin == 2


async def test_resumo_isolamento_entre_tenants(client, db_sessionmaker):
    token_a = await _signup(client, email="resumo-tenant-a@example.com")
    await _signup(client, email="resumo-tenant-b@example.com")
    tenant_b, admin_b = await _tenant_e_admin(db_sessionmaker, "resumo-tenant-b@example.com")

    await _criar_imovel(client, token_a)
    await _criar_imovel(client, token_a, titulo="Outro A")

    async with db_sessionmaker() as session:
        resumo_b = await obter_resumo(session, tenant_id=tenant_b.uuid, user=admin_b)

    assert sum(resumo_b["imoveis_por_status"].values()) == 0


# --- T412: obter_vendas_por_mes ------------------------------------------------------------


async def test_vendas_por_mes_preenche_mes_sem_venda_e_soma_valores(client, db_sessionmaker):
    await _signup(client, email="vendas-mes@example.com")
    tenant, admin = await _tenant_e_admin(db_sessionmaker, "vendas-mes@example.com")

    hoje = date.today()
    mes_passado = (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)

    async with db_sessionmaker() as session:
        with tenant_scope(tenant.uuid):
            session.add(
                Imovel(
                    tenant_id=tenant.uuid,
                    corretor_id=admin.uuid,
                    titulo="Vendido mês passado",
                    cep="01310-100",
                    bairro="Centro",
                    cidade="São Paulo",
                    estado="SP",
                    tipo="apartamento",
                    area_total=80,
                    status="vendido",
                    data_venda=mes_passado,
                    valor_anunciado=300000,
                    fotos="[]",
                )
            )
            await session.commit()

    async with db_sessionmaker() as session:
        serie = await obter_vendas_por_mes(session, tenant_id=tenant.uuid, user=admin, meses=3)

    assert len(serie) == 3
    ponto_mes_passado = next(p for p in serie if p["ano"] == mes_passado.year and p["mes"] == mes_passado.month)
    assert ponto_mes_passado["quantidade"] == 1
    assert ponto_mes_passado["valor_total"] == 300000
    outros = [p for p in serie if p is not ponto_mes_passado]
    assert all(p["quantidade"] == 0 for p in outros)


# --- T413: obter_leads_por_origem -----------------------------------------------------------


async def test_leads_por_origem_conta_corretamente_e_omite_origem_sem_lead(client, db_sessionmaker):
    token = await _signup(client, email="leads-origem@example.com")
    tenant, admin = await _tenant_e_admin(db_sessionmaker, "leads-origem@example.com")

    await _criar_lead(client, token, origem="site")
    await _criar_lead(client, token, origem="site")
    await _criar_lead(client, token, origem="indicacao")

    async with db_sessionmaker() as session:
        origens = await obter_leads_por_origem(session, tenant_id=tenant.uuid, user=admin)

    por_origem = {o["origem"]: o["quantidade"] for o in origens}
    assert por_origem == {"site": 2, "indicacao": 1}
    assert "portal" not in por_origem


# --- T420-T422: endpoints HTTP ------------------------------------------------------------


async def test_endpoint_resumo(client):
    token = await _signup(client, email="endpoint-resumo@example.com")
    await _criar_imovel(client, token)
    await _criar_lead(client, token)

    resp = await client.get("/dashboard/resumo", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["imoveis_por_status"]["disponivel"] == 1
    assert body["leads_ativos"] == 1
    assert body["ticket_medio"] is None


async def test_endpoint_vendas_por_mes(client):
    token = await _signup(client, email="endpoint-vendas@example.com")

    resp = await client.get("/dashboard/vendas-por-mes?meses=6", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 6


async def test_endpoint_leads_por_origem(client):
    token = await _signup(client, email="endpoint-origem@example.com")
    await _criar_lead(client, token, origem="portal")

    resp = await client.get("/dashboard/leads-por-origem", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == [{"origem": "portal", "quantidade": 1}]


async def test_endpoint_requer_autenticacao(client):
    resp = await client.get("/dashboard/resumo")
    assert resp.status_code == 401
