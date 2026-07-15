import enum
import uuid as uuid_pkg
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.tenant_context import TenantScopedMixin
from app.database import Base


class LicenseStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class Plan(Base):
    """Catálogo central de planos — compartilhado entre todos os tenants, sem tenant_id."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    nome: Mapped[str] = mapped_column(String(20), unique=True)  # solo | pro | enterprise
    max_users: Mapped[int | None] = mapped_column(nullable=True)  # None = ilimitado
    max_imoveis: Mapped[int | None] = mapped_column(nullable=True)  # None = ilimitado
    preco_mensal: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class License(Base, TenantScopedMixin):
    """1 por tenant — preço congelado no momento da contratação/upgrade."""

    __tablename__ = "licenses"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_licenses_tenant_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    preco_congelado: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    status: Mapped[LicenseStatus] = mapped_column(Enum(LicenseStatus, native_enum=False), default=LicenseStatus.TRIAL)
    trial_termina_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    past_due_desde: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspensa_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Invoice(Base, TenantScopedMixin):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id"))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus, native_enum=False), default=InvoiceStatus.PENDING)
    ciclo_mes: Mapped[int] = mapped_column()
    ciclo_ano: Mapped[int] = mapped_column()
    vencimento: Mapped[date] = mapped_column(Date())
    externa_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)  # id no gateway
    pago_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaymentEvent(Base, TenantScopedMixin):
    """Append-only — garante idempotência do webhook (RN5): event_id_externo é UNIQUE."""

    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    event_id_externo: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    payload: Mapped[str] = mapped_column(Text)  # JSON
    processado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
