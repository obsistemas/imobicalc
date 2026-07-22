from decimal import Decimal

from sqlalchemy import select

from app.modules.precos_mercado.geocoding_driver import FakeGeocodingDriver
from app.modules.precos_mercado.models import PrecoMercado
from app.modules.precos_mercado.service import importar_precos_csv

from tests.test_precos_mercado import _admin_token, _corretor_token

_CABECALHO = "bairro,cidade,estado,tipo,preco_m2,fonte"


# --- T511: importar_precos_csv (service) ----------------------------------------------------


async def test_importar_csv_cria_registro_novo(db_sessionmaker):
    csv_texto = f"{_CABECALHO}\nCentro,Campinas,SP,casa,4500,Portal X"
    async with db_sessionmaker() as session:
        relatorio = await importar_precos_csv(session, csv_texto, geocoding_driver=FakeGeocodingDriver())

    assert relatorio.total_linhas == 1
    assert relatorio.criados == 1
    assert relatorio.atualizados == 0
    assert relatorio.erros == []


async def test_importar_csv_atualiza_registro_existente_upsert(db_sessionmaker):
    csv_texto = f"{_CABECALHO}\nCentro,Campinas,SP,casa,4500,Portal X"
    async with db_sessionmaker() as session:
        await importar_precos_csv(session, csv_texto, geocoding_driver=FakeGeocodingDriver())

    csv_atualizado = f"{_CABECALHO}\nCentro,Campinas,SP,casa,5000,Portal Y"
    driver_com_coordenada = FakeGeocodingDriver(respostas={"Centro|Campinas": (Decimal("-22.9"), Decimal("-47.06"))})
    async with db_sessionmaker() as session:
        relatorio = await importar_precos_csv(session, csv_atualizado, geocoding_driver=driver_com_coordenada)

    assert relatorio.criados == 0
    assert relatorio.atualizados == 1

    async with db_sessionmaker() as session:
        result = await session.execute(
            select(PrecoMercado).where(PrecoMercado.bairro == "Centro", PrecoMercado.cidade == "Campinas")
        )
        preco = result.scalar_one()
        assert preco.preco_m2 == Decimal("5000")
        assert preco.fonte == "Portal Y"
        # regressão: upsert também atualiza a coordenada quando a geocodificação tem sucesso
        assert preco.latitude == Decimal("-22.9")
        assert preco.longitude == Decimal("-47.06")


async def test_importar_csv_linha_malformada_nao_interrompe_as_demais(db_sessionmaker):
    csv_texto = (
        f"{_CABECALHO}\n"
        "Centro,Campinas,SP,casa,4500,Portal X\n"
        "Jardins,São Paulo,SP,tipo-invalido,9000,Portal X\n"
        "Vila Nova,Recife,PE,apartamento,7000,Portal X"
    )
    async with db_sessionmaker() as session:
        relatorio = await importar_precos_csv(session, csv_texto, geocoding_driver=FakeGeocodingDriver())

    assert relatorio.total_linhas == 3
    assert relatorio.criados == 2
    assert len(relatorio.erros) == 1
    assert relatorio.erros[0].linha == 3  # cabeçalho é linha 1
    assert "tipo inválido" in relatorio.erros[0].motivo


async def test_importar_csv_arquivo_vazio_retorna_relatorio_vazio(db_sessionmaker):
    async with db_sessionmaker() as session:
        relatorio = await importar_precos_csv(session, _CABECALHO, geocoding_driver=FakeGeocodingDriver())

    assert relatorio.total_linhas == 0
    assert relatorio.criados == 0
    assert relatorio.erros == []


async def test_importar_csv_geocodifica_cada_linha(db_sessionmaker):
    csv_texto = f"{_CABECALHO}\nCentro,Campinas,SP,casa,4500,Portal X"
    driver = FakeGeocodingDriver(respostas={"Centro|Campinas": (Decimal("-22.9"), Decimal("-47.06"))})
    async with db_sessionmaker() as session:
        await importar_precos_csv(session, csv_texto, geocoding_driver=driver)

    async with db_sessionmaker() as session:
        result = await session.execute(
            select(PrecoMercado).where(PrecoMercado.bairro == "Centro", PrecoMercado.cidade == "Campinas")
        )
        preco = result.scalar_one()
        assert preco.latitude == Decimal("-22.9")
        assert preco.longitude == Decimal("-47.06")


# --- T512: endpoint POST /admin/precos-mercado/importar -------------------------------------


async def test_endpoint_importar_requer_admin(client, db_sessionmaker):
    admin_token = await _admin_token(client, email="import-admin@example.com")
    corretor_token = await _corretor_token(client, db_sessionmaker, admin_token, email="import-corretor@example.com")

    arquivo = (f"{_CABECALHO}\nCentro,Campinas,SP,casa,4500,Portal X").encode("utf-8")
    resp = await client.post(
        "/admin/precos-mercado/importar",
        files={"arquivo": ("precos.csv", arquivo, "text/csv")},
        headers={"Authorization": f"Bearer {corretor_token}"},
    )
    assert resp.status_code == 403


async def test_endpoint_importar_ok(client):
    admin_token = await _admin_token(client, email="import-ok@example.com")

    arquivo = (
        f"{_CABECALHO}\n"
        "Centro,Campinas,SP,casa,4500,Portal X\n"
        "Jardins,São Paulo,SP,tipo-invalido,9000,Portal X"
    ).encode("utf-8")
    resp = await client.post(
        "/admin/precos-mercado/importar",
        files={"arquivo": ("precos.csv", arquivo, "text/csv")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_linhas"] == 2
    assert body["criados"] == 1
    assert len(body["erros"]) == 1
    assert body["erros"][0]["linha"] == 3
