import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.tenant_context import tenant_scope


async def assert_tenant_isolated(
    sessionmaker: async_sessionmaker,
    model_cls: type,
    create_row: Callable[[AsyncSession, uuid.UUID], Awaitable[None]],
) -> None:
    """Cria uma linha de `model_cls` para o tenant A (via `create_row`) e garante que uma
    query do mesmo model, executada no contexto do tenant B, nunca a retorna. Gate de CI
    obrigatório (Artigo I) para todo recurso tenant-scoped novo."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    async with sessionmaker() as session:
        with tenant_scope(tenant_a):
            await create_row(session, tenant_a)
            await session.commit()

    async with sessionmaker() as session:
        with tenant_scope(tenant_b):
            result = await session.execute(select(model_cls))
            rows = result.scalars().all()
            assert rows == [], (
                f"Isolamento violado: tenant B enxergou {len(rows)} linha(s) de "
                f"{model_cls.__name__} pertencentes ao tenant A"
            )

    async with sessionmaker() as session:
        with tenant_scope(tenant_a):
            result = await session.execute(select(model_cls))
            rows = result.scalars().all()
            assert len(rows) == 1, "a própria linha do tenant A deveria ser visível para o tenant A"
