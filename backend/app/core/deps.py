import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import InvalidTokenError, TokenType, decode_token, decode_superadmin_token
from app.database import get_session
from app.modules.tenancy.models import Papel, TenantStatus, User


async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")

    token = auth.split(" ", 1)[1]
    try:
        payload = decode_token(token, expected_type=TokenType.ACCESS)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from exc

    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        # Token sem tenant_id não é um token de tenant válido aqui (ex.: token de superadmin,
        # RN3 de 007-superadmin — os dois mundos nunca se misturam).
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    from app.modules.tenancy import service  # import tardio evita ciclo de import

    tenant_uuid = uuid.UUID(tenant_id)
    user = await service.get_user_by_uuid(session, tenant_uuid, uuid.UUID(payload["sub"]))
    if user is None or not user.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido")

    # RN2 (007-superadmin): tenant suspenso bloqueia toda rota autenticada, independente de
    # User.ativo — checagem central aqui garante que nenhuma rota escapa dela (Artigo I).
    tenant = await service.get_tenant_by_uuid(session, tenant_uuid)
    if tenant is not None and tenant.status == TenantStatus.SUSPENDED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant suspenso")

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.papel != Papel.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apenas admin pode executar esta ação")
    return user


async def require_admin_with_2fa(user: User = Depends(require_admin)) -> User:
    if not user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ative a autenticação de dois fatores para executar esta ação",
        )
    return user


async def require_superadmin(request: Request, session: AsyncSession = Depends(get_session)):
    """Dependency paralela a `get_current_user`, nunca a mesma (RN3/007-superadmin): um token
    de tenant (mesmo `admin`) nunca passa aqui, e um token de superadmin nunca passa em
    `get_current_user`/`require_admin`."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")

    token = auth.split(" ", 1)[1]
    try:
        payload = decode_superadmin_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token não é de superadmin") from exc

    from app.modules.superadmin import service  # import tardio evita ciclo de import

    superadmin = await service.get_superadmin_by_uuid(session, uuid.UUID(payload["sub"]))
    if superadmin is None or not superadmin.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Superadmin inválido")
    return superadmin
