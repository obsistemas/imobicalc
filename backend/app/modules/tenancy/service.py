import re
import secrets
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import emit
from app.core.security import create_access_token, hash_password, verify_password
from app.core.tenant_context import system_scope, tenant_scope
from app.modules.tenancy.models import Convite, Papel, Tenant, User
from app.modules.tenancy.schemas import AceitarConviteRequest, AuthResponse, LoginRequest, SignupRequest, UserOut


class EmailAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class ConvitePendingExistsError(Exception):
    pass


class ConviteInvalidoOuExpiradoError(Exception):
    pass


def _slugify(nome: str) -> str:
    # Remove acentos antes de reduzir a [a-z0-9-] — "Imobiliária" deve virar "imobiliaria",
    # não "imobili-ria" (subdomínio precisa ser legível, não só válido).
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-") or "tenant"
    return base


async def _email_exists(session: AsyncSession, email: str) -> bool:
    with system_scope():
        result = await session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none() is not None


async def _unique_slug(session: AsyncSession, nome: str) -> str:
    base = _slugify(nome)
    slug = base
    while True:
        result = await session.execute(select(Tenant).where(Tenant.slug == slug))
        if result.scalar_one_or_none() is None:
            return slug
        slug = f"{base}-{secrets.token_hex(2)}"


def _issue_auth_response(user: User) -> AuthResponse:
    from app.config import settings

    token = create_access_token(user_id=user.uuid, tenant_id=user.tenant_id, papel=user.papel.value)
    return AuthResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserOut.from_user(user),
    )


async def signup(session: AsyncSession, payload: SignupRequest) -> tuple[User, AuthResponse]:
    if await _email_exists(session, payload.email):
        raise EmailAlreadyExistsError(payload.email)

    slug = await _unique_slug(session, payload.nome_tenant)
    tenant = Tenant(nome=payload.nome_tenant, slug=slug)
    session.add(tenant)
    await session.flush()  # popula tenant.uuid/id sem precisar de contexto (Tenant não é tenant-scoped)

    # Comunicação entre módulos por evento de domínio (ARQUITETURA-REFERENCIA.md §1) — quem
    # cria a license em reação a isso é o módulo de licenciamento, não um import direto aqui.
    await emit("tenant_criado", session=session, tenant=tenant)

    with tenant_scope(tenant.uuid):
        admin = User(
            nome=payload.nome,
            email=payload.email,
            password_hash=hash_password(payload.senha),
            papel=Papel.ADMIN,
            tenant_id=tenant.uuid,
        )
        session.add(admin)
        await session.flush()

    await session.commit()
    return admin, _issue_auth_response(admin)


async def login(session: AsyncSession, payload: LoginRequest) -> tuple[User, AuthResponse]:
    with system_scope():
        result = await session.execute(select(User).where(User.email == payload.email, User.ativo.is_(True)))
        user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.senha, user.password_hash):
        raise InvalidCredentialsError("e-mail ou senha inválidos")

    if user.totp_enabled:
        from app.modules.tenancy.totp_service import confirm_second_factor

        if not await confirm_second_factor(session, user, payload.codigo_totp):
            raise InvalidCredentialsError("código de autenticação de dois fatores inválido ou ausente")

    return user, _issue_auth_response(user)


async def get_user_by_uuid(session: AsyncSession, tenant_id: uuid.UUID, user_uuid: uuid.UUID) -> User | None:
    with tenant_scope(tenant_id):
        result = await session.execute(select(User).where(User.uuid == user_uuid))
        return result.scalar_one_or_none()


async def create_convite(
    session: AsyncSession, *, tenant_id: uuid.UUID, criado_por: User, email: str
) -> Convite:
    if await _email_exists(session, email):
        raise EmailAlreadyExistsError(email)

    # Chamada direta ao service (não evento) porque é uma leitura síncrona que decide se a
    # requisição atual deve falhar — não uma reação assíncrona a um fato já consumado. É uma
    # checagem leve, só para UX rápida; a garantia de fato (com lock) é em aceitar_convite.
    from app.modules.licenciamento import service as licenciamento_service

    if not await licenciamento_service.ha_vaga_usuario_disponivel(session, tenant_id):
        raise licenciamento_service.SeatLimitExceededError(tenant_id)

    now = datetime.now(timezone.utc)
    with tenant_scope(tenant_id):
        result = await session.execute(select(Convite).where(Convite.email == email))
        for existente in result.scalars().all():
            if existente.pendente(now):
                raise ConvitePendingExistsError(email)

        convite = Convite(
            email=email,
            papel=Papel.CORRETOR,
            token=secrets.token_urlsafe(32),
            criado_por_id=criado_por.id,
            expires_at=now + timedelta(days=7),
            tenant_id=tenant_id,
        )
        session.add(convite)
        await session.commit()
    return convite


async def aceitar_convite(session: AsyncSession, token: str, payload: AceitarConviteRequest) -> tuple[User, AuthResponse]:
    with system_scope():
        result = await session.execute(select(Convite).where(Convite.token == token))
        convite = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if convite is None or not convite.pendente(now):
        raise ConviteInvalidoOuExpiradoError(token)

    if await _email_exists(session, convite.email):
        raise EmailAlreadyExistsError(convite.email)

    # Enforcement autoritativo (RN3) — com lock, feito aqui porque é o ponto real de INSERT
    # do User (a checagem em create_convite acima é só UX antecipada, sem lock).
    from app.modules.licenciamento import service as licenciamento_service

    await licenciamento_service.reservar_vaga_usuario(session, convite.tenant_id)

    with tenant_scope(convite.tenant_id):
        novo_user = User(
            nome=payload.nome,
            email=convite.email,
            password_hash=hash_password(payload.senha),
            papel=convite.papel,
            tenant_id=convite.tenant_id,
        )
        session.add(novo_user)
        convite.aceito_em = now
        await session.flush()

    await session.commit()
    return novo_user, _issue_auth_response(novo_user)
