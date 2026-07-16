import json
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.modules.avaliacoes.models import Avaliacao, MetodoAvaliacao
from app.modules.precos_mercado.models import PadraoConstrutivo


class AvaliacaoCreate(BaseModel):
    metodo: MetodoAvaliacao
    # método "reproducao":
    padrao_construtivo: PadraoConstrutivo | None = None
    # método "renda":
    renda_mensal_bruta: Decimal | None = None
    despesas_operacionais_mensais: Decimal | None = None
    taxa_capitalizacao_anual: Decimal | None = None
    observacoes: str | None = None


class AvaliacaoOut(BaseModel):
    id: uuid.UUID
    imovel_id: uuid.UUID
    corretor_id: uuid.UUID
    metodo: MetodoAvaliacao
    valor_estimado: Decimal
    valor_min: Decimal
    valor_max: Decimal
    fatores: dict
    observacoes: str | None
    created_at: datetime

    @classmethod
    def from_avaliacao(cls, avaliacao: Avaliacao) -> "AvaliacaoOut":
        return cls(
            id=avaliacao.uuid,
            imovel_id=avaliacao.imovel_id,
            corretor_id=avaliacao.corretor_id,
            metodo=avaliacao.metodo,
            valor_estimado=avaliacao.valor_estimado,
            valor_min=avaliacao.valor_min,
            valor_max=avaliacao.valor_max,
            fatores=json.loads(avaliacao.fatores),
            observacoes=avaliacao.observacoes,
            created_at=avaliacao.created_at,
        )
