import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.redis_client import get_redis
from app.database import Base, get_session
from app.main import app

# Importa os models para que Base.metadata os conheça antes do create_all.
from app.modules.tenancy import models  # noqa: F401


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_sessionmaker(db_engine):
    return async_sessionmaker(bind=db_engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture
async def db_session(db_sessionmaker) -> AsyncSession:
    async with db_sessionmaker() as session:
        yield session


@pytest_asyncio.fixture
async def fake_redis():
    redis = FakeAsyncRedis(decode_responses=True)
    yield redis
    await redis.flushall()


@pytest_asyncio.fixture
async def client(db_sessionmaker, fake_redis):
    async def _override_get_session():
        async with db_sessionmaker() as session:
            yield session

    async def _override_get_redis():
        yield fake_redis

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_redis] = _override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver/api/v1") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_tenant_context():
    """Garante que nenhum teste vaze contexto de tenant para o próximo (contextvars são
    resetados entre tasks asyncio, mas o fixture deixa a garantia explícita e documentada)."""
    from app.core.tenant_context import current_tenant_id, _system_bypass

    yield
    current_tenant_id.set(None)
    _system_bypass.set(False)
