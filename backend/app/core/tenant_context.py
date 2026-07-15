"""Isolamento multi-tenant (Artigo I da constituição).

Toda tabela operacional herda de `TenantScopedMixin`. Um listener de sessão aplica
automaticamente `WHERE tenant_id = :contexto` em toda leitura, e outro preenche/valida
`tenant_id` em toda escrita — nenhum código de aplicação precisa (nem pode esquecer de)
filtrar manualmente por tenant.
"""

import contextvars
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.orm import Mapped, Session, mapped_column, with_loader_criteria

current_tenant_id: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar(
    "current_tenant_id", default=None
)
_system_bypass: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "tenant_system_bypass", default=False
)


class TenantContextMissingError(RuntimeError):
    """Uma query/escrita tenant-scoped foi executada sem tenant no contexto e sem system_scope()."""


class TenantIsolationViolationError(RuntimeError):
    """Uma escrita tentou usar um tenant_id diferente do tenant do contexto ativo."""


class TenantScopedMixin:
    """Mixin para toda tabela operacional. Adiciona tenant_id e participa do isolamento automático."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)


def _as_uuid(tenant_id: uuid.UUID | str) -> uuid.UUID:
    return tenant_id if isinstance(tenant_id, uuid.UUID) else uuid.UUID(str(tenant_id))


@contextmanager
def tenant_scope(tenant_id: uuid.UUID | str) -> Iterator[None]:
    """Contexto normal de uma requisição/job autenticado: todo acesso é restrito a este tenant."""
    token = current_tenant_id.set(_as_uuid(tenant_id))
    try:
        yield
    finally:
        current_tenant_id.reset(token)


@contextmanager
def system_scope() -> Iterator[None]:
    """Bypass explícito do filtro de leitura, para jobs de sistema que iteram todos os tenants
    (ex.: dunning, reconciliação de faturas) ou consultas globais legítimas (ex.: login por
    e-mail, que ainda não sabe a qual tenant o usuário pertence). Nunca use para atender a
    uma requisição comum de usuário."""
    token = _system_bypass.set(True)
    try:
        yield
    finally:
        _system_bypass.reset(token)


def _touches_tenant_scoped_entity(statement) -> bool:
    for desc in statement.column_descriptions:
        entity = desc.get("entity")
        if isinstance(entity, type) and issubclass(entity, TenantScopedMixin):
            return True
    return False


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_read_filter(execute_state):
    # O sistema de cache de "lambda SQL" da SQLAlchemy não permite invocar funções
    # (como ContextVar.get()) de dentro do callable passado a with_loader_criteria — ele
    # tenta extrair valores literais sem executar o callable. Por isso resolvemos o
    # contexto AQUI (fora de qualquer lambda) e só então construímos um closure com o
    # valor já resolvido, como a própria mensagem de erro da SQLAlchemy recomenda.
    if not execute_state.is_select:
        return
    if execute_state.is_column_load or execute_state.is_relationship_load:
        return
    if not _touches_tenant_scoped_entity(execute_state.statement):
        return

    if _system_bypass.get():
        return

    tenant_id = current_tenant_id.get()
    if tenant_id is None:
        raise TenantContextMissingError(
            "Query tenant-scoped sem tenant no contexto (use tenant_scope() ou, para "
            "acesso deliberadamente cross-tenant, system_scope())."
        )

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantScopedMixin,
            lambda cls: cls.tenant_id == tenant_id,
            include_aliases=True,
        )
    )


@event.listens_for(Session, "before_flush")
def _autofill_and_guard_tenant_id(session, _flush_context, _instances):
    tenant_id = current_tenant_id.get()
    for obj in session.new:
        if not isinstance(obj, TenantScopedMixin):
            continue
        if obj.tenant_id is None:
            if tenant_id is None:
                raise TenantContextMissingError(
                    f"Criando {type(obj).__name__} sem tenant_id explícito e sem "
                    "tenant no contexto (use tenant_scope())."
                )
            obj.tenant_id = tenant_id
        elif tenant_id is not None and obj.tenant_id != tenant_id:
            raise TenantIsolationViolationError(
                f"Tentativa de criar {type(obj).__name__} com tenant_id={obj.tenant_id} "
                f"dentro do contexto do tenant {tenant_id}."
            )
