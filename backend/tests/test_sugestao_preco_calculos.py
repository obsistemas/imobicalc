from decimal import Decimal

import pytest

from app.modules.sugestoes_preco.calculos import UrgenciaInvalidaError, calcular_sugestao_preco
from app.modules.sugestoes_preco.models import Urgencia

# --- T210: calcular_sugestao_preco --------------------------------------------------------


def test_urgencia_rapido_sugere_preco_abaixo_do_valor_estimado():
    resultado = calcular_sugestao_preco(
        valor_estimado=Decimal("500000"),
        valor_min=Decimal("450000"),
        urgencia=Urgencia.RAPIDO,
    )
    assert resultado.preco_anuncio_sugerido == Decimal("500000") * Decimal("0.95")
    assert resultado.fatores["fator_urgencia"] == "0.95"
    assert resultado.fatores["margem_negociacao_pct"] == "0.05"
    assert resultado.fatores["clamp_aplicado"] is False


def test_urgencia_normal_sugere_preco_igual_ao_valor_estimado():
    resultado = calcular_sugestao_preco(
        valor_estimado=Decimal("500000"),
        valor_min=Decimal("450000"),
        urgencia=Urgencia.NORMAL,
    )
    assert resultado.preco_anuncio_sugerido == Decimal("500000")
    margem = Decimal("0.08")
    assert resultado.valor_minimo_aceitavel == Decimal("500000") * (Decimal("1") - margem)


def test_urgencia_maximo_sugere_preco_acima_do_valor_estimado():
    resultado = calcular_sugestao_preco(
        valor_estimado=Decimal("500000"),
        valor_min=Decimal("450000"),
        urgencia=Urgencia.MAXIMO,
    )
    assert resultado.preco_anuncio_sugerido == Decimal("500000") * Decimal("1.08")
    assert resultado.fatores["margem_negociacao_pct"] == "0.12"


def test_valor_minimo_aceitavel_nunca_fica_abaixo_do_valor_min_da_avaliacao():
    # Margem de negociação de 12% (máximo) sobre um preço próximo do valor_min
    # derruba o mínimo aceitável abaixo do piso da faixa de confiança — deve ser
    # ajustado (clamp) para o próprio valor_min.
    resultado = calcular_sugestao_preco(
        valor_estimado=Decimal("100000"),
        valor_min=Decimal("96000"),
        urgencia=Urgencia.MAXIMO,
    )
    valor_minimo_bruto = Decimal("100000") * Decimal("1.08") * (Decimal("1") - Decimal("0.12"))
    assert valor_minimo_bruto < Decimal("96000")
    assert resultado.valor_minimo_aceitavel == Decimal("96000")
    assert resultado.fatores["clamp_aplicado"] is True
    assert resultado.fatores["valor_minimo_aceitavel_bruto"] == str(valor_minimo_bruto)


def test_valor_minimo_aceitavel_sem_clamp_quando_acima_do_valor_min():
    resultado = calcular_sugestao_preco(
        valor_estimado=Decimal("500000"),
        valor_min=Decimal("100000"),
        urgencia=Urgencia.NORMAL,
    )
    valor_minimo_bruto = Decimal("500000") * (Decimal("1") - Decimal("0.08"))
    assert resultado.fatores["clamp_aplicado"] is False
    assert resultado.valor_minimo_aceitavel == valor_minimo_bruto


def test_fatores_registram_valores_base_da_avaliacao():
    resultado = calcular_sugestao_preco(
        valor_estimado=Decimal("500000"),
        valor_min=Decimal("450000"),
        urgencia=Urgencia.NORMAL,
    )
    assert resultado.fatores["valor_estimado_base"] == "500000"
    assert resultado.fatores["valor_min_base"] == "450000"
    assert resultado.fatores["urgencia"] == "normal"


def test_urgencia_desconhecida_levanta_erro():
    with pytest.raises(UrgenciaInvalidaError):
        calcular_sugestao_preco(
            valor_estimado=Decimal("500000"),
            valor_min=Decimal("450000"),
            urgencia="inexistente",
        )
