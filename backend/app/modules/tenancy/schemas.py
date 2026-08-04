import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.modules.tenancy.models import Papel


class SignupRequest(BaseModel):
    nome_tenant: str = Field(min_length=2, max_length=200)
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str
    codigo_totp: str | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    nome: str
    email: EmailStr
    papel: Papel
    totp_enabled: bool = False
    ativo: bool
    created_at: datetime

    @classmethod
    def from_user(cls, user) -> "UserOut":
        # user.id (int) é a PK interna; user.uuid é o identificador público exposto como "id" na API.
        return cls(
            id=user.uuid,
            nome=user.nome,
            email=user.email,
            papel=user.papel,
            totp_enabled=user.totp_enabled,
            ativo=user.ativo,
            created_at=user.created_at,
        )


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class TotpSetupResponse(BaseModel):
    secret_otpauth_url: str
    qrcode_png_base64: str


class TotpVerifyRequest(BaseModel):
    codigo: str = Field(min_length=6, max_length=6)


class TotpVerifyResponse(BaseModel):
    ativado: bool
    recovery_codes: list[str]


class ConviteCreateRequest(BaseModel):
    email: EmailStr
    papel: Papel
    assistente_de_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _valida_papel(self) -> "ConviteCreateRequest":
        # 010-rbac-papeis, US6/AC1: convite nunca cria um segundo dono; assistente_de_id só
        # faz sentido (e é obrigatório) quando papel=assistente.
        if self.papel == Papel.DONO:
            raise ValueError("não é possível convidar alguém como dono")
        if self.papel == Papel.ASSISTENTE and self.assistente_de_id is None:
            raise ValueError("convite de assistente exige assistente_de_id")
        if self.papel != Papel.ASSISTENTE and self.assistente_de_id is not None:
            raise ValueError("assistente_de_id só é válido para papel=assistente")
        return self


class ConviteOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    papel: Papel
    assistente_de_id: uuid.UUID | None = None
    expires_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_convite(cls, convite) -> "ConviteOut":
        return cls(
            id=convite.uuid,
            email=convite.email,
            papel=convite.papel,
            assistente_de_id=convite.assistente_de_id,
            expires_at=convite.expires_at,
        )


class UserResumo(BaseModel):
    # "id" (não "uuid") por convenção com UserOut/ConviteOut — user.id (int) é a PK interna;
    # user.uuid é o identificador público, sempre exposto como "id" na API.
    id: uuid.UUID
    nome: str
    email: EmailStr
    papel: Papel
    assistente_de_id: uuid.UUID | None = None

    @classmethod
    def from_user(cls, user) -> "UserResumo":
        return cls(
            id=user.uuid,
            nome=user.nome,
            email=user.email,
            papel=user.papel,
            assistente_de_id=user.assistente_de_id,
        )


class AceitarConviteRequest(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    senha: str = Field(min_length=8, max_length=72)
