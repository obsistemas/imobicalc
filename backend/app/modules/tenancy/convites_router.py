from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin_with_2fa
from app.core.security import create_refresh_token
from app.database import get_session
from app.modules.licenciamento.service import SeatLimitExceededError
from app.modules.tenancy import service
from app.modules.tenancy.cookies import set_refresh_cookie
from app.modules.tenancy.models import User
from app.modules.tenancy.schemas import AceitarConviteRequest, AuthResponse, ConviteCreateRequest, ConviteOut

router = APIRouter(tags=["convites"])

_LIMITE_PLANO_DETAIL = "Limite de usuários do plano atingido — faça upgrade para convidar mais gente"


@router.post("/users/convites", response_model=ConviteOut, status_code=status.HTTP_201_CREATED)
async def criar_convite(
    payload: ConviteCreateRequest,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin_with_2fa),
):
    try:
        convite = await service.create_convite(
            session, tenant_id=admin.tenant_id, criado_por=admin, email=payload.email
        )
    except service.EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado") from exc
    except service.ConvitePendingExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Já existe um convite pendente para este e-mail"
        ) from exc
    except SeatLimitExceededError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=_LIMITE_PLANO_DETAIL) from exc
    return ConviteOut.from_convite(convite)


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
