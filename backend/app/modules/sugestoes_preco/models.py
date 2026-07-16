import enum
import uuid as uuid_pkg
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.tenant_context import TenantScopedMixin
from app.database import Base


class Urgencia(str, enum.Enum):
    RAPIDO = "rapido"
    NORMAL = "normal"
    MAXIMO = "maximo"


class SugestaoPreco(Base, TenantScopedMixin):
    """Histórico append-only (RN4) — nunca editada; trocar a urgência gera uma nova linha."""

    __tablename__ = "sugestoes_preco"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    # Guardam Imovel.uuid / Avaliacao.uuid / User.uuid (não o id interno) — mesmo padrão de avaliacoes.
    imovel_id: Mapped[uuid_pkg.UUID] = mapped_column(index=True)
    avaliacao_id: Mapped[uuid_pkg.UUID] = mapped_column(index=True)
    corretor_id: Mapped[uuid_pkg.UUID] = mapped_column(index=True)
    urgencia: Mapped[Urgencia] = mapped_column(Enum(Urgencia, native_enum=False))
    preco_anuncio_sugerido: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    valor_minimo_aceitavel: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    fatores: Mapped[str] = mapped_column(Text)  # JSON — inputs/intermediários (RN da spec)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
