from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.redis_client import get_redis_singleton
from app.core.security import InvalidTokenError, TokenType, decode_token
from app.core.tenant_context import tenant_scope
from app.database import SessionLocal
from app.modules.tenancy.subdomain import resolve_tenant_uuid_by_host


class IdentifyTenantMiddleware(BaseHTTPMiddleware):
    """Resolve o tenant da requisição (Artigo I): via JWT quando autenticado, com fallback
    para o subdomínio do Host header em rotas públicas por tenant. Se nenhum dos dois resolve
    um tenant, a requisição segue sem contexto — endpoints tenant-scoped vão levantar
    TenantContextMissingError se tentarem acessar dado tenant-scoped sem um tenant identificado."""

    async def dispatch(self, request: Request, call_next) -> Response:
        tenant_uuid = await self._resolve_via_jwt(request) or await self._resolve_via_host(request)

        if tenant_uuid is None:
            return await call_next(request)

        request.state.tenant_id = tenant_uuid
        with tenant_scope(tenant_uuid):
            return await call_next(request)

    @staticmethod
    async def _resolve_via_jwt(request: Request) -> str | None:
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return None
        token = auth.split(" ", 1)[1]
        try:
            payload = decode_token(token, expected_type=TokenType.ACCESS)
        except InvalidTokenError:
            return None
        return payload.get("tenant_id")

    @staticmethod
    async def _resolve_via_host(request: Request) -> str | None:
        host = request.headers.get("host", "")
        if not host:
            return None
        async with SessionLocal() as session:
            return await resolve_tenant_uuid_by_host(host, session=session, redis=get_redis_singleton())
