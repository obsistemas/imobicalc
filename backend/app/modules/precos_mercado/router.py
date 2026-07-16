from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_admin
from app.database import get_session
from app.modules.precos_mercado import service
from app.modules.precos_mercado.schemas import PrecoMercadoCreate, PrecoMercadoOut
from app.modules.tenancy.models import User

router = APIRouter(tags=["precos-mercado"])


@router.get("/admin/precos-mercado", response_model=list[PrecoMercadoOut])
async def listar_precos_mercado(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    precos = await service.list_precos_mercado(session)
    return [PrecoMercadoOut.from_model(p) for p in precos]


@router.post("/admin/precos-mercado", response_model=PrecoMercadoOut, status_code=status.HTTP_201_CREATED)
async def criar_preco_mercado(
    payload: PrecoMercadoCreate,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
):
    preco = await service.create_preco_mercado(session, payload)
    return PrecoMercadoOut.from_model(preco)
