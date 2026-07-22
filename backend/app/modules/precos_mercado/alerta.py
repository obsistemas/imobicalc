"""Comparação pura (sem I/O) entre o valor anunciado de um imóvel e o preço de mercado
esperado — usada para o alerta de subprecificação (006-dados-mercado, US2). A camada de
serviço resolve o preço de mercado (com fallback, 002-avaliacao) e só então chama esta função."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AlertaSubprecificado:
    valor_esperado: Decimal
    percentual_abaixo: float


def calcular_alerta_subprecificado(
    *, valor_anunciado: Decimal, preco_m2: Decimal, area: Decimal, threshold: float
) -> AlertaSubprecificado | None:
    """Retorna o alerta quando `valor_anunciado` está `threshold` (ou mais) abaixo do esperado
    (`preco_m2 × area`); `None` quando está dentro/acima — nunca emite alerta "negativo"."""
    valor_esperado = preco_m2 * area
    if valor_esperado <= 0:
        return None

    percentual_abaixo = float((valor_esperado - valor_anunciado) / valor_esperado)
    if percentual_abaixo >= threshold:
        return AlertaSubprecificado(valor_esperado=valor_esperado, percentual_abaixo=percentual_abaixo)
    return None
