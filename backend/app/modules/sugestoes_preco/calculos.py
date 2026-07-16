"""Motor de sugestão de preço de anúncio (M5) — função pura, sem I/O (mesmo racional de
avaliacoes/calculos.py: TDD exaustivo, camada de serviço resolve os dados e só então
chama esta função). Nunca recalcula o valor de mercado — recebe valor_estimado/valor_min
já persistidos por uma avaliação existente."""

from dataclasses import dataclass, field
from decimal import Decimal

from app.modules.sugestoes_preco.models import Urgencia

_FATOR_URGENCIA = {
    Urgencia.RAPIDO: (Decimal("0.95"), Decimal("0.05")),
    Urgencia.NORMAL: (Decimal("1.00"), Decimal("0.08")),
    Urgencia.MAXIMO: (Decimal("1.08"), Decimal("0.12")),
}


class UrgenciaInvalidaError(Exception):
    pass


@dataclass(frozen=True)
class ResultadoSugestao:
    preco_anuncio_sugerido: Decimal
    valor_minimo_aceitavel: Decimal
    fatores: dict = field(default_factory=dict)


def calcular_sugestao_preco(
    *,
    valor_estimado: Decimal,
    valor_min: Decimal,
    urgencia: Urgencia,
) -> ResultadoSugestao:
    if urgencia not in _FATOR_URGENCIA:
        raise UrgenciaInvalidaError(urgencia)

    fator_urgencia, margem_negociacao = _FATOR_URGENCIA[urgencia]
    preco_anuncio_sugerido = valor_estimado * fator_urgencia
    valor_minimo_aceitavel_bruto = preco_anuncio_sugerido * (Decimal("1") - margem_negociacao)
    clamp_aplicado = valor_minimo_aceitavel_bruto < valor_min
    valor_minimo_aceitavel = max(valor_minimo_aceitavel_bruto, valor_min)

    fatores = {
        "valor_estimado_base": str(valor_estimado),
        "valor_min_base": str(valor_min),
        "urgencia": urgencia.value,
        "fator_urgencia": str(fator_urgencia),
        "margem_negociacao_pct": str(margem_negociacao),
        "valor_minimo_aceitavel_bruto": str(valor_minimo_aceitavel_bruto),
        "clamp_aplicado": clamp_aplicado,
    }
    return ResultadoSugestao(
        preco_anuncio_sugerido=preco_anuncio_sugerido,
        valor_minimo_aceitavel=valor_minimo_aceitavel,
        fatores=fatores,
    )
