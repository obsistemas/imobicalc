import base64
import json
import secrets
from io import BytesIO

import bcrypt
import pyotp
import qrcode
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt, encrypt
from app.modules.tenancy.models import User

_ISSUER = "Proptech Avaliador"
_RECOVERY_CODE_COUNT = 10


class InvalidTotpCodeError(Exception):
    pass


async def setup_totp(session: AsyncSession, user: User) -> tuple[str, str]:
    """Gera um novo segredo TOTP (ainda não ativado) e retorna (otpauth_url, qrcode_png_base64)."""
    secret = pyotp.random_base32()
    user.totp_secret = encrypt(secret)
    user.totp_enabled = False
    await session.commit()

    otpauth_url = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=_ISSUER)
    qr_img = qrcode.make(otpauth_url)
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")  # type: ignore[call-arg]  # stub de qrcode não cobre PilImage.save
    qrcode_png_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return otpauth_url, qrcode_png_base64


def _generate_recovery_codes() -> list[str]:
    return [secrets.token_hex(5) for _ in range(_RECOVERY_CODE_COUNT)]


def _hash_recovery_code(code: str) -> str:
    return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def verify_and_activate_totp(session: AsyncSession, user: User, codigo: str) -> list[str]:
    """Confirma o código TOTP contra o segredo pendente (setup_totp) e ativa o 2FA. Retorna
    os recovery codes em texto plano (única vez — só o hash é persistido)."""
    if not user.totp_secret:
        raise InvalidTotpCodeError("Nenhum setup de 2FA pendente para este usuário")

    secret = decrypt(user.totp_secret)
    if not pyotp.TOTP(secret).verify(codigo, valid_window=1):
        raise InvalidTotpCodeError("Código TOTP inválido")

    plain_codes = _generate_recovery_codes()
    user.totp_recovery_codes = json.dumps([_hash_recovery_code(c) for c in plain_codes])
    user.totp_enabled = True
    await session.commit()
    return plain_codes


def _verify_totp_code(user: User, codigo: str) -> bool:
    if not user.totp_secret:
        return False
    secret = decrypt(user.totp_secret)
    return pyotp.TOTP(secret).verify(codigo, valid_window=1)


def _consume_recovery_code(user: User, codigo: str) -> bool:
    if not user.totp_recovery_codes:
        return False
    hashes = json.loads(user.totp_recovery_codes)
    for hashed in hashes:
        if bcrypt.checkpw(codigo.encode("utf-8"), hashed.encode("utf-8")):
            hashes.remove(hashed)
            user.totp_recovery_codes = json.dumps(hashes)
            return True
    return False


async def confirm_second_factor(session: AsyncSession, user: User, codigo: str | None) -> bool:
    """Usado no login de usuários com 2FA ativo: aceita um código TOTP válido OU um recovery
    code (consumido — uso único). Persiste a remoção do recovery code quando usado."""
    if not codigo:
        return False
    if _verify_totp_code(user, codigo):
        return True
    if _consume_recovery_code(user, codigo):
        await session.commit()
        return True
    return False
