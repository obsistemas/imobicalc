import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.core.tenant_context import system_scope
from app.modules.auditoria import service as auditoria_service
from app.modules.auditoria.models import AuditLog
from app.modules.avaliacoes.models import Avaliacao
from app.modules.imoveis.models import Imovel
from app.modules.leads.models import Lead
from app.modules.licenciamento.models import Invoice, InvoiceStatus, License, LicenseStatus, Plan
from app.modules.superadmin.models import SuperadminUser
from app.modules.tenancy.models import Tenant, TenantStatus, User


class InvalidCredentialsError(Exception):
    pass


class TenantNotFoundError(Exception):
    pass


async def bootstrap_superadmin(session: AsyncSession, *, email: str, password: str, nome: str = "Superadmin") -> None:
    """Idempotente: só cria se `email`/`senha` vierem preenchidos e não existir conta com aquele
    e-mail ainda. Nunca reseta a senha de uma conta já existente (evita reset acidental a cada
    deploy/boot)."""
    if not email or not password:
        return
    result = await session.execute(select(SuperadminUser).where(SuperadminUser.email == email))
    if result.scalar_one_or_none() is not None:
        return
    session.add(SuperadminUser(nome=nome, email=email, password_hash=hash_password(password)))
    await session.commit()


async def authenticate(session: AsyncSession, *, email: str, senha: str) -> SuperadminUser:
    result = await session.execute(select(SuperadminUser).where(SuperadminUser.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.ativo or not verify_password(senha, user.password_hash):
        raise InvalidCredentialsError(email)
    return user


async def get_superadmin_by_uuid(session: AsyncSession, superadmin_uuid: uuid.UUID) -> SuperadminUser | None:
    result = await session.execute(select(SuperadminUser).where(SuperadminUser.uuid == superadmin_uuid))
    return result.scalar_one_or_none()


async def _plano_nome(session: AsyncSession, plan_id: int | None) -> str | None:
    if plan_id is None:
        return None
    result = await session.execute(select(Plan.nome).where(Plan.id == plan_id))
    return result.scalar_one_or_none()


async def _get_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    result = await session.execute(select(Tenant).where(Tenant.uuid == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise TenantNotFoundError(str(tenant_id))
    return tenant


def _tenant_resumo(tenant: Tenant, plano: str | None) -> dict:
    return {
        "id": tenant.uuid,
        "nome": tenant.nome,
        "slug": tenant.slug,
        "status": tenant.status,
        "plano": plano,
        "criado_em": tenant.created_at,
    }


async def listar_tenants(session: AsyncSession, *, pagina: int = 1, tamanho_pagina: int = 20) -> list[dict]:
    with system_scope():
        result = await session.execute(
            select(Tenant)
            .order_by(Tenant.created_at.desc())
            .offset((pagina - 1) * tamanho_pagina)
            .limit(tamanho_pagina)
        )
        tenants = list(result.scalars().all())

        resumos = []
        for tenant in tenants:
            license_result = await session.execute(select(License).where(License.tenant_id == tenant.uuid))
            license_ = license_result.scalar_one_or_none()
            plano = await _plano_nome(session, license_.plan_id) if license_ is not None else None
            resumos.append(_tenant_resumo(tenant, plano))
        return resumos


async def metricas_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> dict:
    tenant = await _get_tenant(session, tenant_id)

    with system_scope():
        usuarios_result = await session.execute(
            select(func.count()).select_from(User).where(User.tenant_id == tenant_id, User.ativo.is_(True))
        )
        imoveis_result = await session.execute(
            select(func.count()).select_from(Imovel).where(Imovel.tenant_id == tenant_id, Imovel.ativo.is_(True))
        )
        leads_result = await session.execute(
            select(func.count()).select_from(Lead).where(Lead.tenant_id == tenant_id)
        )
        inicio_mes = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        avaliacoes_result = await session.execute(
            select(func.count())
            .select_from(Avaliacao)
            .where(Avaliacao.tenant_id == tenant_id, Avaliacao.created_at >= inicio_mes)
        )

        license_result = await session.execute(select(License).where(License.tenant_id == tenant_id))
        license_ = license_result.scalar_one_or_none()
        license_out = None
        plano = None
        if license_ is not None:
            plano = await _plano_nome(session, license_.plan_id)
            license_out = {
                "plano": plano,
                "status": license_.status.value,
                "trial_termina_em": license_.trial_termina_em,
            }

    return {
        "tenant": _tenant_resumo(tenant, plano),
        "usuarios_ativos": usuarios_result.scalar_one(),
        "imoveis_ativos": imoveis_result.scalar_one(),
        "leads_total": leads_result.scalar_one(),
        "avaliacoes_mes": avaliacoes_result.scalar_one(),
        "license": license_out,
    }


async def suspender_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    tenant = await _get_tenant(session, tenant_id)
    status_anterior = tenant.status
    tenant.status = TenantStatus.SUSPENDED
    await auditoria_service.record(
        session,
        tenant_id=tenant_id,
        ator_user_id=None,
        acao="tenant_suspenso_por_superadmin",
        entidade="tenant",
        entidade_id=str(tenant_id),
        antes={"status": status_anterior.value},
        depois={"status": TenantStatus.SUSPENDED.value},
    )
    await session.commit()


async def reativar_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    tenant = await _get_tenant(session, tenant_id)
    status_anterior = tenant.status
    tenant.status = TenantStatus.ACTIVE
    await auditoria_service.record(
        session,
        tenant_id=tenant_id,
        ator_user_id=None,
        acao="tenant_reativado_por_superadmin",
        entidade="tenant",
        entidade_id=str(tenant_id),
        antes={"status": status_anterior.value},
        depois={"status": TenantStatus.ACTIVE.value},
    )
    await session.commit()


async def uso_plataforma(session: AsyncSession) -> dict:
    with system_scope():
        status_result = await session.execute(select(Tenant.status, func.count()).group_by(Tenant.status))
        tenants_por_status = {status.value: 0 for status in TenantStatus}
        for status, contagem in status_result.all():
            tenants_por_status[status.value] = contagem

        total_usuarios = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        total_imoveis = (
            await session.execute(select(func.count()).select_from(Imovel).where(Imovel.ativo.is_(True)))
        ).scalar_one()
        total_leads = (await session.execute(select(func.count()).select_from(Lead))).scalar_one()
        total_avaliacoes = (await session.execute(select(func.count()).select_from(Avaliacao))).scalar_one()

    return {
        "tenants_por_status": tenants_por_status,
        "total_usuarios": total_usuarios,
        "total_imoveis": total_imoveis,
        "total_leads": total_leads,
        "total_avaliacoes": total_avaliacoes,
    }


async def faturamento_consolidado(session: AsyncSession) -> dict:
    hoje = date.today()
    with system_scope():
        mrr_result = await session.execute(
            select(func.coalesce(func.sum(License.preco_congelado), 0)).where(License.status == LicenseStatus.ACTIVE)
        )
        mrr = mrr_result.scalar_one()

        receita_result = await session.execute(
            select(func.coalesce(func.sum(Invoice.valor), 0)).where(
                Invoice.status == InvoiceStatus.PAID,
                Invoice.ciclo_mes == hoje.month,
                Invoice.ciclo_ano == hoje.year,
            )
        )
        receita = receita_result.scalar_one()

        status_result = await session.execute(select(Invoice.status, func.count()).group_by(Invoice.status))
        invoices_por_status = {status.value: 0 for status in InvoiceStatus}
        for status, contagem in status_result.all():
            invoices_por_status[status.value] = contagem

    return {
        "mrr": str(Decimal(mrr)),
        "receita_paga_mes_atual": str(Decimal(receita)),
        "invoices_por_status": invoices_por_status,
    }


async def listar_auditoria_cross_tenant(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None = None,
    acao: str | None = None,
    desde: date | None = None,
    ate: date | None = None,
    pagina: int = 1,
    tamanho_pagina: int = 20,
) -> list[AuditLog]:
    with system_scope():
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(AuditLog.tenant_id == tenant_id)
        if acao is not None:
            stmt = stmt.where(AuditLog.acao == acao)
        if desde is not None:
            stmt = stmt.where(AuditLog.created_at >= datetime.combine(desde, datetime.min.time(), tzinfo=timezone.utc))
        if ate is not None:
            stmt = stmt.where(AuditLog.created_at <= datetime.combine(ate, datetime.max.time(), tzinfo=timezone.utc))
        stmt = stmt.offset((pagina - 1) * tamanho_pagina).limit(tamanho_pagina)
        result = await session.execute(stmt)
        return list(result.scalars().all())
