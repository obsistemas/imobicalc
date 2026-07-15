"""Driver pattern (ARQUITETURA-REFERENCIA.md §5): interface única para o gateway de
pagamento, com implementação real (Mercado Pago) e uma fake para dev/test — troca por config,
nunca é acoplado direto no service de licenciamento."""

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.config import settings


@dataclass(frozen=True)
class EventoPagamento:
    event_id_externo: str
    invoice_externa_id: str | None
    status: str  # "paid" | "failed" | "refunded" | "unknown"


@runtime_checkable
class PagamentoGatewayDriver(Protocol):
    def verificar_assinatura(self, payload: bytes, headers: dict[str, str]) -> bool: ...

    def extrair_evento(self, payload: dict) -> EventoPagamento: ...

    async def criar_cobranca(self, *, valor: Decimal, referencia: str) -> str:
        """Retorna o id externo da cobrança criada no gateway."""
        ...


class FakeMercadoPagoDriver:
    """Driver padrão em desenvolvimento/teste — nunca faz chamada de rede. Aceita qualquer
    assinatura e espera um payload já no formato interno simplificado
    `{"event_id": ..., "invoice_externa_id": ..., "status": ...}`."""

    def verificar_assinatura(self, payload: bytes, headers: dict[str, str]) -> bool:
        return True

    def extrair_evento(self, payload: dict) -> EventoPagamento:
        return EventoPagamento(
            event_id_externo=str(payload.get("event_id") or uuid.uuid4()),
            invoice_externa_id=payload.get("invoice_externa_id"),
            status=payload.get("status", "unknown"),
        )

    async def criar_cobranca(self, *, valor: Decimal, referencia: str) -> str:
        return f"fake-{uuid.uuid4()}"


class MercadoPagoDriver:  # pragma: no cover
    """Implementação real via SDK oficial do Mercado Pago. Não coberta por teste automatizado
    nesta feature (exigiria credenciais reais/sandbox) — estrutura pronta para a homologação
    oficial antes de produção (Artigo/METODOLOGIA §3.7)."""

    def __init__(self) -> None:
        import mercadopago

        self._sdk = mercadopago.SDK(settings.mercadopago_access_token)

    def verificar_assinatura(self, payload: bytes, headers: dict[str, str]) -> bool:
        assinatura = headers.get("x-signature", "")
        esperado = hmac.new(
            settings.mercadopago_webhook_secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(assinatura, esperado)

    def extrair_evento(self, payload: dict) -> EventoPagamento:
        data = payload.get("data", {})
        status_mp = payload.get("action", "unknown")
        status = {"payment.created": "pending", "payment.updated": "paid"}.get(status_mp, "unknown")
        return EventoPagamento(
            event_id_externo=str(payload.get("id")),
            invoice_externa_id=str(data.get("id")) if data.get("id") else None,
            status=status,
        )

    async def criar_cobranca(self, *, valor: Decimal, referencia: str) -> str:
        resultado = self._sdk.preference().create(
            {"items": [{"title": referencia, "quantity": 1, "unit_price": float(valor)}]}
        )
        return str(resultado["response"]["id"])


def get_payment_driver() -> PagamentoGatewayDriver:  # pragma: no cover
    if settings.environment == "production":
        return MercadoPagoDriver()
    return FakeMercadoPagoDriver()


__all__ = [
    "EventoPagamento",
    "FakeMercadoPagoDriver",
    "MercadoPagoDriver",
    "PagamentoGatewayDriver",
    "get_payment_driver",
]
