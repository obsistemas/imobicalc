import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_session
from app.modules.avaliacoes import calculos, service
from app.modules.avaliacoes.schemas import AvaliacaoCreate, AvaliacaoOut
from app.modules.imoveis.service import ImovelNotFoundError
from app.modules.precos_mercado.service import CustoConstrucaoNaoEncontradoError, PrecoMercadoNaoEncontradoError
from app.modules.tenancy.models import User

router = APIRouter(tags=["avaliacoes"])

_PRECO_MERCADO_AUSENTE_DETAIL = (
    "Preço de mercado não cadastrado para esta região/tipo — cadastre em /admin/precos-mercado"
)


@router.post("/imoveis/{imovel_id}/avaliacoes", response_model=AvaliacaoOut, status_code=status.HTTP_201_CREATED)
async def criar_avaliacao(
    imovel_id: uuid.UUID,
    payload: AvaliacaoCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        avaliacao = await service.avaliar_imovel(
            session, tenant_id=user.tenant_id, imovel_uuid=imovel_id, corretor=user, payload=payload
        )
    except ImovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imóvel não encontrado") from exc
    except (PrecoMercadoNaoEncontradoError, CustoConstrucaoNaoEncontradoError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=_PRECO_MERCADO_AUSENTE_DETAIL) from exc
    except service.DadosInsuficientesError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except calculos.RendaLiquidaInvalidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Renda líquida deve ser positiva (renda bruta menos despesas operacionais)",
        ) from exc
    except calculos.TaxaCapitalizacaoInvalidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Taxa de capitalização deve ser maior que zero"
        ) from exc
    return AvaliacaoOut.from_avaliacao(avaliacao)


@router.get("/imoveis/{imovel_id}/avaliacoes", response_model=list[AvaliacaoOut])
async def listar_avaliacoes(
    imovel_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        avaliacoes = await service.listar_avaliacoes(
            session, tenant_id=user.tenant_id, imovel_uuid=imovel_id, user=user
        )
    except ImovelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imóvel não encontrado") from exc
    return [AvaliacaoOut.from_avaliacao(a) for a in avaliacoes]
