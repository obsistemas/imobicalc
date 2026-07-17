import enum
import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.tenant_context import TenantScopedMixin
from app.database import Base


class OrigemLead(str, enum.Enum):
    SITE = "site"
    INDICACAO = "indicacao"
    PORTAL = "portal"
    REDES_SOCIAIS = "redes_sociais"
    OUTRO = "outro"


class EstagioLead(str, enum.Enum):
    NOVO = "novo"
    CONTATADO = "contatado"
    VISITA = "visita"
    PROPOSTA = "proposta"
    FECHADO = "fechado"
    PERDIDO = "perdido"


ESTAGIOS_TERMINAIS = frozenset({EstagioLead.FECHADO, EstagioLead.PERDIDO})


class Lead(Base, TenantScopedMixin):
    """Registro mutável — reflete o estado atual do pipeline. Histórico fica em LeadNota."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    corretor_id: Mapped[uuid_pkg.UUID] = mapped_column(index=True)
    imovel_id: Mapped[uuid_pkg.UUID | None] = mapped_column(index=True, nullable=True)
    nome: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    origem: Mapped[OrigemLead] = mapped_column(Enum(OrigemLead, native_enum=False))
    estagio: Mapped[EstagioLead] = mapped_column(Enum(EstagioLead, native_enum=False), default=EstagioLead.NOVO)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Setado uma única vez, no momento exato da transição para FECHADO (nunca retroativo) —
    # base do tempo médio de fechamento do dashboard (005-dashboard, RN3).
    fechado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LeadNota(Base, TenantScopedMixin):
    """Histórico append-only (RN3) — nunca editada; inclui notas manuais e transições automáticas."""

    __tablename__ = "leads_notas"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    lead_id: Mapped[uuid_pkg.UUID] = mapped_column(index=True)
    autor_id: Mapped[uuid_pkg.UUID] = mapped_column(index=True)
    texto: Mapped[str] = mapped_column(Text)
    automatica: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
