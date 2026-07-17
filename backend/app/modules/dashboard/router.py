from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_session
from app.modules.dashboard import service
from app.modules.dashboard.schemas import DashboardResumoOut, LeadOrigemOut, VendaMesOut
from app.modules.tenancy.models import User

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/resumo", response_model=DashboardResumoOut)
async def obter_resumo(
    meses: int = Query(default=12, ge=1, le=36),
    dias_sem_contato: int = Query(default=3, ge=1),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    resumo = await service.obter_resumo(
        session, tenant_id=user.tenant_id, user=user, meses=meses, dias_sem_contato=dias_sem_contato
    )
    return DashboardResumoOut(**resumo)


@router.get("/dashboard/vendas-por-mes", response_model=list[VendaMesOut])
async def obter_vendas_por_mes(
    meses: int = Query(default=12, ge=1, le=36),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    serie = await service.obter_vendas_por_mes(session, tenant_id=user.tenant_id, user=user, meses=meses)
    return [VendaMesOut(**ponto) for ponto in serie]


@router.get("/dashboard/leads-por-origem", response_model=list[LeadOrigemOut])
async def obter_leads_por_origem(
    meses: int = Query(default=12, ge=1, le=36),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    origens = await service.obter_leads_por_origem(session, tenant_id=user.tenant_id, user=user, meses=meses)
    return [LeadOrigemOut(**item) for item in origens]
