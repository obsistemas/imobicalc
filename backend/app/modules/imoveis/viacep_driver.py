"""Driver pattern (ARQUITETURA-REFERENCIA.md §5): interface única para a consulta de CEP,
com implementação real (ViaCEP) e uma fake para dev/test. Falha ou timeout do ViaCEP nunca
bloqueia o cadastro do imóvel — apenas deixa o logradouro vazio para preenchimento manual."""

import re
from typing import Protocol, runtime_checkable

import httpx

_VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"


def _cep_limpo(cep: str) -> str:
    return re.sub(r"\D", "", cep)


@runtime_checkable
class CepLookupDriver(Protocol):
    async def buscar_logradouro(self, cep: str) -> str | None: ...


class ViaCepDriver:
    async def buscar_logradouro(self, cep: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(_VIACEP_URL.format(cep=_cep_limpo(cep)))
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError):
            return None
        if data.get("erro"):
            return None
        return data.get("logradouro") or None


class FakeViaCepDriver:
    """Driver padrão em desenvolvimento/teste — nunca faz chamada de rede."""

    def __init__(self, respostas: dict[str, str | None] | None = None, sempre_falha: bool = False) -> None:
        self._respostas = respostas or {}
        self._sempre_falha = sempre_falha

    async def buscar_logradouro(self, cep: str) -> str | None:
        if self._sempre_falha:
            return None
        return self._respostas.get(_cep_limpo(cep))


def get_cep_driver() -> CepLookupDriver:
    from app.config import settings

    if settings.environment == "production":
        return ViaCepDriver()
    return FakeViaCepDriver()


__all__ = ["CepLookupDriver", "FakeViaCepDriver", "ViaCepDriver", "get_cep_driver"]
