from urllib.parse import parse_qs, urlparse

import pyotp
import pytest
from sqlalchemy import select

from app.core.tenant_context import system_scope
from app.modules.imoveis.models import ImovelTipo
from app.modules.precos_mercado.models import PadraoConstrutivo, PrecoMercado
from app.modules.precos_mercado.service import (
    CustoConstrucaoNaoEncontradoError,
    PrecoMercadoNaoEncontradoError,
    buscar_custo_construcao,
    buscar_preco_mercado,
    ensure_custo_construcao_seeded,
    ensure_precos_mercado_seeded,
)
from app.modules.tenancy.models import Convite


async def _admin_token(client, email="admin-precos@example.com"):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Preços", "nome": "Admin", "email": email, "senha": "senha12345"},
    )
    return resp.json()["access_token"]


async def _corretor_token(client, db_sessionmaker, admin_token: str, email="corretor-precos@example.com"):
    setup = await client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {admin_token}"})
    secret = parse_qs(urlparse(setup.json()["secret_otpauth_url"]).query)["secret"][0]
    codigo = pyotp.TOTP(secret).now()
    await client.post("/auth/2fa/verify", json={"codigo": codigo}, headers={"Authorization": f"Bearer {admin_token}"})

    planos_resp = await client.get("/plans")
    plano_pro = next(p for p in planos_resp.json() if p["nome"] == "pro")
    await client.post(
        "/license/upgrade", json={"plan_id": plano_pro["id"]}, headers={"Authorization": f"Bearer {admin_token}"}
    )

    await client.post("/users/convites", json={"email": email}, headers={"Authorization": f"Bearer {admin_token}"})
    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Convite).where(Convite.email == email))
            convite = result.scalar_one()
    resp = await client.post(f"/convites/{convite.token}/aceitar", json={"nome": "Corretor", "senha": "senha12345"})
    return resp.json()["access_token"]


async def test_criar_preco_mercado_requer_admin(client, db_sessionmaker):
    admin_token = await _admin_token(client)
    corretor_token = await _corretor_token(client, db_sessionmaker, admin_token)

    resp = await client.post(
        "/admin/precos-mercado",
        json={"tipo": "apartamento", "preco_m2": 6000, "fonte": "teste"},
        headers={"Authorization": f"Bearer {corretor_token}"},
    )
    assert resp.status_code == 403


async def test_criar_e_listar_preco_mercado_admin_ok(client):
    admin_token = await _admin_token(client, email="admin-precos2@example.com")

    resp = await client.post(
        "/admin/precos-mercado",
        json={"bairro": "Centro", "cidade": "Campinas", "tipo": "casa", "preco_m2": 4500, "fonte": "curadoria manual"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["bairro"] == "Centro"
    assert body["preco_m2"] == "4500.0000" or float(body["preco_m2"]) == 4500

    lista = await client.get("/admin/precos-mercado", headers={"Authorization": f"Bearer {admin_token}"})
    assert lista.status_code == 200
    assert len(lista.json()) == 1


# --- T102: fallback de busca (RN3) --------------------------------------------------------


async def test_buscar_preco_mercado_especifico_do_bairro(db_sessionmaker):
    async with db_sessionmaker() as session:
        session.add(
            PrecoMercado(bairro="Jardins", cidade="São Paulo", tipo=ImovelTipo.APARTAMENTO, preco_m2="9000", fonte="t")
        )
        await session.commit()

        preco, eh_fallback = await buscar_preco_mercado(
            session, bairro="Jardins", cidade="São Paulo", tipo=ImovelTipo.APARTAMENTO
        )
        assert preco.preco_m2 == 9000
        assert eh_fallback is False


async def test_buscar_preco_mercado_cai_para_fallback_generico_do_tipo(db_sessionmaker):
    async with db_sessionmaker() as session:
        session.add(PrecoMercado(bairro=None, cidade=None, tipo=ImovelTipo.CASA, preco_m2="4000", fonte="seed"))
        await session.commit()

        preco, eh_fallback = await buscar_preco_mercado(
            session, bairro="Bairro Sem Dado", cidade="Cidade Sem Dado", tipo=ImovelTipo.CASA
        )
        assert preco.preco_m2 == 4000
        assert eh_fallback is True


async def test_buscar_preco_mercado_sem_especifico_nem_generico_levanta_erro(db_sessionmaker):
    async with db_sessionmaker() as session:
        with pytest.raises(PrecoMercadoNaoEncontradoError):
            await buscar_preco_mercado(session, bairro="X", cidade="Y", tipo=ImovelTipo.GALPAO)


async def test_ensure_precos_mercado_seeded_popula_fallback_de_todos_os_tipos(db_sessionmaker):
    async with db_sessionmaker() as session:
        await ensure_precos_mercado_seeded(session)
        for tipo in ImovelTipo:
            preco, eh_fallback = await buscar_preco_mercado(session, bairro="Qualquer", cidade="Qualquer", tipo=tipo)
            assert eh_fallback is True


async def test_ensure_precos_mercado_seeded_e_idempotente(db_sessionmaker):
    async with db_sessionmaker() as session:
        await ensure_precos_mercado_seeded(session)
        await ensure_precos_mercado_seeded(session)
        result = await session.execute(select(PrecoMercado))
        assert len(result.scalars().all()) == len(ImovelTipo)


async def test_buscar_custo_construcao_encontrado(db_sessionmaker):
    async with db_sessionmaker() as session:
        await ensure_custo_construcao_seeded(session)
        custo = await buscar_custo_construcao(session, padrao=PadraoConstrutivo.NORMAL)
        assert custo.custo_m2 == 2200


async def test_buscar_custo_construcao_nao_encontrado_levanta_erro(db_sessionmaker):
    async with db_sessionmaker() as session:
        with pytest.raises(CustoConstrucaoNaoEncontradoError):
            await buscar_custo_construcao(session, padrao=PadraoConstrutivo.ALTO)
