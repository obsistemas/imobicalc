from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import SessionLocal
from app.health import router as health_router
from app.middleware.tenant import IdentifyTenantMiddleware
from app.modules.imoveis.router import router as imoveis_router
from app.modules.licenciamento import listeners as licenciamento_listeners  # noqa: F401  (registra @on)
from app.modules.licenciamento import service as licenciamento_service
from app.modules.licenciamento.router import router as licenciamento_router
from app.modules.tenancy.convites_router import router as convites_router
from app.modules.tenancy.router import router as tenancy_router
from app.observability import configure_logging, configure_sentry


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with SessionLocal() as session:
        await licenciamento_service.ensure_plans_seeded(session)
    yield


def create_app() -> FastAPI:
    configure_logging()
    configure_sentry()

    app = FastAPI(title="Proptech Avaliador API", version="0.1.0", lifespan=_lifespan)
    app.add_middleware(IdentifyTenantMiddleware)

    app.include_router(health_router)
    app.include_router(tenancy_router, prefix="/api/v1")
    app.include_router(convites_router, prefix="/api/v1")
    app.include_router(licenciamento_router, prefix="/api/v1")
    app.include_router(imoveis_router, prefix="/api/v1")

    return app


app = create_app()
