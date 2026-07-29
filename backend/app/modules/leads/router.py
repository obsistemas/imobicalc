import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_admin
from app.core.redis_client import get_redis
from app.database import get_session
from app.modules.imoveis.service import ImovelNotFoundError
from app.modules.leads import service
from app.modules.leads.models import EstagioLead, OrigemLead
from app.modules.leads.schemas import (
    ApiKeyGerada,
    ApiKeyStatus,
    LeadCreate,
    LeadEstagioUpdate,
    LeadNotaCreate,
    LeadNotaOut,
    LeadOut,
    LeadPublicoCreate,
    LeadWebhookCreate,
)
from app.modules.tenancy.models import User

router = APIRouter(tags=["leads"])

_IMOVEL_NAO_ENCONTRADO = "Imóvel não encontrado"
_API_KEY_INVALIDA = "X-API-Key ausente ou inválida"


@router.post("/leads/integracao/api-key", response_model=ApiKeyGerada)
async def gerar_api_key(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    chave, criada_em = await service.gerar_api_key(session, tenant_id=user.tenant_id)
    return ApiKeyGerada(api_key=chave, created_at=criada_em)


@router.get("/leads/integracao/api-key", response_model=ApiKeyStatus)
async def status_api_key(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    chave = await service.obter_status_api_key(session, tenant_id=user.tenant_id)
    if chave is None:
        return ApiKeyStatus(existe=False)
    return ApiKeyStatus(existe=True, created_at=chave.created_at, last_used_at=chave.last_used_at)


@router.post("/leads/publico", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def criar_lead_publico(
    payload: LeadPublicoCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_IMOVEL_NAO_ENCONTRADO)
    try:
        lead = await service.criar_lead_publico(
            session, tenant_id=uuid.UUID(str(tenant_id)), payload=payload, redis=redis
        )
    except ImovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_IMOVEL_NAO_ENCONTRADO) from exc
    return LeadOut.from_lead(lead)


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


@router.post("/webhooks/leads", response_model=LeadOut, status_code=status.HTTP_201_CREATED, tags=["webhooks"])
async def criar_lead_webhook(
    payload: LeadWebhookCreate,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    x_api_key: str | None = Header(default=None),
):
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_API_KEY_INVALIDA)
    try:
        lead = await service.criar_lead_webhook(session, api_key=x_api_key, payload=payload, redis=redis)
    except service.InvalidApiKeyError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_API_KEY_INVALIDA) from exc
    except ImovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_IMOVEL_NAO_ENCONTRADO) from exc
    return LeadOut.from_lead(lead)
