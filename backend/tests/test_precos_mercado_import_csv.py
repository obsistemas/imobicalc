from decimal import Decimal

import pytest

from app.modules.imoveis.models import ImovelTipo
from app.modules.precos_mercado.import_csv import parse_linha

# --- T511: parse_linha (função pura) --------------------------------------------------------


def test_parse_linha_completa_ok():
    linha = {"bairro": "Centro", "cidade": "Campinas", "estado": "SP", "tipo": "casa", "preco_m2": "4500.50", "fonte": "Portal X"}
    bairro, cidade, estado, tipo, preco_m2, fonte = parse_linha(linha)
    assert bairro == "Centro"
    assert cidade == "Campinas"
    assert estado == "SP"
    assert tipo == ImovelTipo.CASA
    assert preco_m2 == Decimal("4500.50")
    assert fonte == "Portal X"


def test_parse_linha_campos_vazios_viram_none():
    linha = {"bairro": "", "cidade": "", "estado": "", "tipo": "terreno", "preco_m2": "1000", "fonte": "manual"}
    bairro, cidade, estado, _, _, _ = parse_linha(linha)
    assert bairro is None
    assert cidade is None
    assert estado is None


def test_parse_linha_tipo_ausente_levanta_erro():
    linha = {"bairro": "X", "cidade": "Y", "tipo": "", "preco_m2": "1000", "fonte": "manual"}
    with pytest.raises(ValueError, match="tipo"):
        parse_linha(linha)


def test_parse_linha_tipo_invalido_levanta_erro():
    linha = {"tipo": "castelo", "preco_m2": "1000", "fonte": "manual"}
    with pytest.raises(ValueError, match="tipo inválido"):
        parse_linha(linha)


def test_parse_linha_preco_ausente_levanta_erro():
    linha = {"tipo": "casa", "preco_m2": "", "fonte": "manual"}
    with pytest.raises(ValueError, match="preco_m2"):
        parse_linha(linha)


def test_parse_linha_preco_nao_numerico_levanta_erro():
    linha = {"tipo": "casa", "preco_m2": "abc", "fonte": "manual"}
    with pytest.raises(ValueError, match="preco_m2"):
        parse_linha(linha)


def test_parse_linha_preco_zero_ou_negativo_levanta_erro():
    linha = {"tipo": "casa", "preco_m2": "0", "fonte": "manual"}
    with pytest.raises(ValueError, match="maior que zero"):
        parse_linha(linha)


def test_parse_linha_fonte_ausente_levanta_erro():
    linha = {"tipo": "casa", "preco_m2": "1000", "fonte": ""}
    with pytest.raises(ValueError, match="fonte"):
        parse_linha(linha)
