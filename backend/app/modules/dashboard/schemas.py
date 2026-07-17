from decimal import Decimal

from pydantic import BaseModel

from app.modules.leads.models import OrigemLead


class DashboardResumoOut(BaseModel):
    imoveis_por_status: dict[str, int]
    leads_ativos: int
    leads_sem_contato: int
    taxa_conversao: float
    ticket_medio: Decimal | None
    tempo_medio_venda_imovel_dias: float | None
    tempo_medio_fechamento_lead_dias: float | None


class VendaMesOut(BaseModel):
    ano: int
    mes: int
    quantidade: int
    valor_total: Decimal


class LeadOrigemOut(BaseModel):
    origem: OrigemLead
    quantidade: int
