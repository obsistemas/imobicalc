import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import require_superadmin
from app.core.security import create_superadmin_access_token
from app.database import get_session
from app.modules.superadmin import service
from app.modules.superadmin.models import SuperadminUser
from app.modules.superadmin.schemas import (
    AuditLogEntry,
    FaturamentoConsolidado,
    MetricasTenant,
    SuperadminLoginRequest,
    SuperadminTokenResponse,
    TenantResumo,
    UsoPlataforma,
)

router = APIRouter(prefix="/admin", tags=["superadmin"])


@router.post("/auth/login", response_model=SuperadminTokenResponse)
async def login(payload: SuperadminLoginRequest, session: AsyncSession = Depends(get_session)):
    try:
        superadmin = await service.authenticate(session, email=payload.email, senha=payload.senha)
    except service.InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos") from exc

    token = create_superadmin_access_token(superadmin_id=superadmin.uuid)
    return SuperadminTokenResponse(
        access_token=token, expires_in=settings.superadmin_token_expire_minutes * 60
    )


@router.get("/tenants", response_model=list[TenantResumo])
async def listar_tenants(
    pagina: int = Query(default=1, ge=1),
    tamanho_pagina: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _superadmin: SuperadminUser = Depends(require_superadmin),
):
    return await service.listar_tenants(session, pagina=pagina, tamanho_pagina=tamanho_pagina)


@router.get("/tenants/{tenant_id}/metricas", response_model=MetricasTenant)
async def metricas_tenant(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _superadmin: SuperadminUser = Depends(require_superadmin),
):
    try:
        return await service.metricas_tenant(session, tenant_id)
    except service.TenantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado") from exc


@router.post("/tenants/{tenant_id}/suspender", status_code=status.HTTP_200_OK)
async def suspender_tenant(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _superadmin: SuperadminUser = Depends(require_superadmin),
):
    try:
        await service.suspender_tenant(session, tenant_id)
    except service.TenantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado") from exc
    return {"status": "suspenso"}


@router.post("/tenants/{tenant_id}/reativar", status_code=status.HTTP_200_OK)
async def reativar_tenant(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _superadmin: SuperadminUser = Depends(require_superadmin),
):
    try:
        await service.reativar_tenant(session, tenant_id)
    except service.TenantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado") from exc
    return {"status": "ativo"}


@router.get("/uso/plataforma", response_model=UsoPlataforma)
async def uso_plataforma(
    session: AsyncSession = Depends(get_session),
    _superadmin: SuperadminUser = Depends(require_superadmin),
):
    return await service.uso_plataforma(session)


@router.get("/faturamento/consolidado", response_model=FaturamentoConsolidado)
async def faturamento_consolidado(
    session: AsyncSession = Depends(get_session),
    _superadmin: SuperadminUser = Depends(require_superadmin),
):
    return await service.faturamento_consolidado(session)


@router.get("/auditoria/logs", response_model=list[AuditLogEntry])
async def auditoria_logs(
    tenant_id: uuid.UUID | None = None,
    acao: str | None = None,
    desde: str | None = None,
    ate: str | None = None,
    pagina: int = Query(default=1, ge=1),
    session: AsyncSession = Depends(get_session),
    _superadmin: SuperadminUser = Depends(require_superadmin),
):
    from datetime import date as date_cls

    logs = await service.listar_auditoria_cross_tenant(
        session,
        tenant_id=tenant_id,
        acao=acao,
        desde=date_cls.fromisoformat(desde) if desde else None,
        ate=date_cls.fromisoformat(ate) if ate else None,
        pagina=pagina,
    )
    return [
        AuditLogEntry(
            id=log.uuid,
            tenant_id=log.tenant_id,
            ator_user_id=log.ator_user_id,
            acao=log.acao,
            entidade=log.entidade,
            entidade_id=log.entidade_id,
            created_at=log.created_at,
        )
        for log in logs
    ]
