import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import tenant_scope
from app.modules.imoveis.models import Imovel, ImovelStatus, ImovelTipo
from app.modules.imoveis.schemas import ImovelCreate, ImovelUpdate
from app.modules.imoveis.viacep_driver import CepLookupDriver
from app.modules.tenancy.models import Papel, User


class ImovelNotFoundError(Exception):
    pass


def _aplicar_campos(imovel: Imovel, payload: ImovelCreate) -> None:
    imovel.titulo = payload.titulo
    imovel.descricao = payload.descricao
    imovel.cep = payload.cep
    imovel.bairro = payload.bairro
    imovel.cidade = payload.cidade
    imovel.estado = payload.estado
    imovel.tipo = payload.tipo
    imovel.area_total = payload.area_total
    imovel.area_util = payload.area_util
    imovel.quartos = payload.quartos
    imovel.banheiros = payload.banheiros
    imovel.suites = payload.suites
    imovel.vagas = payload.vagas
    imovel.andar = payload.andar
    imovel.idade_anos = payload.idade_anos
    imovel.conservacao = payload.conservacao
    imovel.valor_anunciado = payload.valor_anunciado
    imovel.matricula = payload.matricula
    imovel.iptu_quitado = payload.iptu_quitado
    imovel.escritura_ok = payload.escritura_ok


def _garante_visivel(imovel: Imovel, user: User) -> None:
    # 404 (não 403) para não revelar a um corretor a existência de imóvel de outro corretor.
    if user.papel == Papel.CORRETOR and imovel.corretor_id != user.uuid:
        raise ImovelNotFoundError(imovel.uuid)


async def criar_imovel(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    corretor: User,
    payload: ImovelCreate,
    cep_driver: CepLookupDriver,
) -> Imovel:
    from app.modules.licenciamento import service as licenciamento_service

    await licenciamento_service.reservar_vaga_imovel(session, tenant_id)

    logradouro = await cep_driver.buscar_logradouro(payload.cep)

    with tenant_scope(tenant_id):
        imovel = Imovel(tenant_id=tenant_id, corretor_id=corretor.uuid, logradouro=logradouro, fotos="[]")
        _aplicar_campos(imovel, payload)
        session.add(imovel)
        await session.flush()
        await session.commit()
    return imovel


async def obter_imovel(session: AsyncSession, *, tenant_id: uuid.UUID, imovel_uuid: uuid.UUID, user: User) -> Imovel:
    with tenant_scope(tenant_id):
        result = await session.execute(
            select(Imovel).where(
                Imovel.tenant_id == tenant_id, Imovel.uuid == imovel_uuid, Imovel.ativo.is_(True)
            )
        )
        imovel = result.scalar_one_or_none()
    if imovel is None:
        raise ImovelNotFoundError(imovel_uuid)
    _garante_visivel(imovel, user)
    return imovel


async def listar_imoveis(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user: User,
    status: ImovelStatus | None = None,
    tipo: ImovelTipo | None = None,
    bairro: str | None = None,
    cidade: str | None = None,
    valor_min: Decimal | None = None,
    valor_max: Decimal | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Imovel], int]:
    with tenant_scope(tenant_id):
        filtros = [Imovel.tenant_id == tenant_id, Imovel.ativo.is_(True)]
        if user.papel == Papel.CORRETOR:
            filtros.append(Imovel.corretor_id == user.uuid)
        if status is not None:
            filtros.append(Imovel.status == status)
        if tipo is not None:
            filtros.append(Imovel.tipo == tipo)
        if bairro is not None:
            filtros.append(Imovel.bairro == bairro)
        if cidade is not None:
            filtros.append(Imovel.cidade == cidade)
        if valor_min is not None:
            filtros.append(Imovel.valor_anunciado >= valor_min)
        if valor_max is not None:
            filtros.append(Imovel.valor_anunciado <= valor_max)

        total = (await session.execute(select(func.count()).select_from(Imovel).where(*filtros))).scalar_one()
        result = await session.execute(
            select(Imovel).where(*filtros).order_by(Imovel.created_at.desc()).offset(skip).limit(limit)
        )
        items = list(result.scalars().all())
    return items, total


async def atualizar_imovel(
    session: AsyncSession, *, tenant_id: uuid.UUID, imovel_uuid: uuid.UUID, user: User, payload: ImovelUpdate
) -> Imovel:
    imovel = await obter_imovel(session, tenant_id=tenant_id, imovel_uuid=imovel_uuid, user=user)
    with tenant_scope(tenant_id):
        _aplicar_campos(imovel, payload)
        if payload.status is not None:
            # Setado uma única vez, no momento exato da transição para VENDIDO (nunca
            # retroativo) — base das métricas de vendas do dashboard (005-dashboard).
            # Usa data UTC explícita (não date.today(), que usa fuso local do servidor e
            # pode ficar um dia "atrasada" em relação a created_at, gerado em UTC — causaria
            # tempo_medio_venda_imovel_dias negativo em servidores fora de UTC).
            if payload.status == ImovelStatus.VENDIDO and imovel.data_venda is None:
                imovel.data_venda = datetime.now(timezone.utc).date()
            imovel.status = payload.status
        await session.commit()
        await session.refresh(imovel)
    return imovel


async def inativar_imovel(session: AsyncSession, *, tenant_id: uuid.UUID, imovel_uuid: uuid.UUID, user: User) -> None:
    imovel = await obter_imovel(session, tenant_id=tenant_id, imovel_uuid=imovel_uuid, user=user)
    with tenant_scope(tenant_id):
        imovel.ativo = False
        await session.commit()
