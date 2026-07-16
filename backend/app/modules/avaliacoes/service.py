import json
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import tenant_scope
from app.modules.avaliacoes import calculos
from app.modules.avaliacoes.models import Avaliacao, MetodoAvaliacao
from app.modules.avaliacoes.schemas import AvaliacaoCreate
from app.modules.imoveis.models import ImovelTipo
from app.modules.imoveis.service import obter_imovel
from app.modules.precos_mercado import service as precos_service
from app.modules.tenancy.models import User

_TAXA_CAPITALIZACAO_PADRAO = Decimal("0.08")


class DadosInsuficientesError(Exception):
    pass


class AvaliacaoNotFoundError(Exception):
    pass


def _conservacao_valor(imovel) -> str | None:
    return imovel.conservacao.value if imovel.conservacao else None


async def avaliar_imovel(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    imovel_uuid: uuid.UUID,
    corretor: User,
    payload: AvaliacaoCreate,
) -> Avaliacao:
    imovel = await obter_imovel(session, tenant_id=tenant_id, imovel_uuid=imovel_uuid, user=corretor)

    if payload.metodo == MetodoAvaliacao.COMPARATIVO:
        area = imovel.area_util if imovel.area_util is not None else imovel.area_total
        preco, eh_fallback = await precos_service.buscar_preco_mercado(
            session, bairro=imovel.bairro, cidade=imovel.cidade, tipo=imovel.tipo
        )
        resultado = calculos.calcular_comparativo(
            area=area,
            preco_m2_base=preco.preco_m2,
            idade_anos=imovel.idade_anos,
            conservacao=_conservacao_valor(imovel),
            preco_eh_fallback=eh_fallback,
        )

    elif payload.metodo == MetodoAvaliacao.REPRODUCAO:
        if payload.padrao_construtivo is None:
            raise DadosInsuficientesError(
                "padrao_construtivo é obrigatório para o método de reprodução/reposição"
            )
        preco_terreno, _ = await precos_service.buscar_preco_mercado(
            session, bairro=imovel.bairro, cidade=imovel.cidade, tipo=ImovelTipo.TERRENO
        )
        custo = await precos_service.buscar_custo_construcao(session, padrao=payload.padrao_construtivo)
        area_construida = imovel.area_util if imovel.area_util is not None else imovel.area_total
        resultado = calculos.calcular_reproducao(
            area_terreno=imovel.area_total,
            preco_m2_terreno=preco_terreno.preco_m2,
            area_construida=area_construida,
            custo_m2_construcao=custo.custo_m2,
            idade_anos=imovel.idade_anos,
            conservacao=_conservacao_valor(imovel),
            tipo_imovel=imovel.tipo.value,
        )

    else:  # RENDA
        if payload.renda_mensal_bruta is None or payload.despesas_operacionais_mensais is None:
            raise DadosInsuficientesError(
                "renda_mensal_bruta e despesas_operacionais_mensais são obrigatórios para o método de renda"
            )
        taxa = (
            payload.taxa_capitalizacao_anual
            if payload.taxa_capitalizacao_anual is not None
            else _TAXA_CAPITALIZACAO_PADRAO
        )
        resultado = calculos.calcular_renda(
            renda_mensal_bruta=payload.renda_mensal_bruta,
            despesas_operacionais_mensais=payload.despesas_operacionais_mensais,
            taxa_capitalizacao_anual=taxa,
        )

    observacoes = payload.observacoes
    if resultado.observacao_automatica:
        observacoes = (
            f"{resultado.observacao_automatica}\n{observacoes}" if observacoes else resultado.observacao_automatica
        )

    with tenant_scope(tenant_id):
        avaliacao = Avaliacao(
            tenant_id=tenant_id,
            imovel_id=imovel.uuid,
            corretor_id=corretor.uuid,
            metodo=payload.metodo,
            valor_estimado=resultado.valor_estimado,
            valor_min=resultado.valor_min,
            valor_max=resultado.valor_max,
            fatores=json.dumps(resultado.fatores),
            observacoes=observacoes,
        )
        session.add(avaliacao)
        await session.flush()
        await session.commit()
    return avaliacao


async def listar_avaliacoes(
    session: AsyncSession, *, tenant_id: uuid.UUID, imovel_uuid: uuid.UUID, user: User
) -> list[Avaliacao]:
    imovel = await obter_imovel(session, tenant_id=tenant_id, imovel_uuid=imovel_uuid, user=user)
    with tenant_scope(tenant_id):
        result = await session.execute(
            select(Avaliacao)
            .where(Avaliacao.tenant_id == tenant_id, Avaliacao.imovel_id == imovel.uuid)
            .order_by(Avaliacao.created_at.desc(), Avaliacao.id.desc())
        )
        return list(result.scalars().all())


async def obter_avaliacao(
    session: AsyncSession, *, tenant_id: uuid.UUID, imovel_uuid: uuid.UUID, avaliacao_uuid: uuid.UUID, user: User
) -> Avaliacao:
    imovel = await obter_imovel(session, tenant_id=tenant_id, imovel_uuid=imovel_uuid, user=user)
    with tenant_scope(tenant_id):
        result = await session.execute(
            select(Avaliacao).where(
                Avaliacao.tenant_id == tenant_id,
                Avaliacao.imovel_id == imovel.uuid,
                Avaliacao.uuid == avaliacao_uuid,
            )
        )
        avaliacao = result.scalar_one_or_none()
    if avaliacao is None:
        raise AvaliacaoNotFoundError(avaliacao_uuid)
    return avaliacao
