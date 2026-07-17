"""Funções puras do dashboard (sem I/O) — geração/preenchimento de série temporal e médias de
dias. A camada de serviço busca os dados brutos e só então chama estas funções (mesmo racional
de separação usado no motor de avaliação, 002-avaliacao)."""

from datetime import date, datetime
from decimal import Decimal


def meses_do_periodo(*, meses: int, referencia: date) -> list[tuple[int, int]]:
    """Lista de `meses` pares (ano, mês) terminando no mês de `referencia` (inclusive),
    em ordem cronológica crescente. Atravessa virada de ano corretamente."""
    resultado = []
    ano, mes = referencia.year, referencia.month
    for _ in range(meses):
        resultado.append((ano, mes))
        mes -= 1
        if mes == 0:
            mes = 12
            ano -= 1
    return list(reversed(resultado))


def inicio_periodo(*, meses: int, referencia: date) -> date:
    """Primeiro dia do mês mais antigo do período — usado como corte para filtros de query."""
    ano, mes = meses_do_periodo(meses=meses, referencia=referencia)[0]
    return date(ano, mes, 1)


def preencher_serie_vendas(
    contagem_por_mes: dict[tuple[int, int], tuple[int, Decimal]], *, meses: int, referencia: date
) -> list[dict]:
    """Garante exatamente `meses` pontos na série (RN2 — mês sem venda entra como zero, nunca
    omitido)."""
    serie = []
    for ano, mes in meses_do_periodo(meses=meses, referencia=referencia):
        quantidade, valor_total = contagem_por_mes.get((ano, mes), (0, Decimal("0")))
        serie.append({"ano": ano, "mes": mes, "quantidade": quantidade, "valor_total": valor_total})
    return serie


def media_dias(pares: list[tuple[datetime, datetime]]) -> float | None:
    """Média de dias entre (inicio, fim) de cada par, com precisão de sub-dia (os dois lados têm
    hora/minuto reais — caso de `Lead.created_at`/`fechado_em`). `None` (não 0) quando a lista é
    vazia — RN da spec: ausência de dado nunca é confundida com métrica zero."""
    if not pares:
        return None
    total_dias = sum((fim - inicio).total_seconds() / 86400 for inicio, fim in pares)
    return total_dias / len(pares)


def media_dias_calendario(pares: list[tuple[date, date]]) -> float | None:
    """Média de dias entre (inicio, fim) em granularidade de dia calendário — usar quando um dos
    lados só tem data, sem hora (caso de `Imovel.data_venda`). Tratar esse lado como "meia-noite
    UTC" e comparar contra um timestamp completo (`created_at`) geraria diferença artificialmente
    negativa para vendas no mesmo dia do cadastro; aqui os dois lados são reduzidos a `date` antes
    de subtrair, o que nunca fica negativo para dado válido (venda no mesmo dia = 0 dias)."""
    if not pares:
        return None
    total_dias = sum((fim - inicio).days for inicio, fim in pares)
    return total_dias / len(pares)
