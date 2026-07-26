import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr

from app.modules.tenancy.models import TenantStatus


class SuperadminLoginRequest(BaseModel):
    email: EmailStr
    senha: str


class SuperadminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TenantResumo(BaseModel):
    id: uuid.UUID
    nome: str
    slug: str
    status: TenantStatus
    plano: str | None
    criado_em: datetime


class LicenseResumo(BaseModel):
    plano: str
    status: str
    trial_termina_em: datetime | None


class MetricasTenant(BaseModel):
    tenant: TenantResumo
    usuarios_ativos: int
    imoveis_ativos: int
    leads_total: int
    avaliacoes_mes: int
    license: LicenseResumo | None


class UsoPlataforma(BaseModel):
    tenants_por_status: dict[str, int]
    total_usuarios: int
    total_imoveis: int
    total_leads: int
    total_avaliacoes: int


class FaturamentoConsolidado(BaseModel):
    mrr: str
    receita_paga_mes_atual: str
    invoices_por_status: dict[str, int]


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    ator_user_id: int | None
    acao: str
    entidade: str
    entidade_id: str
    created_at: datetime


class AuditoriaFiltro(BaseModel):
    tenant_id: uuid.UUID | None = None
    acao: str | None = None
    desde: date | None = None
    ate: date | None = None
    pagina: int = 1
    tamanho_pagina: int = 20
