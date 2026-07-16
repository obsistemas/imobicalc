from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.imoveis.models import ImovelTipo
from app.modules.precos_mercado.models import CustoConstrucaoPadrao, PadraoConstrutivo, PrecoMercado
from app.modules.precos_mercado.schemas import PrecoMercadoCreate

# Fallback genérico nacional por tipo (RN3/US5 AC3) — curadoria inicial, admin substitui/complementa
# por região conforme dado real fica disponível (fonte documentada para reprodutibilidade).
_FONTE_SEED_INICIAL = "seed inicial (curadoria genérica nacional, v0.2.0)"

PRECO_MERCADO_FALLBACK_SEED: list[dict[str, Any]] = [
    {"tipo": ImovelTipo.APARTAMENTO, "preco_m2": Decimal("6000.0000")},
    {"tipo": ImovelTipo.CASA, "preco_m2": Decimal("4000.0000")},
    {"tipo": ImovelTipo.TERRENO, "preco_m2": Decimal("800.0000")},
    {"tipo": ImovelTipo.COMERCIAL, "preco_m2": Decimal("5000.0000")},
    {"tipo": ImovelTipo.GALPAO, "preco_m2": Decimal("2000.0000")},
]

CUSTO_CONSTRUCAO_SEED: list[dict[str, Any]] = [
    {"padrao": PadraoConstrutivo.BAIXO, "custo_m2": Decimal("1500.0000")},
    {"padrao": PadraoConstrutivo.NORMAL, "custo_m2": Decimal("2200.0000")},
    {"padrao": PadraoConstrutivo.ALTO, "custo_m2": Decimal("3500.0000")},
]


class PrecoMercadoNaoEncontradoError(Exception):
    pass


class CustoConstrucaoNaoEncontradoError(Exception):
    pass


async def ensure_precos_mercado_seeded(session: AsyncSession) -> None:
    result = await session.execute(select(func.count()).select_from(PrecoMercado))
    if result.scalar_one() > 0:
        return
    for dados in PRECO_MERCADO_FALLBACK_SEED:
        session.add(PrecoMercado(bairro=None, cidade=None, estado=None, fonte=_FONTE_SEED_INICIAL, **dados))
    await session.commit()


async def ensure_custo_construcao_seeded(session: AsyncSession) -> None:
    result = await session.execute(select(func.count()).select_from(CustoConstrucaoPadrao))
    if result.scalar_one() > 0:
        return
    for dados in CUSTO_CONSTRUCAO_SEED:
        session.add(CustoConstrucaoPadrao(**dados))
    await session.commit()


async def list_precos_mercado(session: AsyncSession) -> list[PrecoMercado]:
    result = await session.execute(select(PrecoMercado).order_by(PrecoMercado.cidade, PrecoMercado.bairro))
    return list(result.scalars().all())


async def create_preco_mercado(session: AsyncSession, payload: PrecoMercadoCreate) -> PrecoMercado:
    preco = PrecoMercado(
        bairro=payload.bairro,
        cidade=payload.cidade,
        estado=payload.estado,
        tipo=payload.tipo,
        preco_m2=payload.preco_m2,
        fonte=payload.fonte,
    )
    session.add(preco)
    await session.commit()
    return preco


async def buscar_preco_mercado(
    session: AsyncSession, *, bairro: str, cidade: str, tipo: ImovelTipo
) -> tuple[PrecoMercado, bool]:
    """Busca preço específico (bairro+cidade+tipo); cai para o genérico do tipo (RN3) —
    nunca calcula com valor arbitrário. Retorna (preco, eh_fallback)."""
    result = await session.execute(
        select(PrecoMercado).where(
            PrecoMercado.bairro == bairro, PrecoMercado.cidade == cidade, PrecoMercado.tipo == tipo
        )
    )
    preco = result.scalar_one_or_none()
    if preco is not None:
        return preco, False

    result = await session.execute(
        select(PrecoMercado).where(
            PrecoMercado.bairro.is_(None), PrecoMercado.cidade.is_(None), PrecoMercado.tipo == tipo
        )
    )
    preco = result.scalar_one_or_none()
    if preco is not None:
        return preco, True

    raise PrecoMercadoNaoEncontradoError(tipo)


async def buscar_custo_construcao(session: AsyncSession, *, padrao: PadraoConstrutivo) -> CustoConstrucaoPadrao:
    result = await session.execute(select(CustoConstrucaoPadrao).where(CustoConstrucaoPadrao.padrao == padrao))
    custo = result.scalar_one_or_none()
    if custo is None:
        raise CustoConstrucaoNaoEncontradoError(padrao)
    return custo
