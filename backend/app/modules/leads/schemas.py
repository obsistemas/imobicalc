import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.leads.models import EstagioLead, Lead, LeadNota, OrigemLead


class LeadCreate(BaseModel):
    nome: str
    email: str | None = None
    telefone: str | None = None
    origem: OrigemLead
    imovel_id: uuid.UUID | None = None


class _ExigeContato(BaseModel):
    """Mixin de validação (008-captacao-leads, RN3): diferente do LeadCreate (cadastro manual,
    onde um corretor pode ter motivo para um contato incompleto), os caminhos automáticos
    exigem ao menos telefone ou email — ninguém valida o dado ao vivo."""

    email: str | None = None
    telefone: str | None = None

    @model_validator(mode="after")
    def _telefone_ou_email(self) -> "_ExigeContato":
        if not self.email and not self.telefone:
            raise ValueError("informe ao menos telefone ou email")
        return self


class LeadPublicoCreate(_ExigeContato):
    nome: str
    imovel_id: uuid.UUID


class LeadWebhookCreate(_ExigeContato):
    nome: str
    origem: OrigemLead | None = None
    imovel_id: uuid.UUID | None = None


class LeadPortalPayload(BaseModel):
    """Formato real do webhook de leads do Grupo OLX (009-integracao-portais) — não é o mesmo
    payload do webhook genérico da 008 (LeadWebhookCreate). Campos desconhecidos são ignorados
    de propósito (a doc deles avisa que novos campos podem aparecer sem aviso prévio)."""

    model_config = ConfigDict(populate_by_name=True)

    client_listing_id: str | None = Field(default=None, alias="clientListingId")
    origin_listing_id: str | None = Field(default=None, alias="originListingId")
    origin_lead_id: str | None = Field(default=None, alias="originLeadId")
    name: str = ""
    email: str | None = None
    ddd: str | None = None
    phone: str | None = None
    message: str | None = None


class ApiKeyGerada(BaseModel):
    api_key: str
    created_at: datetime


class ApiKeyStatus(BaseModel):
    existe: bool
    created_at: datetime | None = None
    last_used_at: datetime | None = None


class LeadEstagioUpdate(BaseModel):
    estagio: EstagioLead


class LeadNotaCreate(BaseModel):
    texto: str


class LeadOut(BaseModel):
    id: uuid.UUID
    corretor_id: uuid.UUID | None
    imovel_id: uuid.UUID | None
    nome: str
    email: str | None
    telefone: str | None
    origem: OrigemLead
    estagio: EstagioLead
    created_at: datetime
    updated_at: datetime
    fechado_em: datetime | None

    @classmethod
    def from_lead(cls, lead: Lead) -> "LeadOut":
        return cls(
            id=lead.uuid,
            corretor_id=lead.corretor_id,
            imovel_id=lead.imovel_id,
            nome=lead.nome,
            email=lead.email,
            telefone=lead.telefone,
            origem=lead.origem,
            estagio=lead.estagio,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
            fechado_em=lead.fechado_em,
        )


class LeadNotaOut(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    autor_id: uuid.UUID
    texto: str
    automatica: bool
    created_at: datetime

    @classmethod
    def from_nota(cls, nota: LeadNota) -> "LeadNotaOut":
        return cls(
            id=nota.uuid,
            lead_id=nota.lead_id,
            autor_id=nota.autor_id,
            texto=nota.texto,
            automatica=nota.automatica,
            created_at=nota.created_at,
        )
