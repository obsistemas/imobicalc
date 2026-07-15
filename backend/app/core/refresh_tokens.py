from datetime import datetime, timezone

from redis.asyncio import Redis

_DENYLIST_PREFIX = "refresh_denylist:"


async def denylist_refresh_token(redis: Redis, *, jti: str, exp: datetime) -> None:
    ttl_seconds = max(1, int((exp - datetime.now(timezone.utc)).total_seconds()))
    await redis.set(f"{_DENYLIST_PREFIX}{jti}", "1", ex=ttl_seconds)


async def is_refresh_token_denylisted(redis: Redis, *, jti: str) -> bool:
    return bool(await redis.exists(f"{_DENYLIST_PREFIX}{jti}"))
