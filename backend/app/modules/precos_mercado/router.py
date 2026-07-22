from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_admin
from app.database import get_session
from app.modules.precos_mercado import service
from app.modules.precos_mercado.geocoding_driver import GeocodingDriver, get_geocoding_driver
from app.modules.precos_mercado.schemas import (
    ErroImportacaoOut,
    PontoMapaCalorOut,
    PrecoMercadoCreate,
    PrecoMercadoOut,
    RelatorioImportacaoOut,
)
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
    geocoding_driver: GeocodingDriver = Depends(get_geocoding_driver),
):
    preco = await service.create_preco_mercado(session, payload, geocoding_driver=geocoding_driver)
    return PrecoMercadoOut.from_model(preco)


@router.post("/admin/precos-mercado/importar", response_model=RelatorioImportacaoOut)
async def importar_precos_mercado(
    arquivo: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
    geocoding_driver: GeocodingDriver = Depends(get_geocoding_driver),
):
    conteudo_bytes = await arquivo.read()
    conteudo = conteudo_bytes.decode("utf-8-sig")  # utf-8-sig tolera BOM de export do Excel
    relatorio = await service.importar_precos_csv(session, conteudo, geocoding_driver=geocoding_driver)
    return RelatorioImportacaoOut(
        total_linhas=relatorio.total_linhas,
        criados=relatorio.criados,
        atualizados=relatorio.atualizados,
        erros=[ErroImportacaoOut(linha=e.linha, motivo=e.motivo) for e in relatorio.erros],
    )


@router.get("/precos-mercado/mapa-calor", response_model=list[PontoMapaCalorOut])
async def obter_mapa_calor(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    pontos = await service.obter_mapa_calor(session)
    return [PontoMapaCalorOut.from_model(p) for p in pontos]
