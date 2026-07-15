import uuid as uuid_pkg
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pyotp
import pytest
from sqlalchemy import select

from app.core.tenant_context import system_scope
from app.modules.auditoria.models import AuditLog
from app.modules.licenciamento import dunning
from app.modules.licenciamento.models import InvoiceStatus, License, LicenseStatus, PaymentEvent, Plan
from app.modules.licenciamento.payment_driver import FakeMercadoPagoDriver, get_payment_driver
from app.modules.licenciamento.service import (
    PlanNotFoundError,
    SeatLimitExceededError,
    get_plan_by_nome,
    ha_vaga_usuario_disponivel,
    iniciar_cobranca_ciclo_atual,
    reservar_vaga_usuario,
)
from app.modules.tenancy.models import Convite, Tenant, TenantStatus


async def _signup(client, email="lic@example.com", senha="senha12345"):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": f"Imobiliária {email}", "nome": "Lic Admin", "email": email, "senha": senha},
    )
    return resp.json()


async def _tenant_by_email(db_sessionmaker, admin_email: str) -> Tenant:
    async with db_sessionmaker() as session:
        with system_scope():
            from app.modules.tenancy.models import User

            result = await session.execute(select(User).where(User.email == admin_email))
            user = result.scalar_one()
            result = await session.execute(select(Tenant).where(Tenant.uuid == user.tenant_id))
            return result.scalar_one()


async def _ativar_2fa(client, token: str) -> None:
    setup = await client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {token}"})
    secret = parse_qs(urlparse(setup.json()["secret_otpauth_url"]).query)["secret"][0]
    codigo = pyotp.TOTP(secret).now()
    await client.post("/auth/2fa/verify", json={"codigo": codigo}, headers={"Authorization": f"Bearer {token}"})


async def _upgrade_to_pro(client, token: str) -> None:
    planos_resp = await client.get("/plans")
    plano_pro = next(p for p in planos_resp.json() if p["nome"] == "pro")
    resp = await client.post(
        "/license/upgrade", json={"plan_id": plano_pro["id"]}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200


# --- T051: signup cria license -------------------------------------------------------


async def test_signup_cria_license_trial_no_plano_solo(client, db_sessionmaker):
    body = await _signup(client, email="lic-signup@example.com")
    tenant = await _tenant_by_email(db_sessionmaker, "lic-signup@example.com")

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(License).where(License.tenant_id == tenant.uuid))
            license_ = result.scalar_one()
            result = await session.execute(select(Plan).where(Plan.id == license_.plan_id))
            plan = result.scalar_one()

    assert license_.status == LicenseStatus.TRIAL
    assert plan.nome == "solo"
    assert license_.preco_congelado == Decimal("39.0000")
    assert body["user"]["papel"] == "admin"


async def test_get_license_endpoint(client):
    token = (await _signup(client, email="lic-get@example.com"))["access_token"]
    resp = await client.get("/license", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "trial"
    assert body["plan"]["nome"] == "solo"


async def test_list_plans_apos_signup(client):
    await _signup(client, email="lic-plans@example.com")
    resp = await client.get("/plans")
    assert resp.status_code == 200
    nomes = {p["nome"] for p in resp.json()}
    assert nomes == {"solo", "pro", "enterprise"}


# --- T053: upgrade de plano + limite de vagas -------------------------------------------


async def test_upgrade_plan_altera_license_e_gera_auditoria(client, db_sessionmaker):
    token = (await _signup(client, email="lic-upgrade@example.com"))["access_token"]
    await _upgrade_to_pro(client, token)

    resp = await client.get("/license", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["plan"]["nome"] == "pro"

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(AuditLog).where(AuditLog.acao == "upgrade_plano"))
            registros = result.scalars().all()
    assert len(registros) == 1
    assert registros[0].ator_user_id is not None


async def test_upgrade_plan_requer_admin(client, db_sessionmaker):
    admin_token = (await _signup(client, email="lic-corretor-admin@example.com"))["access_token"]
    await _ativar_2fa(client, admin_token)
    await _upgrade_to_pro(client, admin_token)

    await client.post(
        "/users/convites",
        json={"email": "corretor-upgrade@example.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Convite).where(Convite.email == "corretor-upgrade@example.com"))
            convite_token = result.scalar_one().token

    accept_resp = await client.post(
        f"/convites/{convite_token}/aceitar", json={"nome": "Corretor X", "senha": "senha12345"}
    )
    corretor_token = accept_resp.json()["access_token"]

    planos_resp = await client.get("/plans")
    plano_enterprise = next(p for p in planos_resp.json() if p["nome"] == "enterprise")
    resp = await client.post(
        "/license/upgrade",
        json={"plan_id": plano_enterprise["id"]},
        headers={"Authorization": f"Bearer {corretor_token}"},
    )
    assert resp.status_code == 403


async def test_reservar_vaga_usuario_raises_quando_no_limite(client, db_sessionmaker):
    """Enforcement autoritativo (RN3) — testado direto na função usada por aceitar_convite,
    não só pela checagem leve de create_convite."""
    await _signup(client, email="lic-reservar1@example.com")
    tenant = await _tenant_by_email(db_sessionmaker, "lic-reservar1@example.com")

    async with db_sessionmaker() as session:
        with pytest.raises(SeatLimitExceededError):
            await reservar_vaga_usuario(session, tenant.uuid)  # plano solo: max_users=1, já ocupado pelo admin


async def test_reservar_vaga_usuario_noop_quando_plano_ilimitado(client, db_sessionmaker):
    token = (await _signup(client, email="lic-reservar2@example.com"))["access_token"]
    tenant = await _tenant_by_email(db_sessionmaker, "lic-reservar2@example.com")

    planos_resp = await client.get("/plans")
    plano_enterprise = next(p for p in planos_resp.json() if p["nome"] == "enterprise")
    await client.post(
        "/license/upgrade",
        json={"plan_id": plano_enterprise["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )

    async with db_sessionmaker() as session:
        await reservar_vaga_usuario(session, tenant.uuid)  # não deve levantar (max_users=None)


async def test_ha_vaga_usuario_disponivel_sem_license_retorna_true(db_sessionmaker):
    async with db_sessionmaker() as session:
        disponivel = await ha_vaga_usuario_disponivel(session, uuid_pkg.uuid4())
    assert disponivel is True


async def test_ha_vaga_usuario_disponivel_plano_ilimitado_retorna_true(client, db_sessionmaker):
    token = (await _signup(client, email="lic-havaga-ilimitado@example.com"))["access_token"]
    tenant = await _tenant_by_email(db_sessionmaker, "lic-havaga-ilimitado@example.com")

    planos_resp = await client.get("/plans")
    plano_enterprise = next(p for p in planos_resp.json() if p["nome"] == "enterprise")
    await client.post(
        "/license/upgrade",
        json={"plan_id": plano_enterprise["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )

    async with db_sessionmaker() as session:
        disponivel = await ha_vaga_usuario_disponivel(session, tenant.uuid)
    assert disponivel is True


async def test_get_plan_by_nome_inexistente_levanta_erro(db_sessionmaker):
    async with db_sessionmaker() as session:
        with pytest.raises(PlanNotFoundError):
            await get_plan_by_nome(session, "plano-que-nao-existe")


async def test_upgrade_plan_com_plano_inexistente_retorna_404(client):
    token = (await _signup(client, email="lic-upgrade-404@example.com"))["access_token"]
    resp = await client.post(
        "/license/upgrade",
        json={"plan_id": str(uuid_pkg.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_convidar_alem_do_limite_do_plano_solo_bloqueia_402(client):
    token = (await _signup(client, email="lic-limite@example.com"))["access_token"]
    # plano padrão é "solo" (max_users=1) — o próprio admin já ocupa a única vaga.
    await _ativar_2fa(client, token)

    resp = await client.post(
        "/users/convites", json={"email": "outrocorretor@example.com"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 402


# --- T054/T055: webhook idempotente + reativação -----------------------------------------


async def test_webhook_pagamento_confirma_e_reativa_tenant(client, db_sessionmaker):
    token = (await _signup(client, email="lic-webhook@example.com"))["access_token"]
    tenant = await _tenant_by_email(db_sessionmaker, "lic-webhook@example.com")

    async with db_sessionmaker() as session:
        invoice = await iniciar_cobranca_ciclo_atual(session, tenant_id=tenant.uuid, driver=FakeMercadoPagoDriver())

    resp = await client.post(
        "/webhooks/mercadopago",
        json={"event_id": "evt-1", "invoice_externa_id": invoice.externa_id, "status": "paid"},
    )
    assert resp.status_code == 200

    license_resp = await client.get("/license", headers={"Authorization": f"Bearer {token}"})
    assert license_resp.json()["status"] == "active"

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Tenant).where(Tenant.uuid == tenant.uuid))
            tenant_atualizado = result.scalar_one()
    assert tenant_atualizado.status == TenantStatus.ACTIVE


async def test_webhook_idempotente_nao_duplica_efeito(client, db_sessionmaker):
    await _signup(client, email="lic-idemp@example.com")
    tenant = await _tenant_by_email(db_sessionmaker, "lic-idemp@example.com")

    async with db_sessionmaker() as session:
        invoice = await iniciar_cobranca_ciclo_atual(session, tenant_id=tenant.uuid, driver=FakeMercadoPagoDriver())

    payload = {"event_id": "evt-dup", "invoice_externa_id": invoice.externa_id, "status": "paid"}
    first = await client.post("/webhooks/mercadopago", json=payload)
    second = await client.post("/webhooks/mercadopago", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(PaymentEvent).where(PaymentEvent.event_id_externo == "evt-dup"))
            eventos = result.scalars().all()
    assert len(eventos) == 1


async def test_webhook_evento_refunded_marca_invoice_estornada(client, db_sessionmaker):
    await _signup(client, email="lic-refund@example.com")
    tenant = await _tenant_by_email(db_sessionmaker, "lic-refund@example.com")
    async with db_sessionmaker() as session:
        invoice = await iniciar_cobranca_ciclo_atual(session, tenant_id=tenant.uuid, driver=FakeMercadoPagoDriver())

    resp = await client.post(
        "/webhooks/mercadopago",
        json={"event_id": "evt-refund", "invoice_externa_id": invoice.externa_id, "status": "refunded"},
    )
    assert resp.status_code == 200

    from app.modules.licenciamento.models import Invoice as InvoiceModel

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(InvoiceModel).where(InvoiceModel.id == invoice.id))
            invoice_atualizada = result.scalar_one()
    assert invoice_atualizada.status == InvoiceStatus.REFUNDED


async def test_webhook_evento_failed_marca_invoice_falha(client, db_sessionmaker):
    await _signup(client, email="lic-failed@example.com")
    tenant = await _tenant_by_email(db_sessionmaker, "lic-failed@example.com")
    async with db_sessionmaker() as session:
        invoice = await iniciar_cobranca_ciclo_atual(session, tenant_id=tenant.uuid, driver=FakeMercadoPagoDriver())

    resp = await client.post(
        "/webhooks/mercadopago",
        json={"event_id": "evt-failed", "invoice_externa_id": invoice.externa_id, "status": "failed"},
    )
    assert resp.status_code == 200

    from app.modules.licenciamento.models import Invoice as InvoiceModel

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(InvoiceModel).where(InvoiceModel.id == invoice.id))
            invoice_atualizada = result.scalar_one()
    assert invoice_atualizada.status == InvoiceStatus.FAILED


async def test_webhook_evento_sem_invoice_conhecida_nao_quebra(client):
    resp = await client.post(
        "/webhooks/mercadopago",
        json={"event_id": "evt-orfao", "invoice_externa_id": "nao-existe", "status": "paid"},
    )
    assert resp.status_code == 200


async def test_webhook_assinatura_invalida_retorna_401(client):
    class DriverAssinaturaInvalida(FakeMercadoPagoDriver):
        def verificar_assinatura(self, payload, headers):
            return False

    from app.main import app

    app.dependency_overrides[get_payment_driver] = lambda: DriverAssinaturaInvalida()
    try:
        resp = await client.post("/webhooks/mercadopago", json={"event_id": "x", "status": "paid"})
    finally:
        del app.dependency_overrides[get_payment_driver]

    assert resp.status_code == 401


async def test_webhook_payload_nao_json_nao_quebra(client):
    resp = await client.post(
        "/webhooks/mercadopago", content=b"corpo-nao-json", headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 200


# --- GET /license e GET /invoices ---------------------------------------------------------


async def test_obter_license_sem_license_retorna_404(client, db_sessionmaker):
    token = (await _signup(client, email="lic-sem-license@example.com"))["access_token"]
    tenant = await _tenant_by_email(db_sessionmaker, "lic-sem-license@example.com")

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(License).where(License.tenant_id == tenant.uuid))
            await session.delete(result.scalar_one())
            await session.commit()

    resp = await client.get("/license", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


async def test_listar_faturas_retorna_faturas_do_tenant(client, db_sessionmaker):
    token = (await _signup(client, email="lic-faturas@example.com"))["access_token"]
    tenant = await _tenant_by_email(db_sessionmaker, "lic-faturas@example.com")

    async with db_sessionmaker() as session:
        invoice = await iniciar_cobranca_ciclo_atual(session, tenant_id=tenant.uuid, driver=FakeMercadoPagoDriver())

    resp = await client.get("/invoices", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    faturas = resp.json()
    assert len(faturas) == 1
    assert faturas[0]["id"] == str(invoice.uuid)
    assert faturas[0]["status"] == "pending"


async def test_listar_faturas_requer_admin(client, db_sessionmaker):
    token = (await _signup(client, email="lic-faturas-admin@example.com"))["access_token"]
    await _ativar_2fa(client, token)
    await _upgrade_to_pro(client, token)

    convite_resp = await client.post(
        "/users/convites",
        json={"email": "corretor-faturas@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Convite).where(Convite.email == "corretor-faturas@example.com"))
            convite = result.scalar_one()
    aceitar_resp = await client.post(
        f"/convites/{convite.token}/aceitar", json={"nome": "Corretor", "senha": "senha12345"}
    )
    assert convite_resp.status_code == 201
    corretor_token = aceitar_resp.json()["access_token"]

    resp = await client.get("/invoices", headers={"Authorization": f"Bearer {corretor_token}"})
    assert resp.status_code == 403


# --- T057: régua de dunning (função pura + job) -------------------------------------------


def _license_fake(status: LicenseStatus, *, trial_termina_em=None, past_due_desde=None) -> License:
    lic = License(
        tenant_id=uuid_pkg.uuid4(),
        plan_id=1,
        preco_congelado=Decimal("39.0000"),
        status=status,
        trial_termina_em=trial_termina_em or datetime.now(timezone.utc) + timedelta(days=1),
    )
    lic.past_due_desde = past_due_desde
    return lic


def test_calcular_novo_status_trial_nao_expirado_permanece_trial():
    agora = datetime.now(timezone.utc)
    lic = _license_fake(LicenseStatus.TRIAL, trial_termina_em=agora + timedelta(hours=1))
    assert dunning.calcular_novo_status(lic, agora) == LicenseStatus.TRIAL


def test_calcular_novo_status_trial_expirado_vira_past_due():
    agora = datetime.now(timezone.utc)
    lic = _license_fake(LicenseStatus.TRIAL, trial_termina_em=agora - timedelta(minutes=1))
    assert dunning.calcular_novo_status(lic, agora) == LicenseStatus.PAST_DUE


def test_calcular_novo_status_past_due_recente_permanece():
    agora = datetime.now(timezone.utc)
    lic = _license_fake(LicenseStatus.PAST_DUE, past_due_desde=agora - timedelta(days=2))
    assert dunning.calcular_novo_status(lic, agora) == LicenseStatus.PAST_DUE


def test_calcular_novo_status_past_due_alem_do_limite_vira_suspended():
    agora = datetime.now(timezone.utc)
    lic = _license_fake(LicenseStatus.PAST_DUE, past_due_desde=agora - timedelta(days=8))
    assert dunning.calcular_novo_status(lic, agora) == LicenseStatus.SUSPENDED


def test_calcular_novo_status_active_nao_muda_automaticamente():
    agora = datetime.now(timezone.utc)
    lic = _license_fake(LicenseStatus.ACTIVE)
    assert dunning.calcular_novo_status(lic, agora) == LicenseStatus.ACTIVE


async def test_executar_dunning_transiciona_trial_expirado_e_audita(client, db_sessionmaker):
    await _signup(client, email="lic-dunning1@example.com")
    tenant = await _tenant_by_email(db_sessionmaker, "lic-dunning1@example.com")

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(License).where(License.tenant_id == tenant.uuid))
            license_ = result.scalar_one()
            license_.trial_termina_em = datetime.now(timezone.utc) - timedelta(days=1)
            await session.commit()

    transicoes = await dunning.executar_dunning(db_sessionmaker)
    assert transicoes == 1

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(License).where(License.tenant_id == tenant.uuid))
            license_atualizada = result.scalar_one()
            result = await session.execute(select(Tenant).where(Tenant.uuid == tenant.uuid))
            tenant_atualizado = result.scalar_one()
            result = await session.execute(select(AuditLog).where(AuditLog.acao == "dunning_transition"))
            registros = result.scalars().all()

    assert license_atualizada.status == LicenseStatus.PAST_DUE
    assert tenant_atualizado.status == TenantStatus.PAST_DUE
    assert len(registros) == 1

    # idempotência: rodar de novo no mesmo dia não gera nova transição para essa license
    transicoes_2 = await dunning.executar_dunning(db_sessionmaker)
    assert transicoes_2 == 0


async def test_executar_dunning_suspende_apos_prazo(client, db_sessionmaker):
    await _signup(client, email="lic-dunning2@example.com")
    tenant = await _tenant_by_email(db_sessionmaker, "lic-dunning2@example.com")

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(License).where(License.tenant_id == tenant.uuid))
            license_ = result.scalar_one()
            license_.status = LicenseStatus.PAST_DUE
            license_.past_due_desde = datetime.now(timezone.utc) - timedelta(days=10)
            await session.commit()

    await dunning.executar_dunning(db_sessionmaker)

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(License).where(License.tenant_id == tenant.uuid))
            license_atualizada = result.scalar_one()
    assert license_atualizada.status == LicenseStatus.SUSPENDED
