from datetime import date, datetime, timezone
from decimal import Decimal

from app.modules.dashboard.calculos import (
    inicio_periodo,
    media_dias,
    media_dias_calendario,
    meses_do_periodo,
    preencher_serie_vendas,
)

# --- T410: série temporal -----------------------------------------------------------------


def test_meses_do_periodo_sempre_tem_exatamente_n_pontos():
    resultado = meses_do_periodo(meses=12, referencia=date(2026, 7, 16))
    assert len(resultado) == 12


def test_meses_do_periodo_atravessa_virada_de_ano():
    resultado = meses_do_periodo(meses=3, referencia=date(2026, 1, 15))
    assert resultado == [(2025, 11), (2025, 12), (2026, 1)]


def test_meses_do_periodo_ordem_cronologica_crescente():
    resultado = meses_do_periodo(meses=4, referencia=date(2026, 5, 1))
    assert resultado == [(2026, 2), (2026, 3), (2026, 4), (2026, 5)]


def test_inicio_periodo_e_o_primeiro_dia_do_mes_mais_antigo():
    assert inicio_periodo(meses=3, referencia=date(2026, 1, 15)) == date(2025, 11, 1)


def test_preencher_serie_vendas_mes_sem_venda_entra_como_zero():
    contagem = {(2026, 7): (5, Decimal("500000"))}
    serie = preencher_serie_vendas(contagem, meses=3, referencia=date(2026, 7, 16))

    assert len(serie) == 3
    assert serie[-1] == {"ano": 2026, "mes": 7, "quantidade": 5, "valor_total": Decimal("500000")}
    assert serie[0] == {"ano": 2026, "mes": 5, "quantidade": 0, "valor_total": Decimal("0")}
    assert serie[1] == {"ano": 2026, "mes": 6, "quantidade": 0, "valor_total": Decimal("0")}


def test_preencher_serie_vendas_sem_nenhuma_venda_todos_zero():
    serie = preencher_serie_vendas({}, meses=2, referencia=date(2026, 3, 10))
    assert all(ponto["quantidade"] == 0 and ponto["valor_total"] == Decimal("0") for ponto in serie)


# --- T411 (auxiliar): média de dias --------------------------------------------------------


def test_media_dias_calcula_corretamente():
    pares = [
        (datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 11, tzinfo=timezone.utc)),  # 10 dias
        (datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 21, tzinfo=timezone.utc)),  # 20 dias
    ]
    assert media_dias(pares) == 15.0


def test_media_dias_lista_vazia_retorna_none_nao_zero():
    assert media_dias([]) is None


def test_media_dias_calendario_calcula_diferenca_de_dias_inteiros():
    pares = [(date(2026, 1, 1), date(2026, 1, 11)), (date(2026, 1, 1), date(2026, 1, 21))]
    assert media_dias_calendario(pares) == 15.0


def test_media_dias_calendario_venda_no_mesmo_dia_do_cadastro_e_zero_nao_negativo():
    # Regressão: comparar Imovel.data_venda (só data) como se fosse meia-noite contra
    # created_at (timestamp completo do mesmo dia) gerava diferença artificialmente negativa.
    hoje = date(2026, 7, 17)
    assert media_dias_calendario([(hoje, hoje)]) == 0.0


def test_media_dias_calendario_lista_vazia_retorna_none():
    assert media_dias_calendario([]) is None
