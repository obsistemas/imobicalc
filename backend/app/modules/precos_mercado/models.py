import enum
import uuid as uuid_pkg
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.modules.imoveis.models import ImovelTipo


class PadraoConstrutivo(str, enum.Enum):
    BAIXO = "baixo"
    NORMAL = "normal"
    ALTO = "alto"


class PrecoMercado(Base):
    """Catálogo central de preços de mercado (M8) — compartilhado entre tenants, sem
    tenant_id. `bairro`/`cidade` nulos representam a linha de fallback genérico por tipo."""

    __tablename__ = "preco_mercado"
    __table_args__ = (UniqueConstraint("bairro", "cidade", "tipo", name="uq_preco_mercado_bairro_cidade_tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    bairro: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True)
    tipo: Mapped[ImovelTipo] = mapped_column(Enum(ImovelTipo, native_enum=False))
    preco_m2: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    fonte: Mapped[str] = mapped_column(String(200))
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CustoConstrucaoPadrao(Base):
    """Referência central de custo de construção por padrão construtivo (tipo CUB/SINDUSCON),
    seed manual no MVP — usado só pelo método de reprodução/reposição."""

    __tablename__ = "custo_construcao_padrao"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    padrao: Mapped[PadraoConstrutivo] = mapped_column(Enum(PadraoConstrutivo, native_enum=False), unique=True)
    custo_m2: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
