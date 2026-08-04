from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_dono_com_2fa, require_gestao
from app.core.security import create_refresh_token
from app.database import get_session
from app.modules.licenciamento.service import SeatLimitExceededError
from app.modules.tenancy import service
from app.modules.tenancy.cookies import set_refresh_cookie
from app.modules.tenancy.models import User
from app.modules.tenancy.schemas import (
    AceitarConviteRequest,
    AuthResponse,
    ConviteCreateRequest,
    ConviteOut,
    UserResumo,
)

router = APIRouter(tags=["convites"])

_LIMITE_PLANO_DETAIL = "Limite de usuários do plano atingido — faça upgrade para convidar mais gente"
_ASSISTENTE_DE_INVALIDO_DETAIL = "assistente_de_id deve apontar para um corretor ativo do tenant"


@router.post("/users/convites", response_model=ConviteOut, status_code=status.HTTP_201_CREATED)
async def criar_convite(
    payload: ConviteCreateRequest,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_dono_com_2fa),
):
    try:
        convite = await service.create_convite(
            session,
            tenant_id=admin.tenant_id,
            criado_por=admin,
            email=payload.email,
            papel=payload.papel,
            assistente_de_id=payload.assistente_de_id,
        )
    except service.EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado") from exc
    except service.ConvitePendingExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Já existe um convite pendente para este e-mail"
        ) from exc
    except service.AssistenteDeInvalidoError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=_ASSISTENTE_DE_INVALIDO_DETAIL) from exc
    except SeatLimitExceededError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=_LIMITE_PLANO_DETAIL) from exc
    return ConviteOut.from_convite(convite)


@router.get("/users", response_model=list[UserResumo])
async def listar_usuarios(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_gestao),
):
    usuarios = await service.listar_usuarios(session, tenant_id=user.tenant_id)
    return [UserResumo.from_user(u) for u in usuarios]


@router.post("/convites/{token}/aceitar", response_model=AuthResponse)
async def aceitar_convite(
    token: str,
    payload: AceitarConviteRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    try:
        user, auth_response = await service.aceitar_convite(session, token, payload)
    except service.ConviteInvalidoOuExpiradoError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Convite expirado ou já utilizado") from exc
    except service.EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado") from exc
    except SeatLimitExceededError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=_LIMITE_PLANO_DETAIL) from exc

    refresh_token = create_refresh_token(user_id=user.uuid, tenant_id=user.tenant_id, papel=user.papel.value)
    set_refresh_cookie(response, refresh_token)
    return auth_response
