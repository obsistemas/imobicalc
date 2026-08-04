import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import rbac
from app.core.events import emit
from app.core.tenant_context import tenant_scope
from app.modules.imoveis.models import Imovel, ImovelStatus, ImovelTipo
from app.modules.imoveis.schemas import ImovelCreate, ImovelUpdate
from app.modules.imoveis.viacep_driver import CepLookupDriver
from app.modules.tenancy.models import User

# 009-integracao-portais: mesmo limite de tamanho documentado pelo schema VRSync (Media, 7MB).
_TIPOS_PERMITIDOS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
_TAMANHO_MAXIMO_BYTES = 7 * 1024 * 1024


class ImovelNotFoundError(Exception):
    pass


class TipoArquivoInvalidoError(Exception):
    pass


class ArquivoMuitoGrandeError(Exception):
    pass


class FotoNaoEncontradaError(Exception):
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
    imovel.finalidade = payload.finalidade


def _garante_visivel(imovel: Imovel, user: User) -> None:
    # 404 (não 403) para não revelar a existência de imóvel fora do escopo de quem pergunta
    # (010-rbac-papeis, RN2: escopo_visibilidade é o único lugar que decide isso).
    escopo = rbac.escopo_visibilidade(user)
    if escopo is not None and imovel.corretor_id != escopo:
        raise ImovelNotFoundError(imovel.uuid)


async def _verificar_e_emitir_subprecificacao(
    session: AsyncSession, *, tenant_id: uuid.UUID, imovel: Imovel, redis: Redis
) -> None:
    """Best-effort (006-dados-mercado, US2/AC2): sem valor anunciado ou sem preço de mercado
    disponível (nem fallback), simplesmente não emite alerta — nunca bloqueia o cadastro."""
    if imovel.valor_anunciado is None:
        return

    from app.config import settings
    from app.modules.precos_mercado.alerta import calcular_alerta_subprecificado
    from app.modules.precos_mercado.service import PrecoMercadoNaoEncontradoError, buscar_preco_mercado

    try:
        preco, _eh_fallback = await buscar_preco_mercado(
            session, bairro=imovel.bairro, cidade=imovel.cidade, tipo=imovel.tipo
        )
    except PrecoMercadoNaoEncontradoError:
        return

    area = imovel.area_util if imovel.area_util is not None else imovel.area_total
    alerta = calcular_alerta_subprecificado(
        valor_anunciado=imovel.valor_anunciado,
        preco_m2=preco.preco_m2,
        area=area,
        threshold=settings.subprecificado_threshold,
    )
    if alerta is None:
        return

    await emit(
        "imovel_subprecificado",
        tenant_id=tenant_id,
        redis=redis,
        imovel=imovel,
        valor_esperado=alerta.valor_esperado,
        percentual_abaixo=alerta.percentual_abaixo,
    )


async def criar_imovel(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    corretor: User,
    payload: ImovelCreate,
    cep_driver: CepLookupDriver,
    redis: Redis,
) -> Imovel:
    from app.modules.licenciamento import service as licenciamento_service

    await licenciamento_service.reservar_vaga_imovel(session, tenant_id)

    logradouro = await cep_driver.buscar_logradouro(payload.cep)

    with tenant_scope(tenant_id):
        imovel = Imovel(
            tenant_id=tenant_id, corretor_id=rbac.corretor_id_efetivo(corretor), logradouro=logradouro, fotos="[]"
        )
        _aplicar_campos(imovel, payload)
        session.add(imovel)
        await session.flush()
        await session.commit()

    await _verificar_e_emitir_subprecificacao(session, tenant_id=tenant_id, imovel=imovel, redis=redis)
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


def _url_relativa_foto(tenant_id: uuid.UUID, imovel_uuid: uuid.UUID, nome_arquivo: str) -> str:
    return f"/uploads/imoveis/{tenant_id}/{imovel_uuid}/{nome_arquivo}"


def _caminho_disco_foto(tenant_id: uuid.UUID, imovel_uuid: uuid.UUID, nome_arquivo: str) -> Path:
    return Path(settings.uploads_dir) / "imoveis" / str(tenant_id) / str(imovel_uuid) / nome_arquivo


async def adicionar_foto(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    imovel_uuid: uuid.UUID,
    user: User,
    conteudo: bytes,
    content_type: str,
) -> Imovel:
    """Upload de foto (009-integracao-portais) — grava em disco (volume Docker, sem
    dependência de storage externo, RNF009) e acrescenta a URL relativa a `Imovel.fotos`.
    Reaproveita `obter_imovel` para a mesma checagem de visibilidade do resto do módulo."""
    if content_type not in _TIPOS_PERMITIDOS:
        raise TipoArquivoInvalidoError(content_type)
    if len(conteudo) > _TAMANHO_MAXIMO_BYTES:
        raise ArquivoMuitoGrandeError(len(conteudo))

    imovel = await obter_imovel(session, tenant_id=tenant_id, imovel_uuid=imovel_uuid, user=user)

    nome_arquivo = f"{uuid.uuid4().hex}.{_TIPOS_PERMITIDOS[content_type]}"
    caminho = _caminho_disco_foto(tenant_id, imovel_uuid, nome_arquivo)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(conteudo)

    with tenant_scope(tenant_id):
        fotos = json.loads(imovel.fotos)
        fotos.append(_url_relativa_foto(tenant_id, imovel_uuid, nome_arquivo))
        imovel.fotos = json.dumps(fotos)
        await session.commit()
        await session.refresh(imovel)
    return imovel


async def remover_foto(
    session: AsyncSession, *, tenant_id: uuid.UUID, imovel_uuid: uuid.UUID, user: User, indice: int
) -> Imovel:
    imovel = await obter_imovel(session, tenant_id=tenant_id, imovel_uuid=imovel_uuid, user=user)
    fotos = json.loads(imovel.fotos)
    if indice < 0 or indice >= len(fotos):
        raise FotoNaoEncontradaError(indice)
    url_removida = fotos.pop(indice)

    caminho = Path(settings.uploads_dir) / Path(url_removida).relative_to("/uploads")
    caminho.unlink(missing_ok=True)

    with tenant_scope(tenant_id):
        imovel.fotos = json.dumps(fotos)
        await session.commit()
        await session.refresh(imovel)
    return imovel


async def obter_imovel_publico(session: AsyncSession, *, tenant_id: uuid.UUID, imovel_uuid: uuid.UUID) -> Imovel:
    """Sem `user` — página pública (008-captacao-leads), sem restrição por corretor. Só imóveis
    disponíveis e ativos aparecem (RN2); cada chamada bem-sucedida incrementa `views`."""
    with tenant_scope(tenant_id):
        result = await session.execute(
            select(Imovel).where(
                Imovel.tenant_id == tenant_id,
                Imovel.uuid == imovel_uuid,
                Imovel.ativo.is_(True),
                Imovel.status == ImovelStatus.DISPONIVEL,
            )
        )
        imovel = result.scalar_one_or_none()
        if imovel is None:
            raise ImovelNotFoundError(imovel_uuid)
        imovel.views += 1
        await session.commit()
        await session.refresh(imovel)
    return imovel


async def listar_imoveis_para_feed(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[Imovel]:
    """Imóveis publicáveis no feed VRSync (009-integracao-portais, RN2): disponível + ativo +
    finalidade definida + ao menos 1 foto — o schema VRSync exige mínimo 1 imagem por anúncio;
    sem essa checagem, o Grupo OLX rejeitaria o Listing (não o feed inteiro, mas o imóvel some
    silenciosamente do lado deles) — melhor nunca publicar um Listing que sabemos inválido."""
    with tenant_scope(tenant_id):
        result = await session.execute(
            select(Imovel).where(
                Imovel.tenant_id == tenant_id,
                Imovel.ativo.is_(True),
                Imovel.status == ImovelStatus.DISPONIVEL,
                Imovel.finalidade.is_not(None),
            )
        )
        imoveis = result.scalars().all()
        return [imovel for imovel in imoveis if json.loads(imovel.fotos)]


async def obter_imovel_por_uuid_cross_tenant(session: AsyncSession, *, imovel_uuid: uuid.UUID) -> Imovel | None:
    """Resolve um Imovel só pelo uuid, sem saber o tenant de antemão (009-integracao-portais,
    webhook de leads dos portais: o `clientListingId` é o `Imovel.uuid`, e o tenant só é
    conhecido depois de encontrar o imóvel). `system_scope()` — mesmo racional já documentado
    para consultas cross-tenant legítimas (login por e-mail, API key da 008)."""
    from app.core.tenant_context import system_scope

    with system_scope():
        result = await session.execute(select(Imovel).where(Imovel.uuid == imovel_uuid))
        return result.scalar_one_or_none()


async def incrementar_contatos(session: AsyncSession, *, tenant_id: uuid.UUID, imovel_uuid: uuid.UUID) -> None:
    """Chamado ao criar um Lead vinculado a este imóvel (manual, público ou webhook — RN6)."""
    with tenant_scope(tenant_id):
        result = await session.execute(
            select(Imovel).where(Imovel.tenant_id == tenant_id, Imovel.uuid == imovel_uuid)
        )
        imovel = result.scalar_one_or_none()
        if imovel is None:
            raise ImovelNotFoundError(imovel_uuid)
        imovel.contatos += 1
        await session.commit()


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
        escopo = rbac.escopo_visibilidade(user)
        if escopo is not None:
            filtros.append(Imovel.corretor_id == escopo)
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
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    imovel_uuid: uuid.UUID,
    user: User,
    payload: ImovelUpdate,
    redis: Redis,
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

    await _verificar_e_emitir_subprecificacao(session, tenant_id=tenant_id, imovel=imovel, redis=redis)
    return imovel


async def inativar_imovel(session: AsyncSession, *, tenant_id: uuid.UUID, imovel_uuid: uuid.UUID, user: User) -> None:
    imovel = await obter_imovel(session, tenant_id=tenant_id, imovel_uuid=imovel_uuid, user=user)
    # 010-rbac-papeis, RN4: ver/editar não implica poder excluir — checagem adicional à
    # visibilidade já garantida por obter_imovel acima (mesmo 404, não revela o motivo).
    if not rbac.pode_excluir(imovel.corretor_id, user):
        raise ImovelNotFoundError(imovel_uuid)
    with tenant_scope(tenant_id):
        imovel.ativo = False
        await session.commit()
