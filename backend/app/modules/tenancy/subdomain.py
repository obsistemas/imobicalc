from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

_CACHE_PREFIX = "tenant_by_host:"
_CACHE_TTL_SECONDS = 60


def extract_slug_from_host(host: str) -> str | None:
    """`imobiliaria-xyz.proptechavaliador.com.br:8000` -> `imobiliaria-xyz`. None se não houver subdomínio."""
    hostname = host.split(":", 1)[0].lower()
    suffix = f".{settings.platform_domain}"
    if not hostname.endswith(suffix):
        return None
    slug = hostname[: -len(suffix)]
    if not slug or "." in slug:
        return None
    return slug


async def resolve_tenant_uuid_by_host(host: str, *, session: AsyncSession, redis: Redis) -> str | None:
    """Resolve o Host header para o uuid (string) do tenant, com cache Redis. None se não encontrado."""
    slug = extract_slug_from_host(host)
    if slug is None:
        return None

    cache_key = f"{_CACHE_PREFIX}{slug}"
    cached_raw = await redis.get(cache_key)
    if cached_raw is not None:
        cached = cached_raw.decode() if isinstance(cached_raw, bytes) else cached_raw
        return cached if cached != "" else None

    from app.core.tenant_context import system_scope
    from app.modules.tenancy.models import Tenant

    with system_scope():
        result = await session.execute(select(Tenant).where(Tenant.slug == slug))
        tenant = result.scalar_one_or_none()

    await redis.set(cache_key, str(tenant.uuid) if tenant else "", ex=_CACHE_TTL_SECONDS)
    return str(tenant.uuid) if tenant else None
