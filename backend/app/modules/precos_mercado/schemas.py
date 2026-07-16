import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.modules.imoveis.models import ImovelTipo


class PrecoMercadoCreate(BaseModel):
    bairro: str | None = None
    cidade: str | None = None
    estado: str | None = None
    tipo: ImovelTipo
    preco_m2: Decimal
    fonte: str


class PrecoMercadoOut(BaseModel):
    id: uuid.UUID
    bairro: str | None
    cidade: str | None
    estado: str | None
    tipo: ImovelTipo
    preco_m2: Decimal
    fonte: str
    atualizado_em: datetime

    @classmethod
    def from_model(cls, preco) -> "PrecoMercadoOut":
        return cls(
            id=preco.uuid,
            bairro=preco.bairro,
            cidade=preco.cidade,
            estado=preco.estado,
            tipo=preco.tipo,
            preco_m2=preco.preco_m2,
            fonte=preco.fonte,
            atualizado_em=preco.atualizado_em,
        )
