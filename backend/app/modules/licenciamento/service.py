import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import system_scope, tenant_scope
from app.modules.auditoria import service as auditoria_service
from app.modules.licenciamento.models import Invoice, InvoiceStatus, License, LicenseStatus, PaymentEvent, Plan
from app.modules.licenciamento.payment_driver import PagamentoGatewayDriver
from app.modules.tenancy.models import Tenant, TenantStatus, User

PLAN_SEED: list[dict[str, Any]] = [
    {"nome": "solo", "max_users": 1, "max_imoveis": 50, "preco_mensal": Decimal("39.0000")},
    {"nome": "pro", "max_users": 5, "max_imoveis": None, "preco_mensal": Decimal("79.0000")},
    {"nome": "enterprise", "max_users": None, "max_imoveis": None, "preco_mensal": Decimal("0.0000")},
]

DEFAULT_PLAN_NOME = "solo"


class PlanNotFoundError(Exception):
    pass


class SeatLimitExceededError(Exception):
    pass


class ImovelLimitExceededError(Exception):
    pass


class InvalidWebhookSignatureError(Exception):
    pass


async def ensure_plans_seeded(session: AsyncSession) -> None:
    result = await session.execute(select(func.count()).select_from(Plan))
    if result.scalar_one() > 0:
        return
    for dados in PLAN_SEED:
        session.add(Plan(**dados))
    await session.commit()


async def get_plan_by_nome(session: AsyncSession, nome: str) -> Plan:
    result = await session.execute(select(Plan).where(Plan.nome == nome))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise PlanNotFoundError(nome)
    return plan


async def get_plan_by_uuid(session: AsyncSession, plan_uuid: uuid.UUID) -> Plan:
    result = await session.execute(select(Plan).where(Plan.uuid == plan_uuid))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise PlanNotFoundError(str(plan_uuid))
    return plan


async def get_plan_by_id(session: AsyncSession, plan_id: int) -> Plan:
    result = await session.execute(select(Plan).where(Plan.id == plan_id))
    return result.scalar_one()


async def list_active_plans(session: AsyncSession) -> list[Plan]:
    result = await session.execute(select(Plan).where(Plan.ativo.is_(True)).order_by(Plan.preco_mensal))
    return list(result.scalars().all())


async def create_license(session: AsyncSession, *, tenant: Tenant, plan: Plan) -> License:
    now = datetime.now(timezone.utc)
    with tenant_scope(tenant.uuid):
        license_ = License(
            tenant_id=tenant.uuid,
            plan_id=plan.id,
            preco_congelado=plan.preco_mensal,
            status=LicenseStatus.TRIAL,
            trial_termina_em=now + timedelta(days=7),
        )
        session.add(license_)
        await session.flush()
    return license_


async def get_license(session: AsyncSession, tenant_id: uuid.UUID) -> License | None:
    with tenant_scope(tenant_id):
        result = await session.execute(select(License).where(License.tenant_id == tenant_id))
        return result.scalar_one_or_none()


async def get_license_with_plan(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[License, Plan] | None:
    license_ = await get_license(session, tenant_id)
    if license_ is None:
        return None
    plan = await get_plan_by_id(session, license_.plan_id)
    return license_, plan


async def sync_tenant_status(session: AsyncSession, tenant_id: uuid.UUID, status: LicenseStatus) -> None:
    result = await session.execute(select(Tenant).where(Tenant.uuid == tenant_id))
    tenant = result.scalar_one()
    tenant.status = TenantStatus(status.value)


async def reservar_vaga_usuario(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Autoritativo (RN3): chamar imediatamente antes de inserir um novo User. Lock
    pessimista na license evita duas criações simultâneas ultrapassarem o limite."""
    with tenant_scope(tenant_id):
        result = await session.execute(select(License).where(License.tenant_id == tenant_id).with_for_update())
        license_ = result.scalar_one()
        plan = await get_plan_by_id(session, license_.plan_id)
        if plan.max_users is None:
            return
        count_result = await session.execute(
            select(func.count()).select_from(User).where(User.tenant_id == tenant_id, User.ativo.is_(True))
        )
        if count_result.scalar_one() >= plan.max_users:
            raise SeatLimitExceededError(tenant_id)


async def reservar_vaga_imovel(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Autoritativo (RN3): chamar imediatamente antes de inserir um novo Imovel. Lock
    pessimista na license evita duas criações simultâneas ultrapassarem o limite."""
    from app.modules.imoveis.models import Imovel

    with tenant_scope(tenant_id):
        result = await session.execute(select(License).where(License.tenant_id == tenant_id).with_for_update())
        license_ = result.scalar_one()
        plan = await get_plan_by_id(session, license_.plan_id)
        if plan.max_imoveis is None:
            return
        count_result = await session.execute(
            select(func.count()).select_from(Imovel).where(Imovel.tenant_id == tenant_id, Imovel.ativo.is_(True))
        )
        if count_result.scalar_one() >= plan.max_imoveis:
            raise ImovelLimitExceededError(tenant_id)


async def ha_vaga_usuario_disponivel(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
    """Checagem leve (sem lock) usada na criação do convite, só para feedback rápido —
    a garantia de fato vem de reservar_vaga_usuario() no momento do aceite (RN3)."""
    licenca_e_plano = await get_license_with_plan(session, tenant_id)
    if licenca_e_plano is None:
        return True
    license_, plan = licenca_e_plano
    if plan.max_users is None:
        return True
    with tenant_scope(tenant_id):
        count_result = await session.execute(
            select(func.count()).select_from(User).where(User.tenant_id == tenant_id, User.ativo.is_(True))
        )
    return count_result.scalar_one() < plan.max_users


async def upgrade_plan(
    session: AsyncSession, *, tenant_id: uuid.UUID, ator: User, novo_plan_uuid: uuid.UUID
) -> tuple[License, Plan]:
    novo_plano = await get_plan_by_uuid(session, novo_plan_uuid)
    with tenant_scope(tenant_id):
        result = await session.execute(select(License).where(License.tenant_id == tenant_id).with_for_update())
        license_ = result.scalar_one()
        antes = {"plan_id": license_.plan_id, "preco_congelado": str(license_.preco_congelado)}
        license_.plan_id = novo_plano.id
        license_.preco_congelado = novo_plano.preco_mensal
        await session.flush()
        await auditoria_service.record(
            session,
            tenant_id=tenant_id,
            ator_user_id=ator.id,
            acao="upgrade_plano",
            entidade="license",
            entidade_id=str(license_.uuid),
            antes=antes,
            depois={"plan_id": novo_plano.id, "preco_congelado": str(novo_plano.preco_mensal)},
        )
    await session.commit()
    return license_, novo_plano


async def iniciar_cobranca_ciclo_atual(
    session: AsyncSession, *, tenant_id: uuid.UUID, driver: PagamentoGatewayDriver
) -> Invoice:
    now = datetime.now(timezone.utc)
    with tenant_scope(tenant_id):
        license_ = await get_license(session, tenant_id)
        assert license_ is not None
        externa_id = await driver.criar_cobranca(
            valor=license_.preco_congelado, referencia=f"{tenant_id}-{now.year}-{now.month:02d}"
        )
        invoice = Invoice(
            tenant_id=tenant_id,
            license_id=license_.id,
            valor=license_.preco_congelado,
            status=InvoiceStatus.PENDING,
            ciclo_mes=now.month,
            ciclo_ano=now.year,
            vencimento=now.date(),
            externa_id=externa_id,
        )
        session.add(invoice)
        await session.flush()
    await session.commit()
    return invoice


async def registrar_evento_pagamento(
    session: AsyncSession,
    *,
    driver: PagamentoGatewayDriver,
    payload_bytes: bytes,
    headers: dict[str, str],
    payload_json: dict,
) -> None:
    if not driver.verificar_assinatura(payload_bytes, headers):
        raise InvalidWebhookSignatureError()

    evento = driver.extrair_evento(payload_json)

    invoice = None
    if evento.invoice_externa_id:
        with system_scope():
            result = await session.execute(select(Invoice).where(Invoice.externa_id == evento.invoice_externa_id))
            invoice = result.scalar_one_or_none()

    if invoice is None:
        # Sem invoice conhecida não há tenant para atribuir o evento (PaymentEvent é
        # tenant-scoped) — nada a persistir. O gateway reenvia se/quando a fatura existir.
        return

    tenant_id = invoice.tenant_id
    with tenant_scope(tenant_id):
        try:
            session.add(
                PaymentEvent(
                    tenant_id=tenant_id,
                    invoice_id=invoice.id,
                    event_id_externo=evento.event_id_externo,
                    payload=json.dumps(payload_json, default=str),
                )
            )
            await session.flush()
        except IntegrityError:
            await session.rollback()
            return  # já processado (RN5) — idempotente, sem reprocessar efeito

        if evento.status == "paid":
            invoice.status = InvoiceStatus.PAID
            invoice.pago_em = datetime.now(timezone.utc)
            license_ = await get_license(session, tenant_id)
            assert license_ is not None
            antes = {"status": license_.status.value}
            license_.status = LicenseStatus.ACTIVE
            license_.past_due_desde = None
            await sync_tenant_status(session, tenant_id, LicenseStatus.ACTIVE)
            await auditoria_service.record(
                session,
                tenant_id=tenant_id,
                ator_user_id=None,
                acao="pagamento_confirmado",
                entidade="license",
                entidade_id=str(license_.uuid),
                antes=antes,
                depois={"status": "active"},
            )
        elif evento.status == "refunded":
            invoice.status = InvoiceStatus.REFUNDED
        elif evento.status == "failed":
            invoice.status = InvoiceStatus.FAILED
        # demais status ("unknown" etc.): evento fica registrado (idempotência), sem mudar estado

        await session.commit()
