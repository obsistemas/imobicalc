from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_admin
from app.core.tenant_context import tenant_scope
from app.database import get_session
from app.modules.licenciamento import service
from app.modules.licenciamento.models import Invoice
from app.modules.licenciamento.payment_driver import PagamentoGatewayDriver, get_payment_driver
from app.modules.licenciamento.schemas import InvoiceOut, LicenseOut, PlanOut, UpgradeRequest
from app.modules.tenancy.models import User

router = APIRouter(tags=["licenciamento"])


@router.get("/plans", response_model=list[PlanOut])
async def listar_planos(session: AsyncSession = Depends(get_session)):
    planos = await service.list_active_plans(session)
    return [PlanOut.from_plan(p) for p in planos]


@router.get("/license", response_model=LicenseOut)
async def obter_license(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    resultado = await service.get_license_with_plan(session, user.tenant_id)
    if resultado is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Licença não encontrada")
    license_, plan = resultado
    return LicenseOut.from_license(license_, plan)


@router.post("/license/upgrade", response_model=LicenseOut)
async def upgrade_license(
    payload: UpgradeRequest,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
):
    try:
        license_, plan = await service.upgrade_plan(
            session, tenant_id=admin.tenant_id, ator=admin, novo_plan_uuid=payload.plan_id
        )
    except service.PlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano não encontrado") from exc
    return LicenseOut.from_license(license_, plan)


@router.get("/invoices", response_model=list[InvoiceOut])
async def listar_faturas(
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
):
    with tenant_scope(admin.tenant_id):
        result = await session.execute(
            select(Invoice).where(Invoice.tenant_id == admin.tenant_id).order_by(Invoice.created_at.desc())
        )
        faturas = result.scalars().all()
    return [InvoiceOut.from_invoice(f) for f in faturas]


@router.post("/webhooks/mercadopago", status_code=status.HTTP_200_OK)
async def webhook_mercadopago(
    request: Request,
    session: AsyncSession = Depends(get_session),
    driver: PagamentoGatewayDriver = Depends(get_payment_driver),
):
    body = await request.body()
    try:
        payload_json = await request.json()
    except ValueError:
        payload_json = {}

    try:
        await service.registrar_evento_pagamento(
            session, driver=driver, payload_bytes=body, headers=dict(request.headers), payload_json=payload_json
        )
    except service.InvalidWebhookSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura inválida") from exc

    return {"status": "ok"}
