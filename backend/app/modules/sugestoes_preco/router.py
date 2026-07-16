import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_session
from app.modules.avaliacoes.service import AvaliacaoNotFoundError
from app.modules.imoveis.service import ImovelNotFoundError
from app.modules.sugestoes_preco import service
from app.modules.sugestoes_preco.schemas import SugestaoPrecoCreate, SugestaoPrecoOut
from app.modules.tenancy.models import User

router = APIRouter(tags=["sugestoes-preco"])


@router.post(
    "/imoveis/{imovel_id}/avaliacoes/{avaliacao_id}/sugestoes-preco",
    response_model=SugestaoPrecoOut,
    status_code=status.HTTP_201_CREATED,
)
async def criar_sugestao_preco(
    imovel_id: uuid.UUID,
    avaliacao_id: uuid.UUID,
    payload: SugestaoPrecoCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        sugestao = await service.sugerir_preco(
            session,
            tenant_id=user.tenant_id,
            imovel_uuid=imovel_id,
            avaliacao_uuid=avaliacao_id,
            corretor=user,
            urgencia=payload.urgencia,
            observacoes=payload.observacoes,
        )
    except (ImovelNotFoundError, AvaliacaoNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avaliação não encontrada") from exc
    return SugestaoPrecoOut.from_sugestao(sugestao)


@router.get(
    "/imoveis/{imovel_id}/avaliacoes/{avaliacao_id}/sugestoes-preco",
    response_model=list[SugestaoPrecoOut],
)
async def listar_sugestoes_preco(
    imovel_id: uuid.UUID,
    avaliacao_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        sugestoes = await service.listar_sugestoes(
            session, tenant_id=user.tenant_id, imovel_uuid=imovel_id, avaliacao_uuid=avaliacao_id, user=user
        )
    except (ImovelNotFoundError, AvaliacaoNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avaliação não encontrada") from exc
    return [SugestaoPrecoOut.from_sugestao(s) for s in sugestoes]
