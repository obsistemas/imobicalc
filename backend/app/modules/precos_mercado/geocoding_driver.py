"""Driver pattern (ARQUITETURA-REFERENCIA.md §5): geocodificação best-effort de bairro/cidade
para o mapa de calor (006-dados-mercado). Falha ou timeout nunca bloqueia quem chama — só deixa
latitude/longitude nulos (RN1)."""

from decimal import Decimal, InvalidOperation
from typing import Protocol, runtime_checkable

import httpx

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim exige um User-Agent identificável (política de uso do serviço público gratuito).
_USER_AGENT = "ProptechAvaliador/1.0 (https://proptechavaliador.com.br)"

Coordenada = tuple[Decimal, Decimal]


@runtime_checkable
class GeocodingDriver(Protocol):
    async def geocodificar(self, *, bairro: str, cidade: str, estado: str | None) -> Coordenada | None: ...


class NominatimGeocodingDriver:
    async def geocodificar(self, *, bairro: str, cidade: str, estado: str | None) -> Coordenada | None:
        partes = [p for p in (bairro, cidade, estado, "Brasil") if p]
        query = ", ".join(partes)
        try:
            async with httpx.AsyncClient(timeout=5.0, headers={"User-Agent": _USER_AGENT}) as client:
                resp = await client.get(_NOMINATIM_URL, params={"q": query, "format": "json", "limit": 1})
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not data:
            return None
        try:
            return Decimal(data[0]["lat"]), Decimal(data[0]["lon"])
        except (KeyError, InvalidOperation, TypeError):
            return None


class FakeGeocodingDriver:
    """Driver padrão em desenvolvimento/teste — nunca faz chamada de rede."""

    def __init__(self, respostas: dict[str, Coordenada] | None = None, sempre_falha: bool = False) -> None:
        self._respostas = respostas or {}
        self._sempre_falha = sempre_falha

    async def geocodificar(self, *, bairro: str, cidade: str, estado: str | None) -> Coordenada | None:
        if self._sempre_falha:
            return None
        return self._respostas.get(f"{bairro}|{cidade}")


def get_geocoding_driver() -> GeocodingDriver:
    from app.config import settings

    if settings.environment == "production":
        return NominatimGeocodingDriver()
    return FakeGeocodingDriver()


__all__ = ["GeocodingDriver", "FakeGeocodingDriver", "NominatimGeocodingDriver", "get_geocoding_driver"]
