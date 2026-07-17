import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.redis_client import get_redis
from app.database import get_session
from app.modules.imoveis.service import ImovelNotFoundError
from app.modules.leads import service
from app.modules.leads.models import EstagioLead, OrigemLead
from app.modules.leads.schemas import LeadCreate, LeadEstagioUpdate, LeadNotaCreate, LeadNotaOut, LeadOut
from app.modules.tenancy.models import User

router = APIRouter(tags=["leads"])


@router.post("/leads", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def criar_lead(
    payload: LeadCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    try:
        lead = await service.criar_lead(session, tenant_id=user.tenant_id, corretor=user, payload=payload, redis=redis)
    except ImovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imóvel não encontrado") from exc
    return LeadOut.from_lead(lead)


@router.get("/leads/{lead_id}", response_model=LeadOut)
async def obter_lead(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        lead = await service.obter_lead(session, tenant_id=user.tenant_id, lead_uuid=lead_id, user=user)
    except service.LeadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead não encontrado") from exc
    return LeadOut.from_lead(lead)


@router.get("/leads", response_model=list[LeadOut])
async def listar_leads(
    estagio: EstagioLead | None = Query(default=None),
    origem: OrigemLead | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    leads = await service.listar_leads(session, tenant_id=user.tenant_id, user=user, estagio=estagio, origem=origem)
    return [LeadOut.from_lead(lead) for lead in leads]


@router.put("/leads/{lead_id}/estagio", response_model=LeadOut)
async def mover_estagio(
    lead_id: uuid.UUID,
    payload: LeadEstagioUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        lead = await service.mover_estagio(
            session, tenant_id=user.tenant_id, lead_uuid=lead_id, user=user, novo_estagio=payload.estagio
        )
    except service.LeadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead não encontrado") from exc
    except service.EstagioTerminalError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Lead já está em estágio terminal (fechado/perdido) — não pode ser reaberto",
        ) from exc
    return LeadOut.from_lead(lead)


@router.get("/leads/{lead_id}/notas", response_model=list[LeadNotaOut])
async def listar_notas(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        notas = await service.listar_notas(session, tenant_id=user.tenant_id, lead_uuid=lead_id, user=user)
    except service.LeadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead não encontrado") from exc
    return [LeadNotaOut.from_nota(n) for n in notas]


@router.post("/leads/{lead_id}/notas", response_model=LeadNotaOut, status_code=status.HTTP_201_CREATED)
async def adicionar_nota(
    lead_id: uuid.UUID,
    payload: LeadNotaCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        nota = await service.adicionar_nota(
            session, tenant_id=user.tenant_id, lead_uuid=lead_id, user=user, texto=payload.texto
        )
    except service.LeadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead não encontrado") from exc
    return LeadNotaOut.from_nota(nota)
