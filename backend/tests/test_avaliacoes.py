from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pyotp
from sqlalchemy import select

from app.core.tenant_context import system_scope
from app.modules.precos_mercado.service import ensure_custo_construcao_seeded, ensure_precos_mercado_seeded
from app.modules.tenancy.models import Convite

_IMOVEL_PADRAO = {
    "titulo": "Apartamento para avaliar",
    "cep": "01310-100",
    "bairro": "Centro",
    "cidade": "São Paulo",
    "estado": "SP",
    "tipo": "apartamento",
    "area_total": 100,
    "idade_anos": 10,
    "conservacao": "boa",
}


async def _signup(client, email="avaliacao@example.com"):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": f"Imobiliária {email}", "nome": "Admin", "email": email, "senha": "senha12345"},
    )
    return resp.json()["access_token"]


async def _seed_precos(db_sessionmaker):
    async with db_sessionmaker() as session:
        await ensure_precos_mercado_seeded(session)
        await ensure_custo_construcao_seeded(session)


async def _criar_imovel(client, token, **overrides):
    payload = {**_IMOVEL_PADRAO, **overrides}
    resp = await client.post("/imoveis", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    return resp.json()["id"]


# --- T121: POST /imoveis/{id}/avaliacoes --------------------------------------------------


async def test_avaliacao_comparativo_persiste_fatores_completos(client, db_sessionmaker):
    token = await _signup(client)
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token)

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes", json={"metodo": "comparativo"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["metodo"] == "comparativo"
    assert Decimal(str(body["valor_min"])) < Decimal(str(body["valor_estimado"])) < Decimal(str(body["valor_max"]))
    assert "preco_m2_base" in body["fatores"]
    assert "fator_idade" in body["fatores"]
    assert "fator_conservacao" in body["fatores"]


async def test_avaliacao_reproducao_requer_padrao_construtivo(client, db_sessionmaker):
    token = await _signup(client, email="aval-reproducao-sem-padrao@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token, tipo="casa")

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes", json={"metodo": "reproducao"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422


async def test_avaliacao_reproducao_ok_com_padrao_construtivo(client, db_sessionmaker):
    token = await _signup(client, email="aval-reproducao@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token, tipo="casa")

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes",
        json={"metodo": "reproducao", "padrao_construtivo": "normal"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["metodo"] == "reproducao"
    assert "valor_terreno" in body["fatores"]
    assert "valor_construcao_bruto" in body["fatores"]


async def test_avaliacao_reproducao_apartamento_gera_observacao_automatica(client, db_sessionmaker):
    token = await _signup(client, email="aval-reproducao-apto@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token, tipo="apartamento")

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes",
        json={"metodo": "reproducao", "padrao_construtivo": "baixo"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert "apartamento" in resp.json()["observacoes"].lower()


async def test_avaliacao_renda_requer_dados_de_renda(client, db_sessionmaker):
    token = await _signup(client, email="aval-renda-sem-dados@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token, tipo="comercial")

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes", json={"metodo": "renda"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422


async def test_avaliacao_renda_ok(client, db_sessionmaker):
    token = await _signup(client, email="aval-renda@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token, tipo="comercial")

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes",
        json={"metodo": "renda", "renda_mensal_bruta": 5000, "despesas_operacionais_mensais": 1000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["fatores"]["taxa_capitalizacao_anual"] == "0.08"


async def test_avaliacao_renda_liquida_negativa_retorna_422(client, db_sessionmaker):
    token = await _signup(client, email="aval-renda-negativa@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token, tipo="comercial")

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes",
        json={"metodo": "renda", "renda_mensal_bruta": 1000, "despesas_operacionais_mensais": 2000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_avaliacao_renda_taxa_capitalizacao_zero_retorna_422(client, db_sessionmaker):
    token = await _signup(client, email="aval-renda-taxa-zero@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token, tipo="comercial")

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes",
        json={
            "metodo": "renda",
            "renda_mensal_bruta": 5000,
            "despesas_operacionais_mensais": 1000,
            "taxa_capitalizacao_anual": 0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_avaliacao_sem_preco_de_mercado_cadastrado_retorna_422(client):
    token = await _signup(client, email="aval-sem-preco@example.com")
    # não chama _seed_precos — base de preços vazia
    imovel_id = await _criar_imovel(client, token)

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes", json={"metodo": "comparativo"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422


async def test_avaliacao_imovel_de_outro_tenant_retorna_404(client, db_sessionmaker):
    token_a = await _signup(client, email="aval-tenant-a@example.com")
    token_b = await _signup(client, email="aval-tenant-b@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token_a)

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes", json={"metodo": "comparativo"}, headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404


# --- T122: GET /imoveis/{id}/avaliacoes (histórico) ---------------------------------------


async def test_listar_avaliacoes_ordenadas_por_data_desc_com_faixa_e_observacoes(client, db_sessionmaker):
    token = await _signup(client, email="aval-historico@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token, tipo="comercial")

    await client.post(
        f"/imoveis/{imovel_id}/avaliacoes", json={"metodo": "comparativo"}, headers={"Authorization": f"Bearer {token}"}
    )
    await client.post(
        f"/imoveis/{imovel_id}/avaliacoes",
        json={"metodo": "renda", "renda_mensal_bruta": 8000, "despesas_operacionais_mensais": 2000},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(f"/imoveis/{imovel_id}/avaliacoes", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["metodo"] == "renda"  # mais recente primeiro
    assert body[1]["metodo"] == "comparativo"
    for avaliacao in body:
        assert avaliacao["valor_min"] is not None
        assert avaliacao["valor_max"] is not None


async def test_listar_avaliacoes_de_imovel_de_outro_tenant_retorna_404(client, db_sessionmaker):
    token_a = await _signup(client, email="aval-hist-tenant-a@example.com")
    token_b = await _signup(client, email="aval-hist-tenant-b@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token_a)

    resp = await client.get(f"/imoveis/{imovel_id}/avaliacoes", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404


async def test_corretor_nao_ve_avaliacao_de_imovel_de_outro_corretor(client, db_sessionmaker):
    admin_token = await _signup(client, email="aval-corretor-admin@example.com")
    await _seed_precos(db_sessionmaker)

    setup = await client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {admin_token}"})
    secret = parse_qs(urlparse(setup.json()["secret_otpauth_url"]).query)["secret"][0]
    codigo = pyotp.TOTP(secret).now()
    await client.post("/auth/2fa/verify", json={"codigo": codigo}, headers={"Authorization": f"Bearer {admin_token}"})
    planos_resp = await client.get("/plans")
    plano_pro = next(p for p in planos_resp.json() if p["nome"] == "pro")
    await client.post(
        "/license/upgrade", json={"plan_id": plano_pro["id"]}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    await client.post(
        "/users/convites",
        json={"email": "aval-corretor@example.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Convite).where(Convite.email == "aval-corretor@example.com"))
            convite = result.scalar_one()
    aceitar = await client.post(f"/convites/{convite.token}/aceitar", json={"nome": "Corretor", "senha": "senha12345"})
    corretor_token = aceitar.json()["access_token"]

    imovel_do_admin = await _criar_imovel(client, admin_token)

    resp = await client.get(f"/imoveis/{imovel_do_admin}/avaliacoes", headers={"Authorization": f"Bearer {corretor_token}"})
    assert resp.status_code == 404
