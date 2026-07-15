import json
import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.modules.imoveis.models import Conservacao, Imovel, ImovelStatus, ImovelTipo

_CEP_RE = re.compile(r"^\d{5}-?\d{3}$")


class ImovelCreate(BaseModel):
    titulo: str = Field(max_length=200)
    descricao: str | None = None
    cep: str
    bairro: str
    cidade: str
    estado: str = Field(min_length=2, max_length=2)
    tipo: ImovelTipo
    area_total: Decimal
    area_util: Decimal | None = None
    quartos: int | None = None
    banheiros: int | None = None
    suites: int | None = None
    vagas: int | None = None
    andar: int | None = None
    idade_anos: int | None = None
    conservacao: Conservacao | None = None
    valor_anunciado: Decimal | None = None
    matricula: str | None = None
    iptu_quitado: bool | None = None
    escritura_ok: bool | None = None

    @field_validator("cep")
    @classmethod
    def _valida_cep(cls, v: str) -> str:
        if not _CEP_RE.match(v):
            raise ValueError("CEP inválido — use o formato 00000-000")
        return v

    @field_validator("estado")
    @classmethod
    def _upper_estado(cls, v: str) -> str:
        return v.upper()


class ImovelUpdate(ImovelCreate):
    status: ImovelStatus | None = None


class ImovelOut(BaseModel):
    id: uuid.UUID
    corretor_id: uuid.UUID
    titulo: str
    descricao: str | None
    cep: str
    logradouro: str | None
    bairro: str
    cidade: str
    estado: str
    latitude: Decimal | None
    longitude: Decimal | None
    tipo: ImovelTipo
    area_total: Decimal
    area_util: Decimal | None
    quartos: int | None
    banheiros: int | None
    suites: int | None
    vagas: int | None
    andar: int | None
    idade_anos: int | None
    conservacao: Conservacao | None
    valor_anunciado: Decimal | None
    status: ImovelStatus
    matricula: str | None
    iptu_quitado: bool | None
    escritura_ok: bool | None
    fotos: list[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_imovel(cls, imovel: Imovel) -> "ImovelOut":
        return cls(
            id=imovel.uuid,
            corretor_id=imovel.corretor_id,
            titulo=imovel.titulo,
            descricao=imovel.descricao,
            cep=imovel.cep,
            logradouro=imovel.logradouro,
            bairro=imovel.bairro,
            cidade=imovel.cidade,
            estado=imovel.estado,
            latitude=imovel.latitude,
            longitude=imovel.longitude,
            tipo=imovel.tipo,
            area_total=imovel.area_total,
            area_util=imovel.area_util,
            quartos=imovel.quartos,
            banheiros=imovel.banheiros,
            suites=imovel.suites,
            vagas=imovel.vagas,
            andar=imovel.andar,
            idade_anos=imovel.idade_anos,
            conservacao=imovel.conservacao,
            valor_anunciado=imovel.valor_anunciado,
            status=imovel.status,
            matricula=imovel.matricula,
            iptu_quitado=imovel.iptu_quitado,
            escritura_ok=imovel.escritura_ok,
            fotos=json.loads(imovel.fotos),
            created_at=imovel.created_at,
            updated_at=imovel.updated_at,
        )


class ImovelPage(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[ImovelOut]
