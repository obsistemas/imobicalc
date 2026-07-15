import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import tenant_scope
from app.modules.auditoria.models import AuditLog


def _json(valor: dict[str, Any] | None) -> str | None:
    return None if valor is None else json.dumps(valor, default=str)


async def record(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    ator_user_id: int | None,
    acao: str,
    entidade: str,
    entidade_id: str,
    antes: dict[str, Any] | None = None,
    depois: dict[str, Any] | None = None,
) -> None:
    """Registra uma entrada de auditoria. Chamador é responsável por dar commit (a entrada
    normalmente entra na mesma transação da mudança que está sendo auditada)."""
    with tenant_scope(tenant_id):
        session.add(
            AuditLog(
                tenant_id=tenant_id,
                ator_user_id=ator_user_id,
                acao=acao,
                entidade=entidade,
                entidade_id=entidade_id,
                antes=_json(antes),
                depois=_json(depois),
            )
        )
        await session.flush()
