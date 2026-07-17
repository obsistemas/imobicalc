import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.leads.models import EstagioLead, Lead, LeadNota, OrigemLead


class LeadCreate(BaseModel):
    nome: str
    email: str | None = None
    telefone: str | None = None
    origem: OrigemLead
    imovel_id: uuid.UUID | None = None


class LeadEstagioUpdate(BaseModel):
    estagio: EstagioLead


class LeadNotaCreate(BaseModel):
    texto: str


class LeadOut(BaseModel):
    id: uuid.UUID
    corretor_id: uuid.UUID
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
