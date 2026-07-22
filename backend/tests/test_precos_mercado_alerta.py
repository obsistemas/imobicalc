from decimal import Decimal

from app.modules.precos_mercado.alerta import calcular_alerta_subprecificado

# --- T521: calcular_alerta_subprecificado (função pura) -------------------------------------


def test_valor_abaixo_do_threshold_gera_alerta():
    # esperado: 5000 * 100 = 500.000; anunciado 400.000 -> 20% abaixo (threshold 15%)
    alerta = calcular_alerta_subprecificado(
        valor_anunciado=Decimal("400000"), preco_m2=Decimal("5000"), area=Decimal("100"), threshold=0.15
    )
    assert alerta is not None
    assert alerta.valor_esperado == Decimal("500000")
    assert round(alerta.percentual_abaixo, 2) == 0.20


def test_valor_exatamente_no_threshold_gera_alerta():
    # 15% abaixo exatamente de 500.000 = 425.000
    alerta = calcular_alerta_subprecificado(
        valor_anunciado=Decimal("425000"), preco_m2=Decimal("5000"), area=Decimal("100"), threshold=0.15
    )
    assert alerta is not None


def test_valor_dentro_do_esperado_nao_gera_alerta():
    alerta = calcular_alerta_subprecificado(
        valor_anunciado=Decimal("490000"), preco_m2=Decimal("5000"), area=Decimal("100"), threshold=0.15
    )
    assert alerta is None


def test_valor_acima_do_esperado_nao_gera_alerta():
    alerta = calcular_alerta_subprecificado(
        valor_anunciado=Decimal("600000"), preco_m2=Decimal("5000"), area=Decimal("100"), threshold=0.15
    )
    assert alerta is None


def test_valor_esperado_zero_nao_gera_alerta_nem_erro():
    alerta = calcular_alerta_subprecificado(
        valor_anunciado=Decimal("100"), preco_m2=Decimal("0"), area=Decimal("100"), threshold=0.15
    )
    assert alerta is None
