from app.modules.tenancy.models import Tenant
from app.modules.tenancy.subdomain import extract_slug_from_host, resolve_tenant_uuid_by_host


def test_extract_slug_from_host_valid_subdomain():
    assert extract_slug_from_host("imobiliaria-xyz.proptechavaliador.com.br") == "imobiliaria-xyz"


def test_extract_slug_from_host_with_port():
    assert extract_slug_from_host("imobiliaria-xyz.proptechavaliador.com.br:8000") == "imobiliaria-xyz"


def test_extract_slug_from_host_bare_domain_returns_none():
    assert extract_slug_from_host("proptechavaliador.com.br") is None


def test_extract_slug_from_host_unrelated_domain_returns_none():
    assert extract_slug_from_host("testserver") is None
    assert extract_slug_from_host("example.com") is None


async def test_resolve_tenant_uuid_by_host_cache_miss_then_hit(db_session, db_sessionmaker, fake_redis):
    tenant = Tenant(nome="Imobiliária Cache", slug="imobiliaria-cache")
    db_session.add(tenant)
    await db_session.commit()

    host = "imobiliaria-cache.proptechavaliador.com.br"

    resolved = await resolve_tenant_uuid_by_host(host, session=db_session, redis=fake_redis)
    assert resolved == str(tenant.uuid)

    cached_key = "tenant_by_host:imobiliaria-cache"
    assert await fake_redis.get(cached_key) == str(tenant.uuid)

    # segunda chamada não deveria precisar tocar o banco — simulamos removendo a linha e
    # confirmando que o valor em cache ainda responde.
    await db_session.delete(tenant)
    await db_session.commit()
    resolved_again = await resolve_tenant_uuid_by_host(host, session=db_session, redis=fake_redis)
    assert resolved_again == str(tenant.uuid)


async def test_resolve_tenant_uuid_by_host_unknown_slug_returns_none_and_caches_empty(db_session, fake_redis):
    host = "nao-existe.proptechavaliador.com.br"
    resolved = await resolve_tenant_uuid_by_host(host, session=db_session, redis=fake_redis)
    assert resolved is None
    assert await fake_redis.get("tenant_by_host:nao-existe") == ""


async def test_resolve_tenant_uuid_by_host_no_subdomain_returns_none(db_session, fake_redis):
    resolved = await resolve_tenant_uuid_by_host("testserver", session=db_session, redis=fake_redis)
    assert resolved is None
