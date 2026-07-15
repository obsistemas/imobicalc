from cryptography.fernet import Fernet

from app.config import settings

_fernet = Fernet(settings.encryption_key.encode("utf-8"))


def encrypt(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
