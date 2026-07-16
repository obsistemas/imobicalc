import uuid

import pytest
from sqlalchemy import select

from app.core.tenant_context import (
    TenantContextMissingError,
    TenantIsolationViolationError,
    current_tenant_id,
    system_scope,
    tenant_scope,
)
from app.modules.avaliacoes.models import Avaliacao
from app.modules.imoveis.models import Imovel
from app.modules.sugestoes_preco.models import SugestaoPreco
from app.modules.tenancy.models import Papel, User
from tests.helpers import assert_tenant_isolated


async def _create_user(session, tenant_id: uuid.UUID) -> None:
    session.add(
        User(
            nome="Corretor Teste",
            email=f"{uuid.uuid4()}@example.com",
            password_hash="hash",
            papel=Papel.CORRETOR,
        )
    )


async def test_user_isolation_between_tenants(db_sessionmaker):
    await assert_tenant_isolated(db_sessionmaker, User, _create_user)


async def _create_imovel(session, tenant_id: uuid.UUID) -> None:
    session.add(
        Imovel(
            corretor_id=uuid.uuid4(),
            titulo="Imóvel Teste",
            cep="01310-100",
            bairro="Centro",
            cidade="São Paulo",
            estado="SP",
            tipo="apartamento",
            area_total=50,
            fotos="[]",
        )
    )


async def test_imovel_isolation_between_tenants(db_sessionmaker):
    await assert_tenant_isolated(db_sessionmaker, Imovel, _create_imovel)


async def _create_avaliacao(session, tenant_id: uuid.UUID) -> None:
    session.add(
        Avaliacao(
            imovel_id=uuid.uuid4(),
            corretor_id=uuid.uuid4(),
            metodo="comparativo",
            valor_estimado="100000",
            valor_min="90000",
            valor_max="110000",
            fatores="{}",
        )
    )


async def test_avaliacao_isolation_between_tenants(db_sessionmaker):
    await assert_tenant_isolated(db_sessionmaker, Avaliacao, _create_avaliacao)


async def _create_sugestao_preco(session, tenant_id: uuid.UUID) -> None:
    session.add(
        SugestaoPreco(
            imovel_id=uuid.uuid4(),
            avaliacao_id=uuid.uuid4(),
            corretor_id=uuid.uuid4(),
            urgencia="normal",
            preco_anuncio_sugerido="100000",
            valor_minimo_aceitavel="92000",
            fatores="{}",
        )
    )


async def test_sugestao_preco_isolation_between_tenants(db_sessionmaker):
    await assert_tenant_isolated(db_sessionmaker, SugestaoPreco, _create_sugestao_preco)


async def test_query_without_tenant_context_raises(db_session):
    assert current_tenant_id.get() is None
    with pytest.raises(TenantContextMissingError):
        await db_session.execute(select(User))


async def test_insert_without_tenant_context_raises(db_session):
    db_session.add(User(nome="X", email="x@example.com", password_hash="h", papel=Papel.ADMIN))
    with pytest.raises(TenantContextMissingError):
        await db_session.flush()


async def test_insert_with_mismatched_tenant_id_raises(db_session):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    with tenant_scope(tenant_a):
        db_session.add(
            User(nome="X", email="x2@example.com", password_hash="h", papel=Papel.ADMIN, tenant_id=tenant_b)
        )
        with pytest.raises(TenantIsolationViolationError):
            await db_session.flush()


async def test_system_scope_bypasses_read_filter(db_sessionmaker):
    tenant_a = uuid.uuid4()
    async with db_sessionmaker() as session:
        with tenant_scope(tenant_a):
            session.add(
                User(nome="Y", email="y@example.com", password_hash="h", papel=Papel.ADMIN)
            )
            await session.commit()

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User))
            assert len(result.scalars().all()) == 1
