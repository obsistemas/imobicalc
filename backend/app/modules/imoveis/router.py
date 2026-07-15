import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_session
from app.modules.imoveis import service
from app.modules.imoveis.models import ImovelStatus, ImovelTipo
from app.modules.imoveis.schemas import ImovelCreate, ImovelOut, ImovelPage, ImovelUpdate
from app.modules.imoveis.viacep_driver import CepLookupDriver, get_cep_driver
from app.modules.licenciamento.service import ImovelLimitExceededError
from app.modules.tenancy.models import User

router = APIRouter(tags=["imoveis"])

_LIMITE_PLANO_DETAIL = "Limite de imóveis do plano atingido — faça upgrade para cadastrar mais imóveis"


@router.post("/imoveis", response_model=ImovelOut, status_code=status.HTTP_201_CREATED)
async def criar_imovel(
    payload: ImovelCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    cep_driver: CepLookupDriver = Depends(get_cep_driver),
):
    try:
        imovel = await service.criar_imovel(
            session, tenant_id=user.tenant_id, corretor=user, payload=payload, cep_driver=cep_driver
        )
    except ImovelLimitExceededError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=_LIMITE_PLANO_DETAIL) from exc
    return ImovelOut.from_imovel(imovel)


@router.get("/imoveis", response_model=ImovelPage)
async def listar_imoveis(
    status_filtro: ImovelStatus | None = Query(default=None, alias="status"),
    tipo: ImovelTipo | None = Query(default=None),
    bairro: str | None = Query(default=None),
    cidade: str | None = Query(default=None),
    valor_min: Decimal | None = Query(default=None),
    valor_max: Decimal | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    items, total = await service.listar_imoveis(
        session,
        tenant_id=user.tenant_id,
        user=user,
        status=status_filtro,
        tipo=tipo,
        bairro=bairro,
        cidade=cidade,
        valor_min=valor_min,
        valor_max=valor_max,
        skip=skip,
        limit=limit,
    )
    return ImovelPage(total=total, skip=skip, limit=limit, items=[ImovelOut.from_imovel(i) for i in items])


@router.get("/imoveis/{imovel_id}", response_model=ImovelOut)
async def obter_imovel(
    imovel_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        imovel = await service.obter_imovel(session, tenant_id=user.tenant_id, imovel_uuid=imovel_id, user=user)
    except service.ImovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imóvel não encontrado") from exc
    return ImovelOut.from_imovel(imovel)


@router.put("/imoveis/{imovel_id}", response_model=ImovelOut)
async def atualizar_imovel(
    imovel_id: uuid.UUID,
    payload: ImovelUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        imovel = await service.atualizar_imovel(
            session, tenant_id=user.tenant_id, imovel_uuid=imovel_id, user=user, payload=payload
        )
    except service.ImovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imóvel não encontrado") from exc
    return ImovelOut.from_imovel(imovel)


@router.delete("/imoveis/{imovel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def inativar_imovel(
    imovel_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        await service.inativar_imovel(session, tenant_id=user.tenant_id, imovel_uuid=imovel_id, user=user)
    except service.ImovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imóvel não encontrado") from exc
