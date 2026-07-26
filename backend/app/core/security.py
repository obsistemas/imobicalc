import uuid
from datetime import datetime, timedelta, timezone
from enum import StrEnum

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str) -> str:
    # bcrypt aceita no máximo 72 bytes de entrada — SignupRequest.senha já limita o tamanho
    # no schema (Artigo IV: validação na borda), então o encode abaixo nunca deveria estourar.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def _create_token(
    *, subject_user_id: uuid.UUID, tenant_id: uuid.UUID, papel: str, token_type: TokenType, expires_delta: timedelta
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject_user_id),
        "tenant_id": str(tenant_id),
        "papel": papel,
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID, papel: str) -> str:
    return _create_token(
        subject_user_id=user_id,
        tenant_id=tenant_id,
        papel=papel,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID, papel: str) -> str:
    return _create_token(
        subject_user_id=user_id,
        tenant_id=tenant_id,
        papel=papel,
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


class InvalidTokenError(Exception):
    pass


def decode_token(token: str, *, expected_type: TokenType) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    if payload.get("type") != expected_type.value:
        raise InvalidTokenError(f"esperava token do tipo {expected_type.value}")
    return payload


SUPERADMIN_PAPEL = "superadmin"


def create_superadmin_access_token(*, superadmin_id: uuid.UUID) -> str:
    """Token do painel de plataforma (007-superadmin) — deliberadamente sem `tenant_id` no
    payload: é isso que o distingue de um token de tenant (RN3), não um valor sentinela."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(superadmin_id),
        "papel": SUPERADMIN_PAPEL,
        "type": TokenType.ACCESS.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.superadmin_token_expire_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_superadmin_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    if payload.get("type") != TokenType.ACCESS.value:
        raise InvalidTokenError("esperava token de acesso")
    if "tenant_id" in payload or payload.get("papel") != SUPERADMIN_PAPEL:
        raise InvalidTokenError("token não é de superadmin")
    return payload
