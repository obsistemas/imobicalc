import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.core.redis_client import get_redis
from app.database import get_session
from app.modules.imoveis import service
from app.modules.imoveis.models import ImovelStatus, ImovelTipo
from app.modules.imoveis.schemas import ImovelCreate, ImovelOut, ImovelPage, ImovelPublico, ImovelUpdate
from app.modules.imoveis.viacep_driver import CepLookupDriver, get_cep_driver
from app.modules.imoveis.vrsync_feed import gerar_feed_vrsync
from app.modules.licenciamento.service import ImovelLimitExceededError
from app.modules.tenancy.models import User

router = APIRouter(tags=["imoveis"])

_LIMITE_PLANO_DETAIL = "Limite de imóveis do plano atingido — faça upgrade para cadastrar mais imóveis"
_IMOVEL_NAO_ENCONTRADO = "Imóvel não encontrado"
_FOTO_NAO_ENCONTRADA = "Foto não encontrada"
_TIPO_ARQUIVO_INVALIDO = "Tipo de arquivo inválido — use JPEG, PNG ou WEBP"
_ARQUIVO_MUITO_GRANDE = "Arquivo muito grande — limite de 7MB"


def _base_url(request: Request) -> str:
    """URL absoluta (scheme+host) da própria requisição — usada pra transformar as URLs
    relativas de foto (`/uploads/...`) em URLs completas, sempre relativas a quem está
    perguntando (visitante da página pública, corretor logado, feed do Grupo OLX)."""
    return f"{request.url.scheme}://{request.headers.get('host', '')}"


@router.get("/imoveis/publico/feed.xml")
async def feed_vrsync(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    imoveis = (
        await service.listar_imoveis_para_feed(session, tenant_id=uuid.UUID(str(tenant_id)))
        if tenant_id is not None
        else []
    )
    xml = gerar_feed_vrsync(
        imoveis,
        provider="Proptech Avaliador",
        email=settings.canal_pro_feed_email,
        contact_name=settings.platform_domain,
        base_url=_base_url(request),
    )
    return Response(content=xml, media_type="application/xml")


@router.get("/imoveis/publico/{imovel_id}", response_model=ImovelPublico)
async def obter_imovel_publico(
    imovel_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_IMOVEL_NAO_ENCONTRADO)
    try:
        imovel = await service.obter_imovel_publico(session, tenant_id=uuid.UUID(str(tenant_id)), imovel_uuid=imovel_id)
    except service.ImovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_IMOVEL_NAO_ENCONTRADO) from exc
    return ImovelPublico.from_imovel(imovel, base_url=_base_url(request))


@router.post("/imoveis", response_model=ImovelOut, status_code=status.HTTP_201_CREATED)
async def criar_imovel(
    payload: ImovelCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    cep_driver: CepLookupDriver = Depends(get_cep_driver),
    redis: Redis = Depends(get_redis),
):
    try:
        imovel = await service.criar_imovel(
            session, tenant_id=user.tenant_id, corretor=user, payload=payload, cep_driver=cep_driver, redis=redis
        )
    except ImovelLimitExceededError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=_LIMITE_PLANO_DETAIL) from exc
    return ImovelOut.from_imovel(imovel, base_url=_base_url(request))


@router.get("/imoveis", response_model=ImovelPage)
async def listar_imoveis(
    request: Request,
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
    base_url = _base_url(request)
    return ImovelPage(
        total=total, skip=skip, limit=limit, items=[ImovelOut.from_imovel(i, base_url=base_url) for i in items]
    )


@router.get("/imoveis/{imovel_id}", response_model=ImovelOut)
async def obter_imovel(
    imovel_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        imovel = await service.obter_imovel(session, tenant_id=user.tenant_id, imovel_uuid=imovel_id, user=user)
    except service.ImovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imóvel não encontrado") from exc
    return ImovelOut.from_imovel(imovel, base_url=_base_url(request))


@router.put("/imoveis/{imovel_id}", response_model=ImovelOut)
async def atualizar_imovel(
    imovel_id: uuid.UUID,
    payload: ImovelUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    try:
        imovel = await service.atualizar_imovel(
            session, tenant_id=user.tenant_id, imovel_uuid=imovel_id, user=user, payload=payload, redis=redis
        )
    except service.ImovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imóvel não encontrado") from exc
    return ImovelOut.from_imovel(imovel, base_url=_base_url(request))


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


@router.post("/imoveis/{imovel_id}/fotos", response_model=ImovelOut, status_code=status.HTTP_201_CREATED)
async def adicionar_foto(
    imovel_id: uuid.UUID,
    request: Request,
    arquivo: UploadFile,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    conteudo = await arquivo.read()
    try:
        imovel = await service.adicionar_foto(
            session,
            tenant_id=user.tenant_id,
            imovel_uuid=imovel_id,
            user=user,
            conteudo=conteudo,
            content_type=arquivo.content_type or "",
        )
    except service.ImovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_IMOVEL_NAO_ENCONTRADO) from exc
    except service.TipoArquivoInvalidoError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=_TIPO_ARQUIVO_INVALIDO) from exc
    except service.ArquivoMuitoGrandeError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=_ARQUIVO_MUITO_GRANDE) from exc
    return ImovelOut.from_imovel(imovel, base_url=_base_url(request))


@router.delete("/imoveis/{imovel_id}/fotos/{indice}", response_model=ImovelOut)
async def remover_foto(
    imovel_id: uuid.UUID,
    indice: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        imovel = await service.remover_foto(
            session, tenant_id=user.tenant_id, imovel_uuid=imovel_id, user=user, indice=indice
        )
    except service.ImovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_IMOVEL_NAO_ENCONTRADO) from exc
    except service.FotoNaoEncontradaError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_FOTO_NAO_ENCONTRADA) from exc
    return ImovelOut.from_imovel(imovel, base_url=_base_url(request))
