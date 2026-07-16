"""Motor de cálculo (M4) — funções puras, sem I/O (ARQUITETURA-REFERENCIA.md §5, Artigo III
da constituição: domínio crítico, TDD exaustivo). A camada de serviço resolve os dados
(imóvel, preço de mercado) e só então chama estas funções."""

from dataclasses import dataclass, field
from decimal import Decimal

_TAXA_CAPITALIZACAO_MINIMA = Decimal("0.01")

_FATOR_CONSERVACAO = {
    "otima": Decimal("1.05"),
    "boa": Decimal("1.0"),
    "regular": Decimal("0.9"),
    "ruim": Decimal("0.75"),
}


class RendaLiquidaInvalidaError(Exception):
    pass


class TaxaCapitalizacaoInvalidaError(Exception):
    pass


@dataclass(frozen=True)
class ResultadoCalculo:
    valor_estimado: Decimal
    valor_min: Decimal
    valor_max: Decimal
    fatores: dict = field(default_factory=dict)
    observacao_automatica: str | None = None


def _fator_idade(idade_anos: int | None) -> Decimal:
    """Depreciação linear simples: 1%/ano, limitada a 30% (RN — data-model.md)."""
    if idade_anos is None:
        return Decimal("1.0")
    return max(Decimal("1.0") - Decimal("0.01") * idade_anos, Decimal("0.7"))


def _fator_conservacao(conservacao: str | None) -> Decimal:
    if conservacao is None:
        return Decimal("1.0")
    return _FATOR_CONSERVACAO[conservacao]


def calcular_comparativo(
    *,
    area: Decimal,
    preco_m2_base: Decimal,
    idade_anos: int | None,
    conservacao: str | None,
    preco_eh_fallback: bool,
) -> ResultadoCalculo:
    fator_idade = _fator_idade(idade_anos)
    fator_conservacao = _fator_conservacao(conservacao)
    valor_estimado = preco_m2_base * area * fator_idade * fator_conservacao
    margem = Decimal("0.20") if preco_eh_fallback else Decimal("0.10")

    fatores = {
        "area": str(area),
        "preco_m2_base": str(preco_m2_base),
        "preco_eh_fallback": preco_eh_fallback,
        "idade_anos": idade_anos,
        "fator_idade": str(fator_idade),
        "conservacao": conservacao,
        "fator_conservacao": str(fator_conservacao),
        "margem_confianca": str(margem),
    }
    return ResultadoCalculo(
        valor_estimado=valor_estimado,
        valor_min=valor_estimado * (Decimal("1") - margem),
        valor_max=valor_estimado * (Decimal("1") + margem),
        fatores=fatores,
    )


def calcular_reproducao(
    *,
    area_terreno: Decimal,
    preco_m2_terreno: Decimal,
    area_construida: Decimal,
    custo_m2_construcao: Decimal,
    idade_anos: int | None,
    conservacao: str | None,
    tipo_imovel: str,
) -> ResultadoCalculo:
    fator_idade = _fator_idade(idade_anos)
    fator_conservacao = _fator_conservacao(conservacao)

    valor_terreno = area_terreno * preco_m2_terreno
    valor_construcao_bruto = area_construida * custo_m2_construcao
    valor_construcao_depreciado = valor_construcao_bruto * fator_idade * fator_conservacao
    valor_estimado = valor_terreno + valor_construcao_depreciado
    margem = Decimal("0.15")

    observacao = None
    if tipo_imovel == "apartamento":
        observacao = (
            "Método de custo aplicado a apartamento: área de terreno aproximada pela área "
            "total do imóvel — estimativa menos confiável que para casa/terreno."
        )

    fatores = {
        "area_terreno": str(area_terreno),
        "preco_m2_terreno": str(preco_m2_terreno),
        "valor_terreno": str(valor_terreno),
        "area_construida": str(area_construida),
        "custo_m2_construcao": str(custo_m2_construcao),
        "valor_construcao_bruto": str(valor_construcao_bruto),
        "idade_anos": idade_anos,
        "fator_idade": str(fator_idade),
        "conservacao": conservacao,
        "fator_conservacao": str(fator_conservacao),
        "valor_construcao_depreciado": str(valor_construcao_depreciado),
        "margem_confianca": str(margem),
    }
    return ResultadoCalculo(
        valor_estimado=valor_estimado,
        valor_min=valor_estimado * (Decimal("1") - margem),
        valor_max=valor_estimado * (Decimal("1") + margem),
        fatores=fatores,
        observacao_automatica=observacao,
    )


def calcular_renda(
    *,
    renda_mensal_bruta: Decimal,
    despesas_operacionais_mensais: Decimal,
    taxa_capitalizacao_anual: Decimal,
) -> ResultadoCalculo:
    renda_liquida_mensal = renda_mensal_bruta - despesas_operacionais_mensais
    if renda_liquida_mensal <= 0:
        raise RendaLiquidaInvalidaError(renda_liquida_mensal)
    if taxa_capitalizacao_anual <= 0:
        raise TaxaCapitalizacaoInvalidaError(taxa_capitalizacao_anual)

    renda_liquida_anual = renda_liquida_mensal * 12
    valor_estimado = renda_liquida_anual / taxa_capitalizacao_anual

    # taxa maior -> valor menor; taxa menor -> valor maior. Nunca deixa a taxa cair a <= 0.
    taxa_max = taxa_capitalizacao_anual + Decimal("0.01")
    taxa_min = max(taxa_capitalizacao_anual - Decimal("0.01"), _TAXA_CAPITALIZACAO_MINIMA)

    fatores = {
        "renda_mensal_bruta": str(renda_mensal_bruta),
        "despesas_operacionais_mensais": str(despesas_operacionais_mensais),
        "renda_liquida_mensal": str(renda_liquida_mensal),
        "taxa_capitalizacao_anual": str(taxa_capitalizacao_anual),
        "taxa_min": str(taxa_min),
        "taxa_max": str(taxa_max),
    }
    return ResultadoCalculo(
        valor_estimado=valor_estimado,
        valor_min=renda_liquida_anual / taxa_max,
        valor_max=renda_liquida_anual / taxa_min,
        fatores=fatores,
    )
