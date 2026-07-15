import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import InvalidTokenError, TokenType, decode_token
from app.database import get_session
from app.modules.tenancy.models import Papel, User


async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")

    token = auth.split(" ", 1)[1]
    try:
        payload = decode_token(token, expected_type=TokenType.ACCESS)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from exc

    from app.modules.tenancy import service  # import tardio evita ciclo de import

    user = await service.get_user_by_uuid(session, uuid.UUID(payload["tenant_id"]), uuid.UUID(payload["sub"]))
    if user is None or not user.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido")
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
