from decimal import Decimal

from app.modules.precos_mercado.models import PrecoMercado
from app.modules.precos_mercado.service import obter_mapa_calor

# --- T531: obter_mapa_calor (service) -------------------------------------------------------


async def test_mapa_calor_so_retorna_entradas_com_coordenada(db_sessionmaker):
    async with db_sessionmaker() as session:
        session.add(
            PrecoMercado(
                bairro="Centro", cidade="Campinas", tipo="casa", preco_m2=Decimal("4500"), fonte="teste",
                latitude=Decimal("-22.9"), longitude=Decimal("-47.06"),
            )
        )
        session.add(
            PrecoMercado(
                bairro="Sem Coordenada", cidade="Cidade X", tipo="casa", preco_m2=Decimal("3000"), fonte="teste",
            )
        )
        await session.commit()

    async with db_sessionmaker() as session:
        pontos = await obter_mapa_calor(session)

    assert len(pontos) == 1
    assert pontos[0].bairro == "Centro"


async def test_mapa_calor_sem_nenhuma_entrada_geocodificada_retorna_lista_vazia(db_sessionmaker):
    async with db_sessionmaker() as session:
        session.add(PrecoMercado(bairro="X", cidade="Y", tipo="casa", preco_m2=Decimal("1000"), fonte="teste"))
        await session.commit()

    async with db_sessionmaker() as session:
        pontos = await obter_mapa_calor(session)

    assert pontos == []


# --- T532: endpoint GET /precos-mercado/mapa-calor ------------------------------------------


async def test_endpoint_mapa_calor(client):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Mapa", "nome": "Admin", "email": "mapa-calor@example.com", "senha": "senha12345"},
    )
    token = resp.json()["access_token"]

    await client.post(
        "/admin/precos-mercado",
        json={"bairro": "Centro", "cidade": "Campinas", "tipo": "casa", "preco_m2": 4500, "fonte": "teste"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get("/precos-mercado/mapa-calor", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    # sem driver de geocodificação real configurado no teste (Fake sem respostas), a entrada
    # criada acima não tem coordenada — resposta é uma lista vazia, não erro.
    assert resp.json() == []
