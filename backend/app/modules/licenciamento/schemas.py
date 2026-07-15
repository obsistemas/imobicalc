import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.modules.licenciamento.models import InvoiceStatus, LicenseStatus


class PlanOut(BaseModel):
    id: uuid.UUID
    nome: str
    max_users: int | None
    max_imoveis: int | None
    preco_mensal: Decimal

    @classmethod
    def from_plan(cls, plan) -> "PlanOut":
        return cls(
            id=plan.uuid,
            nome=plan.nome,
            max_users=plan.max_users,
            max_imoveis=plan.max_imoveis,
            preco_mensal=plan.preco_mensal,
        )


class LicenseOut(BaseModel):
    tenant_id: uuid.UUID
    plan: PlanOut
    status: LicenseStatus
    trial_termina_em: datetime | None

    @classmethod
    def from_license(cls, license_, plan) -> "LicenseOut":
        return cls(
            tenant_id=license_.tenant_id,
            plan=PlanOut.from_plan(plan),
            status=license_.status,
            trial_termina_em=license_.trial_termina_em,
        )


class UpgradeRequest(BaseModel):
    plan_id: uuid.UUID


class InvoiceOut(BaseModel):
    id: uuid.UUID
    valor: Decimal
    status: InvoiceStatus
    ciclo_mes: int
    ciclo_ano: int
    vencimento: date
    pago_em: datetime | None

    @classmethod
    def from_invoice(cls, invoice) -> "InvoiceOut":
        return cls(
            id=invoice.uuid,
            valor=invoice.valor,
            status=invoice.status,
            ciclo_mes=invoice.ciclo_mes,
            ciclo_ano=invoice.ciclo_ano,
            vencimento=invoice.vencimento,
            pago_em=invoice.pago_em,
        )
