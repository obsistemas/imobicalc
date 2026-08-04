import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rbac
from app.core.events import emit
from app.core.tenant_context import system_scope, tenant_scope
from app.modules.leads.models import ESTAGIOS_TERMINAIS, EstagioLead, Lead, LeadNota, OrigemLead, TenantApiKey
from app.modules.leads.schemas import LeadCreate, LeadPortalPayload, LeadPublicoCreate, LeadWebhookCreate
from app.modules.tenancy.models import User


class LeadNotFoundError(Exception):
    pass


class EstagioTerminalError(Exception):
    pass


class InvalidApiKeyError(Exception):
    pass


def _hash_api_key(chave: str) -> str:
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()


def _garante_visivel(lead: Lead, user: User) -> None:
    # 404 (não 403) para não revelar a existência de lead fora do escopo de quem pergunta.
    # corretor_id=None (008-captacao-leads, RN7) é visível a qualquer um com escopo restrito.
    escopo = rbac.escopo_visibilidade(user)
    if escopo is not None and lead.corretor_id is not None and lead.corretor_id != escopo:
        raise LeadNotFoundError(lead.uuid)


async def criar_lead(
    session: AsyncSession, *, tenant_id: uuid.UUID, corretor: User, payload: LeadCreate, redis: Redis
) -> Lead:
    if payload.imovel_id is not None:
        from app.modules.imoveis.service import obter_imovel

        await obter_imovel(session, tenant_id=tenant_id, imovel_uuid=payload.imovel_id, user=corretor)

    with tenant_scope(tenant_id):
        lead = Lead(
            tenant_id=tenant_id,
            corretor_id=rbac.corretor_id_efetivo(corretor),
            imovel_id=payload.imovel_id,
            nome=payload.nome,
            email=payload.email,
            telefone=payload.telefone,
            origem=payload.origem,
        )
        session.add(lead)
        await session.flush()
        await session.commit()

    if payload.imovel_id is not None:
        from app.modules.imoveis.service import incrementar_contatos

        await incrementar_contatos(session, tenant_id=tenant_id, imovel_uuid=payload.imovel_id)

    await emit("lead_criado", tenant_id=tenant_id, redis=redis, lead=lead)
    return lead


async def criar_lead_publico(
    session: AsyncSession, *, tenant_id: uuid.UUID, payload: LeadPublicoCreate, redis: Redis
) -> Lead:
    """Formulário público de interesse (008-captacao-leads, US1) — sem corretor logado
    (`corretor_id=None`), origem sempre `site` (RF006: o visitante não escolhe a origem)."""
    from app.modules.imoveis.service import incrementar_contatos, obter_imovel_publico

    await obter_imovel_publico(session, tenant_id=tenant_id, imovel_uuid=payload.imovel_id)

    with tenant_scope(tenant_id):
        lead = Lead(
            tenant_id=tenant_id,
            corretor_id=None,
            imovel_id=payload.imovel_id,
            nome=payload.nome,
            email=payload.email,
            telefone=payload.telefone,
            origem=OrigemLead.SITE,
        )
        session.add(lead)
        await session.flush()
        await session.commit()

    await incrementar_contatos(session, tenant_id=tenant_id, imovel_uuid=payload.imovel_id)
    await emit("lead_criado", tenant_id=tenant_id, redis=redis, lead=lead)
    return lead


async def obter_lead(session: AsyncSession, *, tenant_id: uuid.UUID, lead_uuid: uuid.UUID, user: User) -> Lead:
    with tenant_scope(tenant_id):
        result = await session.execute(select(Lead).where(Lead.tenant_id == tenant_id, Lead.uuid == lead_uuid))
        lead = result.scalar_one_or_none()
    if lead is None:
        raise LeadNotFoundError(lead_uuid)
    _garante_visivel(lead, user)
    return lead


async def listar_leads(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user: User,
    estagio: EstagioLead | None = None,
    origem: OrigemLead | None = None,
) -> list[Lead]:
    with tenant_scope(tenant_id):
        filtros = [Lead.tenant_id == tenant_id]
        escopo = rbac.escopo_visibilidade(user)
        if escopo is not None:
            # corretor_id=None (008-captacao-leads, RN7) fica visível a qualquer um com escopo restrito.
            filtros.append((Lead.corretor_id == escopo) | Lead.corretor_id.is_(None))
        if estagio is not None:
            filtros.append(Lead.estagio == estagio)
        if origem is not None:
            filtros.append(Lead.origem == origem)
        result = await session.execute(select(Lead).where(*filtros).order_by(Lead.created_at.desc()))
        return list(result.scalars().all())


async def mover_estagio(
    session: AsyncSession, *, tenant_id: uuid.UUID, lead_uuid: uuid.UUID, user: User, novo_estagio: EstagioLead
) -> Lead:
    lead = await obter_lead(session, tenant_id=tenant_id, lead_uuid=lead_uuid, user=user)
    if lead.estagio in ESTAGIOS_TERMINAIS:
        raise EstagioTerminalError(lead.estagio)

    estagio_anterior = lead.estagio
    with tenant_scope(tenant_id):
        lead.estagio = novo_estagio
        if novo_estagio == EstagioLead.FECHADO:
            lead.fechado_em = datetime.now(timezone.utc)
        session.add(
            LeadNota(
                tenant_id=tenant_id,
                lead_id=lead.uuid,
                autor_id=user.uuid,
                texto=f"Estágio alterado de {estagio_anterior.value} para {novo_estagio.value}",
                automatica=True,
            )
        )
        await session.commit()
        await session.refresh(lead)
    return lead


async def adicionar_nota(
    session: AsyncSession, *, tenant_id: uuid.UUID, lead_uuid: uuid.UUID, user: User, texto: str
) -> LeadNota:
    lead = await obter_lead(session, tenant_id=tenant_id, lead_uuid=lead_uuid, user=user)
    with tenant_scope(tenant_id):
        nota = LeadNota(tenant_id=tenant_id, lead_id=lead.uuid, autor_id=user.uuid, texto=texto, automatica=False)
        session.add(nota)
        await session.flush()
        await session.commit()
    return nota


async def listar_notas(
    session: AsyncSession, *, tenant_id: uuid.UUID, lead_uuid: uuid.UUID, user: User
) -> list[LeadNota]:
    lead = await obter_lead(session, tenant_id=tenant_id, lead_uuid=lead_uuid, user=user)
    with tenant_scope(tenant_id):
        result = await session.execute(
            select(LeadNota)
            .where(LeadNota.tenant_id == tenant_id, LeadNota.lead_id == lead.uuid)
            .order_by(LeadNota.created_at.desc(), LeadNota.id.desc())
        )
        return list(result.scalars().all())


async def gerar_api_key(session: AsyncSession, *, tenant_id: uuid.UUID) -> tuple[str, datetime]:
    """Gera (ou rotaciona) a API key do tenant (008-captacao-leads, RN4/RN5). A chave em texto
    plano só existe aqui — a partir do retorno, só o hash fica salvo."""
    chave = secrets.token_urlsafe(32)
    with tenant_scope(tenant_id):
        result = await session.execute(select(TenantApiKey).where(TenantApiKey.tenant_id == tenant_id))
        existente = result.scalar_one_or_none()
        if existente is not None:
            existente.key_hash = _hash_api_key(chave)
            existente.last_used_at = None
            await session.commit()
            await session.refresh(existente)
            criada_em = existente.created_at
        else:
            nova = TenantApiKey(tenant_id=tenant_id, key_hash=_hash_api_key(chave))
            session.add(nova)
            await session.commit()
            await session.refresh(nova)
            criada_em = nova.created_at
    return chave, criada_em


async def obter_status_api_key(session: AsyncSession, *, tenant_id: uuid.UUID) -> TenantApiKey | None:
    with tenant_scope(tenant_id):
        result = await session.execute(select(TenantApiKey).where(TenantApiKey.tenant_id == tenant_id))
        return result.scalar_one_or_none()


async def criar_lead_webhook(
    session: AsyncSession, *, api_key: str, payload: LeadWebhookCreate, redis: Redis
) -> Lead:
    """Webhook público de leads (008-captacao-leads, US2) — tenant resolvido pelo hash da API
    key (`system_scope()`, mesmo racional já documentado para login por e-mail: não se sabe o
    tenant até resolver o identificador vindo do chamador)."""
    with system_scope():
        result = await session.execute(select(TenantApiKey).where(TenantApiKey.key_hash == _hash_api_key(api_key)))
        chave = result.scalar_one_or_none()
    if chave is None:
        raise InvalidApiKeyError()
    tenant_id = chave.tenant_id

    if payload.imovel_id is not None:
        from app.modules.imoveis.service import incrementar_contatos

        await incrementar_contatos(session, tenant_id=tenant_id, imovel_uuid=payload.imovel_id)

    with tenant_scope(tenant_id):
        lead = Lead(
            tenant_id=tenant_id,
            corretor_id=None,
            imovel_id=payload.imovel_id,
            nome=payload.nome,
            email=payload.email,
            telefone=payload.telefone,
            origem=payload.origem or OrigemLead.OUTRO,
        )
        session.add(lead)
        chave.last_used_at = datetime.now(timezone.utc)
        await session.flush()
        await session.commit()

    await emit("lead_criado", tenant_id=tenant_id, redis=redis, lead=lead)
    return lead


async def criar_lead_portal(session: AsyncSession, *, payload: LeadPortalPayload, redis: Redis) -> Lead | None:
    """Webhook de leads dos portais (009-integracao-portais, US2) — tenant resolvido cruzando
    `clientListingId` com `Imovel.uuid` (o mesmo valor que eu atribuo como ListingID no feed
    VRSync). Retorna None (RN5) quando não há como rotear o lead — sem `clientListingId` (leads
    MCMV, fora de escopo) ou apontando para um imóvel que não existe mais; nesses casos o
    chamador (router) ainda responde 200, para não disparar retry automático inútil."""
    if not payload.client_listing_id:
        return None
    try:
        imovel_uuid = uuid.UUID(payload.client_listing_id)
    except ValueError:
        return None

    from app.modules.imoveis.service import incrementar_contatos, obter_imovel_por_uuid_cross_tenant

    imovel = await obter_imovel_por_uuid_cross_tenant(session, imovel_uuid=imovel_uuid)
    if imovel is None:
        return None
    tenant_id = imovel.tenant_id

    telefone = f"{payload.ddd}{payload.phone}" if payload.ddd and payload.phone else payload.phone

    with tenant_scope(tenant_id):
        lead = Lead(
            tenant_id=tenant_id,
            corretor_id=None,
            imovel_id=imovel.uuid,
            nome=payload.name or "Lead do portal",
            email=payload.email,
            telefone=telefone,
            origem=OrigemLead.PORTAL,
        )
        session.add(lead)
        await session.flush()
        await session.commit()

    await incrementar_contatos(session, tenant_id=tenant_id, imovel_uuid=imovel.uuid)
    await emit("lead_criado", tenant_id=tenant_id, redis=redis, lead=lead)
    return lead
