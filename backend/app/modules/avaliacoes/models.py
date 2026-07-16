import enum
import uuid as uuid_pkg
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.tenant_context import TenantScopedMixin
from app.database import Base


class MetodoAvaliacao(str, enum.Enum):
    COMPARATIVO = "comparativo"
    REPRODUCAO = "reproducao"
    RENDA = "renda"


class Avaliacao(Base, TenantScopedMixin):
    """Histórico append-only (RN2/Artigo II) — nunca editada; recalcular gera uma nova linha."""

    __tablename__ = "avaliacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    # Guardam Imovel.uuid / User.uuid (não o id interno) — mesmo padrão de imoveis.corretor_id.
    imovel_id: Mapped[uuid_pkg.UUID] = mapped_column(index=True)
    corretor_id: Mapped[uuid_pkg.UUID] = mapped_column(index=True)
    metodo: Mapped[MetodoAvaliacao] = mapped_column(Enum(MetodoAvaliacao, native_enum=False))
    valor_estimado: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    valor_min: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    valor_max: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    fatores: Mapped[str] = mapped_column(Text)  # JSON — todos os inputs/intermediários (RN1)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
