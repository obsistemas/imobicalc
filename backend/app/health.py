from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.database import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck(session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)):
    database_ok = True
    redis_ok = True

    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        database_ok = False

    try:
        await redis.ping()
    except Exception:
        redis_ok = False

    status_str = "ok" if database_ok and redis_ok else "degraded"
    return {"status": status_str, "database": database_ok, "redis": redis_ok}
