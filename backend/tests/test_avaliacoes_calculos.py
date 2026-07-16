from decimal import Decimal

import pytest

from app.modules.avaliacoes.calculos import (
    RendaLiquidaInvalidaError,
    TaxaCapitalizacaoInvalidaError,
    calcular_comparativo,
    calcular_renda,
    calcular_reproducao,
)

# --- T110: calcular_comparativo ----------------------------------------------------------


def test_comparativo_sem_idade_nem_conservacao_usa_fatores_neutros():
    resultado = calcular_comparativo(
        area=Decimal("100"),
        preco_m2_base=Decimal("5000"),
        idade_anos=None,
        conservacao=None,
        preco_eh_fallback=False,
    )
    assert resultado.valor_estimado == Decimal("500000")
    assert resultado.fatores["fator_idade"] == "1.0"
    assert resultado.fatores["fator_conservacao"] == "1.0"


def test_comparativo_depreciacao_por_idade_limitada_a_30_por_cento():
    resultado = calcular_comparativo(
        area=Decimal("100"),
        preco_m2_base=Decimal("1000"),
        idade_anos=200,  # bem além do limite
        conservacao=None,
        preco_eh_fallback=False,
    )
    assert resultado.fatores["fator_idade"] == "0.7"
    assert resultado.valor_estimado == Decimal("100") * Decimal("1000") * Decimal("0.7")


@pytest.mark.parametrize(
    "conservacao,fator_esperado",
    [("otima", "1.05"), ("boa", "1.0"), ("regular", "0.9"), ("ruim", "0.75")],
)
def test_comparativo_fator_conservacao_por_nivel(conservacao, fator_esperado):
    resultado = calcular_comparativo(
        area=Decimal("100"),
        preco_m2_base=Decimal("1000"),
        idade_anos=None,
        conservacao=conservacao,
        preco_eh_fallback=False,
    )
    assert resultado.fatores["fator_conservacao"] == fator_esperado


def test_comparativo_faixa_confianca_10_por_cento_com_preco_especifico():
    resultado = calcular_comparativo(
        area=Decimal("100"),
        preco_m2_base=Decimal("1000"),
        idade_anos=None,
        conservacao=None,
        preco_eh_fallback=False,
    )
    assert resultado.valor_min == resultado.valor_estimado * Decimal("0.9")
    assert resultado.valor_max == resultado.valor_estimado * Decimal("1.1")


def test_comparativo_faixa_confianca_20_por_cento_com_preco_fallback():
    resultado = calcular_comparativo(
        area=Decimal("100"),
        preco_m2_base=Decimal("1000"),
        idade_anos=None,
        conservacao=None,
        preco_eh_fallback=True,
    )
    assert resultado.valor_min == resultado.valor_estimado * Decimal("0.8")
    assert resultado.valor_max == resultado.valor_estimado * Decimal("1.2")


# --- T111: calcular_reproducao -----------------------------------------------------------


def test_reproducao_soma_terreno_mais_construcao_depreciada():
    resultado = calcular_reproducao(
        area_terreno=Decimal("300"),
        preco_m2_terreno=Decimal("1000"),
        area_construida=Decimal("150"),
        custo_m2_construcao=Decimal("2000"),
        idade_anos=None,
        conservacao=None,
        tipo_imovel="casa",
    )
    valor_terreno = Decimal("300") * Decimal("1000")
    valor_construcao = Decimal("150") * Decimal("2000")
    assert resultado.valor_estimado == valor_terreno + valor_construcao


def test_reproducao_depreciacao_incide_so_sobre_construcao_nao_sobre_terreno():
    resultado = calcular_reproducao(
        area_terreno=Decimal("300"),
        preco_m2_terreno=Decimal("1000"),
        area_construida=Decimal("150"),
        custo_m2_construcao=Decimal("2000"),
        idade_anos=200,  # fator 0.7
        conservacao=None,
        tipo_imovel="casa",
    )
    valor_terreno = Decimal("300") * Decimal("1000")
    valor_construcao_depreciado = Decimal("150") * Decimal("2000") * Decimal("0.7")
    assert resultado.valor_estimado == valor_terreno + valor_construcao_depreciado


def test_reproducao_observacao_automatica_para_apartamento():
    resultado = calcular_reproducao(
        area_terreno=Decimal("80"),
        preco_m2_terreno=Decimal("1000"),
        area_construida=Decimal("80"),
        custo_m2_construcao=Decimal("2000"),
        idade_anos=None,
        conservacao=None,
        tipo_imovel="apartamento",
    )
    assert resultado.observacao_automatica is not None
    assert "apartamento" in resultado.observacao_automatica.lower()


def test_reproducao_sem_observacao_automatica_para_casa():
    resultado = calcular_reproducao(
        area_terreno=Decimal("300"),
        preco_m2_terreno=Decimal("1000"),
        area_construida=Decimal("150"),
        custo_m2_construcao=Decimal("2000"),
        idade_anos=None,
        conservacao=None,
        tipo_imovel="casa",
    )
    assert resultado.observacao_automatica is None


def test_reproducao_faixa_confianca_fixa_15_por_cento():
    resultado = calcular_reproducao(
        area_terreno=Decimal("300"),
        preco_m2_terreno=Decimal("1000"),
        area_construida=Decimal("150"),
        custo_m2_construcao=Decimal("2000"),
        idade_anos=None,
        conservacao=None,
        tipo_imovel="casa",
    )
    assert resultado.valor_min == resultado.valor_estimado * Decimal("0.85")
    assert resultado.valor_max == resultado.valor_estimado * Decimal("1.15")


# --- T112: calcular_renda -----------------------------------------------------------------


def test_renda_capitaliza_renda_liquida_anual_pela_taxa():
    resultado = calcular_renda(
        renda_mensal_bruta=Decimal("5000"),
        despesas_operacionais_mensais=Decimal("1000"),
        taxa_capitalizacao_anual=Decimal("0.08"),
    )
    renda_liquida_anual = (Decimal("5000") - Decimal("1000")) * 12
    assert resultado.valor_estimado == renda_liquida_anual / Decimal("0.08")


def test_renda_liquida_negativa_levanta_erro():
    with pytest.raises(RendaLiquidaInvalidaError):
        calcular_renda(
            renda_mensal_bruta=Decimal("1000"),
            despesas_operacionais_mensais=Decimal("2000"),
            taxa_capitalizacao_anual=Decimal("0.08"),
        )


def test_renda_liquida_zero_levanta_erro():
    with pytest.raises(RendaLiquidaInvalidaError):
        calcular_renda(
            renda_mensal_bruta=Decimal("1000"),
            despesas_operacionais_mensais=Decimal("1000"),
            taxa_capitalizacao_anual=Decimal("0.08"),
        )


def test_renda_taxa_zero_ou_negativa_levanta_erro():
    with pytest.raises(TaxaCapitalizacaoInvalidaError):
        calcular_renda(
            renda_mensal_bruta=Decimal("5000"),
            despesas_operacionais_mensais=Decimal("1000"),
            taxa_capitalizacao_anual=Decimal("0"),
        )


def test_renda_faixa_confianca_por_variacao_de_1_ponto_percentual():
    resultado = calcular_renda(
        renda_mensal_bruta=Decimal("5000"),
        despesas_operacionais_mensais=Decimal("1000"),
        taxa_capitalizacao_anual=Decimal("0.08"),
    )
    renda_liquida_anual = (Decimal("5000") - Decimal("1000")) * 12
    assert resultado.valor_min == renda_liquida_anual / Decimal("0.09")
    assert resultado.valor_max == renda_liquida_anual / Decimal("0.07")


def test_renda_taxa_minima_evita_divisao_por_zero_no_valor_max():
    resultado = calcular_renda(
        renda_mensal_bruta=Decimal("5000"),
        despesas_operacionais_mensais=Decimal("1000"),
        taxa_capitalizacao_anual=Decimal("0.005"),  # taxa - 0.01 seria negativa
    )
    renda_liquida_anual = (Decimal("5000") - Decimal("1000")) * 12
    assert resultado.fatores["taxa_min"] == "0.01"
    assert resultado.valor_max == renda_liquida_anual / Decimal("0.01")
