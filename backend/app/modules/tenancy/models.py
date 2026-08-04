import enum
import uuid as uuid_pkg
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.core.tenant_context import TenantScopedMixin
from app.database import Base


class TenantStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class Papel(str, enum.Enum):
    """010-rbac-papeis: `DONO` é o antigo `ADMIN` renomeado (migração de dado, mesma pessoa,
    mesmas permissões) — `GERENTE` e `ASSISTENTE` são novos. Ver specs/010-rbac-papeis/spec.md
    pela matriz de permissões e `app/core/rbac.py` pela lógica de visibilidade/exclusão."""

    DONO = "dono"
    GERENTE = "gerente"
    CORRETOR = "corretor"
    ASSISTENTE = "assistente"


class Tenant(Base):
    """Tabela central — a própria unidade de isolamento. Não carrega tenant_id: o `uuid`
    desta tabela É o valor usado como tenant_id em todas as tabelas operacionais."""

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    nome: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, native_enum=False), default=TenantStatus.TRIAL
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def trial_termina_em(self) -> datetime:
        return self.created_at + timedelta(days=settings.trial_days)


class User(Base, TenantScopedMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    # tenant_id (herdado do mixin) guarda o Tenant.uuid correspondente — ver nota em Tenant.
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    papel: Mapped[Papel] = mapped_column(Enum(Papel, native_enum=False), default=Papel.DONO)
    ativo: Mapped[bool] = mapped_column(default=True)
    # 010-rbac-papeis: uuid do corretor que este assistente atende — só populado quando
    # papel=assistente (RN3: sem vínculo, o assistente não enxerga nada, nunca "vê tudo").
    assistente_de_id: Mapped[uuid_pkg.UUID | None] = mapped_column(nullable=True)
    # Segredos criptografados em repouso (Artigo VII) — ver app/core/crypto.py.
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(default=False)
    totp_recovery_codes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: lista de hashes
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Convite(Base, TenantScopedMixin):
    __tablename__ = "convites"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    papel: Mapped[Papel] = mapped_column(Enum(Papel, native_enum=False), default=Papel.CORRETOR)
    # 010-rbac-papeis: carimbado aqui e propagado pro User quando o convite é aceito.
    assistente_de_id: Mapped[uuid_pkg.UUID | None] = mapped_column(nullable=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    criado_por_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    aceito_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def _expires_at_aware(self) -> datetime:
        # SQLite (usado nos testes) descarta tzinfo mesmo com DateTime(timezone=True);
        # Postgres (produção) preserva. Normaliza para UTC-aware nos dois casos.
        return self.expires_at if self.expires_at.tzinfo is not None else self.expires_at.replace(tzinfo=timezone.utc)

    def expirado(self, agora: datetime) -> bool:
        return self.aceito_em is None and agora >= self._expires_at_aware()

    def pendente(self, agora: datetime) -> bool:
        return self.aceito_em is None and agora < self._expires_at_aware()
