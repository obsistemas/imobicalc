"""Parsing puro (sem I/O) de uma linha de CSV de importação de preços de mercado — RN3 (uma
linha malformada nunca invalida as demais). A camada de serviço (`service.importar_precos_csv`)
lê o arquivo, chama `parse_linha` por linha e só então persiste."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from app.modules.imoveis.models import ImovelTipo

LinhaValida = tuple[str | None, str | None, str | None, ImovelTipo, Decimal, str]


@dataclass(frozen=True)
class ErroImportacao:
    linha: int
    motivo: str


@dataclass
class RelatorioImportacao:
    total_linhas: int = 0
    criados: int = 0
    atualizados: int = 0
    erros: list[ErroImportacao] = field(default_factory=list)


def parse_linha(linha: dict[str, str | None]) -> LinhaValida:
    """Retorna (bairro, cidade, estado, tipo, preco_m2, fonte) ou levanta `ValueError` com uma
    mensagem acionável — nunca deixa uma linha malformada derrubar as demais (RN3)."""
    bairro = (linha.get("bairro") or "").strip() or None
    cidade = (linha.get("cidade") or "").strip() or None
    estado = (linha.get("estado") or "").strip() or None
    tipo_raw = (linha.get("tipo") or "").strip()
    preco_raw = (linha.get("preco_m2") or "").strip()
    fonte = (linha.get("fonte") or "").strip()

    if not tipo_raw:
        raise ValueError("campo 'tipo' obrigatório")
    try:
        tipo = ImovelTipo(tipo_raw)
    except ValueError as exc:
        tipos_validos = ", ".join(t.value for t in ImovelTipo)
        raise ValueError(f"tipo inválido: '{tipo_raw}' (válidos: {tipos_validos})") from exc

    if not preco_raw:
        raise ValueError("campo 'preco_m2' obrigatório")
    try:
        preco_m2 = Decimal(preco_raw)
    except InvalidOperation as exc:
        raise ValueError(f"preco_m2 não é um número válido: '{preco_raw}'") from exc
    if preco_m2 <= 0:
        raise ValueError("preco_m2 deve ser maior que zero")

    if not fonte:
        raise ValueError("campo 'fonte' obrigatório")

    return bairro, cidade, estado, tipo, preco_m2, fonte
