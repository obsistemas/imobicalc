import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SuperadminUser(Base):
    """Conta do painel de plataforma (007-superadmin) — deliberadamente fora do modelo de
    tenant: sem `tenant_id`, não herda `TenantScopedMixin`, nunca aparece em query dentro de
    `tenant_scope()`. Ver specs/007-superadmin/data-model.md."""

    __tablename__ = "superadmin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
