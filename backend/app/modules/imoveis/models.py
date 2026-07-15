import enum
import uuid as uuid_pkg
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.tenant_context import TenantScopedMixin
from app.database import Base


class ImovelTipo(str, enum.Enum):
    APARTAMENTO = "apartamento"
    CASA = "casa"
    TERRENO = "terreno"
    COMERCIAL = "comercial"
    GALPAO = "galpao"


class ImovelStatus(str, enum.Enum):
    DISPONIVEL = "disponivel"
    VENDIDO = "vendido"
    ALUGADO = "alugado"
    RESERVADO = "reservado"


class Conservacao(str, enum.Enum):
    OTIMA = "otima"
    BOA = "boa"
    REGULAR = "regular"
    RUIM = "ruim"


class Imovel(Base, TenantScopedMixin):
    __tablename__ = "imoveis"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    # Guarda User.uuid (não o id interno) — mesmo padrão de tenant_id, sem FK literal,
    # para expor diretamente no contrato sem precisar de join.
    corretor_id: Mapped[uuid_pkg.UUID] = mapped_column(index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    cep: Mapped[str] = mapped_column(String(9))
    logradouro: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bairro: Mapped[str] = mapped_column(String(120))
    cidade: Mapped[str] = mapped_column(String(120))
    estado: Mapped[str] = mapped_column(String(2))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    tipo: Mapped[ImovelTipo] = mapped_column(Enum(ImovelTipo, native_enum=False))
    area_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    area_util: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    quartos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    banheiros: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suites: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vagas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    andar: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idade_anos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conservacao: Mapped[Conservacao | None] = mapped_column(Enum(Conservacao, native_enum=False), nullable=True)
    valor_anunciado: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    status: Mapped[ImovelStatus] = mapped_column(
        Enum(ImovelStatus, native_enum=False), default=ImovelStatus.DISPONIVEL
    )
    matricula: Mapped[str | None] = mapped_column(String(50), nullable=True)
    iptu_quitado: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    escritura_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fotos: Mapped[str] = mapped_column(Text, default="[]")  # JSON: lista de URLs
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)  # soft delete
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    data_venda: Mapped[date | None] = mapped_column(Date(), nullable=True)
