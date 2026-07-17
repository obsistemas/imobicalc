import uuid
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import emit
from app.core.tenant_context import tenant_scope
from app.modules.leads.models import ESTAGIOS_TERMINAIS, EstagioLead, Lead, LeadNota, OrigemLead
from app.modules.leads.schemas import LeadCreate
from app.modules.tenancy.models import Papel, User


class LeadNotFoundError(Exception):
    pass


class EstagioTerminalError(Exception):
    pass


def _garante_visivel(lead: Lead, user: User) -> None:
    # 404 (não 403) para não revelar a um corretor a existência de lead de outro corretor.
    if user.papel == Papel.CORRETOR and lead.corretor_id != user.uuid:
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
            corretor_id=corretor.uuid,
            imovel_id=payload.imovel_id,
            nome=payload.nome,
            email=payload.email,
            telefone=payload.telefone,
            origem=payload.origem,
        )
        session.add(lead)
        await session.flush()
        await session.commit()

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
        if user.papel == Papel.CORRETOR:
            filtros.append(Lead.corretor_id == user.uuid)
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
