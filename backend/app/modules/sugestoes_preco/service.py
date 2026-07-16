import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import tenant_scope
from app.modules.avaliacoes.service import obter_avaliacao
from app.modules.sugestoes_preco import calculos
from app.modules.sugestoes_preco.models import SugestaoPreco, Urgencia
from app.modules.tenancy.models import User


async def sugerir_preco(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    imovel_uuid: uuid.UUID,
    avaliacao_uuid: uuid.UUID,
    corretor: User,
    urgencia: Urgencia,
    observacoes: str | None,
) -> SugestaoPreco:
    avaliacao = await obter_avaliacao(
        session, tenant_id=tenant_id, imovel_uuid=imovel_uuid, avaliacao_uuid=avaliacao_uuid, user=corretor
    )
    resultado = calculos.calcular_sugestao_preco(
        valor_estimado=avaliacao.valor_estimado, valor_min=avaliacao.valor_min, urgencia=urgencia
    )

    with tenant_scope(tenant_id):
        sugestao = SugestaoPreco(
            tenant_id=tenant_id,
            imovel_id=imovel_uuid,
            avaliacao_id=avaliacao.uuid,
            corretor_id=corretor.uuid,
            urgencia=urgencia,
            preco_anuncio_sugerido=resultado.preco_anuncio_sugerido,
            valor_minimo_aceitavel=resultado.valor_minimo_aceitavel,
            fatores=json.dumps(resultado.fatores),
            observacoes=observacoes,
        )
        session.add(sugestao)
        await session.flush()
        await session.commit()
    return sugestao


async def listar_sugestoes(
    session: AsyncSession, *, tenant_id: uuid.UUID, imovel_uuid: uuid.UUID, avaliacao_uuid: uuid.UUID, user: User
) -> list[SugestaoPreco]:
    avaliacao = await obter_avaliacao(
        session, tenant_id=tenant_id, imovel_uuid=imovel_uuid, avaliacao_uuid=avaliacao_uuid, user=user
    )
    with tenant_scope(tenant_id):
        result = await session.execute(
            select(SugestaoPreco)
            .where(SugestaoPreco.tenant_id == tenant_id, SugestaoPreco.avaliacao_id == avaliacao.uuid)
            .order_by(SugestaoPreco.created_at.desc(), SugestaoPreco.id.desc())
        )
        return list(result.scalars().all())
