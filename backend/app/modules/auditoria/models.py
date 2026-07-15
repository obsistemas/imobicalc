import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.tenant_context import TenantScopedMixin
from app.database import Base


class AuditLog(Base, TenantScopedMixin):
    """Trilha de auditoria (Artigo VII): append-only, nunca é atualizada nem apagada."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(unique=True, default=uuid_pkg.uuid4, index=True)
    ator_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # None = sistema (job)
    acao: Mapped[str] = mapped_column(String(100))
    entidade: Mapped[str] = mapped_column(String(50))
    entidade_id: Mapped[str] = mapped_column(String(64))
    antes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    depois: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
