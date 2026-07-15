import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.core.redis_client import get_redis
from app.core.refresh_tokens import denylist_refresh_token, is_refresh_token_denylisted
from app.core.security import InvalidTokenError, TokenType, create_access_token, create_refresh_token, decode_token
from app.database import get_session
from app.modules.tenancy import service, totp_service
from app.modules.tenancy.cookies import REFRESH_COOKIE, set_refresh_cookie
from app.modules.tenancy.models import User
from app.modules.tenancy.schemas import (
    AuthResponse,
    LoginRequest,
    SignupRequest,
    TotpSetupResponse,
    TotpVerifyRequest,
    TotpVerifyResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, response: Response, session: AsyncSession = Depends(get_session)):
    try:
        user, auth_response = await service.signup(session, payload)
    except service.EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado") from exc

    refresh_token = create_refresh_token(user_id=user.uuid, tenant_id=user.tenant_id, papel=user.papel.value)
    set_refresh_cookie(response, refresh_token)
    return auth_response


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, response: Response, session: AsyncSession = Depends(get_session)):
    try:
        user, auth_response = await service.login(session, payload)
    except service.InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos") from exc

    refresh_token = create_refresh_token(user_id=user.uuid, tenant_id=user.tenant_id, papel=user.papel.value)
    set_refresh_cookie(response, refresh_token)
    return auth_response


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
):
    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token ausente")
    try:
        payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido") from exc

    if await is_refresh_token_denylisted(redis, jti=payload["jti"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revogado")

    tenant_id = uuid.UUID(payload["tenant_id"])
    user = await service.get_user_by_uuid(session, tenant_id, uuid.UUID(payload["sub"]))
    if user is None or not user.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido")

    await denylist_refresh_token(
        redis, jti=payload["jti"], exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    )

    new_access = create_access_token(user_id=user.uuid, tenant_id=user.tenant_id, papel=user.papel.value)
    new_refresh = create_refresh_token(user_id=user.uuid, tenant_id=user.tenant_id, papel=user.papel.value)
    set_refresh_cookie(response, new_refresh)
    return AuthResponse(
        access_token=new_access,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserOut.from_user(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    redis: Redis = Depends(get_redis),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
):
    if refresh_token is not None:
        try:
            payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
        except InvalidTokenError:
            payload = None
        if payload is not None:
            await denylist_refresh_token(
                redis, jti=payload["jti"], exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            )
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


@router.post("/2fa/setup", response_model=TotpSetupResponse)
async def totp_setup(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    otpauth_url, qrcode_png_base64 = await totp_service.setup_totp(session, user)
    return TotpSetupResponse(secret_otpauth_url=otpauth_url, qrcode_png_base64=qrcode_png_base64)


@router.post("/2fa/verify", response_model=TotpVerifyResponse)
async def totp_verify(
    payload: TotpVerifyRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        recovery_codes = await totp_service.verify_and_activate_totp(session, user, payload.codigo)
    except totp_service.InvalidTotpCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TotpVerifyResponse(ativado=True, recovery_codes=recovery_codes)
