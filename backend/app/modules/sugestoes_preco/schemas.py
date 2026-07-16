import json
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.modules.sugestoes_preco.models import SugestaoPreco, Urgencia


class SugestaoPrecoCreate(BaseModel):
    urgencia: Urgencia
    observacoes: str | None = None


class SugestaoPrecoOut(BaseModel):
    id: uuid.UUID
    imovel_id: uuid.UUID
    avaliacao_id: uuid.UUID
    corretor_id: uuid.UUID
    urgencia: Urgencia
    preco_anuncio_sugerido: Decimal
    valor_minimo_aceitavel: Decimal
    fatores: dict
    observacoes: str | None
    created_at: datetime

    @classmethod
    def from_sugestao(cls, sugestao: SugestaoPreco) -> "SugestaoPrecoOut":
        return cls(
            id=sugestao.uuid,
            imovel_id=sugestao.imovel_id,
            avaliacao_id=sugestao.avaliacao_id,
            corretor_id=sugestao.corretor_id,
            urgencia=sugestao.urgencia,
            preco_anuncio_sugerido=sugestao.preco_anuncio_sugerido,
            valor_minimo_aceitavel=sugestao.valor_minimo_aceitavel,
            fatores=json.loads(sugestao.fatores),
            observacoes=sugestao.observacoes,
            created_at=sugestao.created_at,
        )
