from urllib.parse import parse_qs, urlparse

import pyotp
from sqlalchemy import select

from app.core.tenant_context import system_scope, tenant_scope
from app.main import app
from app.modules.imoveis.models import Imovel
from app.modules.imoveis.viacep_driver import FakeViaCepDriver, get_cep_driver
from app.modules.tenancy.models import Tenant, User

CEP_PADRAO = "01310-100"

_PAYLOAD_BASE = {
    "titulo": "Apartamento com vista para o parque",
    "cep": CEP_PADRAO,
    "bairro": "Centro",
    "cidade": "São Paulo",
    "estado": "sp",
    "tipo": "apartamento",
    "area_total": 80,
}


def _override_cep_driver(driver) -> None:
    async def _get():
        return driver

    app.dependency_overrides[get_cep_driver] = _get


async def _signup(client, email="corretor-imoveis@example.com", senha="senha12345"):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": f"Imobiliária {email}", "nome": "Admin", "email": email, "senha": senha},
    )
    return resp.json()["access_token"]


async def _tenant_by_email(db_sessionmaker, admin_email: str) -> Tenant:
    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == admin_email))
            user = result.scalar_one()
            result = await session.execute(select(Tenant).where(Tenant.uuid == user.tenant_id))
            return result.scalar_one()


# --- T082: POST /imoveis --------------------------------------------------------------


async def test_criar_imovel_campos_obrigatorios_ausentes_retorna_422(client):
    token = await _signup(client)
    payload = dict(_PAYLOAD_BASE)
    del payload["titulo"]
    resp = await client.post("/imoveis", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422


async def test_criar_imovel_cep_invalido_retorna_422(client):
    token = await _signup(client)
    payload = {**_PAYLOAD_BASE, "cep": "abc"}
    resp = await client.post("/imoveis", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422


async def test_criar_imovel_cep_nao_encontrado_no_viacep_nao_impede_criacao(client):
    token = await _signup(client, email="cep-falha@example.com")
    _override_cep_driver(FakeViaCepDriver(sempre_falha=True))

    resp = await client.post("/imoveis", json=_PAYLOAD_BASE, headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["logradouro"] is None
    assert body["titulo"] == _PAYLOAD_BASE["titulo"]
    assert body["estado"] == "SP"


async def test_criar_imovel_preenche_logradouro_via_viacep(client):
    token = await _signup(client, email="cep-ok@example.com")
    _override_cep_driver(FakeViaCepDriver(respostas={"01310100": "Avenida Paulista"}))

    resp = await client.post("/imoveis", json=_PAYLOAD_BASE, headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 201
    assert resp.json()["logradouro"] == "Avenida Paulista"


async def test_criar_imovel_alem_do_limite_do_plano_retorna_402(client, db_sessionmaker):
    token = await _signup(client, email="limite-imoveis@example.com")
    tenant = await _tenant_by_email(db_sessionmaker, "limite-imoveis@example.com")

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == "limite-imoveis@example.com"))
            admin = result.scalar_one()
        with tenant_scope(tenant.uuid):
            for i in range(50):  # plano padrão "solo": max_imoveis=50
                session.add(
                    Imovel(
                        tenant_id=tenant.uuid,
                        corretor_id=admin.uuid,
                        titulo=f"Imóvel {i}",
                        cep=CEP_PADRAO,
                        bairro="Centro",
                        cidade="São Paulo",
                        estado="SP",
                        tipo="apartamento",
                        area_total=50,
                        fotos="[]",
                    )
                )
            await session.commit()

    resp = await client.post("/imoveis", json=_PAYLOAD_BASE, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 402


async def test_corretor_so_ve_imoveis_proprios_admin_ve_todos(client, db_sessionmaker):
    admin_token = await _signup(client, email="visibilidade@example.com")

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
        json={"email": "corretor-visibilidade@example.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    async with db_sessionmaker() as session:
        with system_scope():
            from app.modules.tenancy.models import Convite

            result = await session.execute(
                select(Convite).where(Convite.email == "corretor-visibilidade@example.com")
            )
            convite = result.scalar_one()
    aceitar_resp = await client.post(
        f"/convites/{convite.token}/aceitar", json={"nome": "Corretor", "senha": "senha12345"}
    )
    corretor_token = aceitar_resp.json()["access_token"]

    resp_admin_imovel = await client.post(
        "/imoveis", json=_PAYLOAD_BASE, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp_admin_imovel.status_code == 201

    resp_corretor_imovel = await client.post(
        "/imoveis",
        json={**_PAYLOAD_BASE, "titulo": "Imóvel do corretor"},
        headers={"Authorization": f"Bearer {corretor_token}"},
    )
    assert resp_corretor_imovel.status_code == 201
    imovel_corretor_id = resp_corretor_imovel.json()["id"]
    imovel_admin_id = resp_admin_imovel.json()["id"]

    lista_corretor = await client.get("/imoveis", headers={"Authorization": f"Bearer {corretor_token}"})
    assert lista_corretor.json()["total"] == 1
    assert lista_corretor.json()["items"][0]["id"] == imovel_corretor_id

    lista_admin = await client.get("/imoveis", headers={"Authorization": f"Bearer {admin_token}"})
    assert lista_admin.json()["total"] == 2

    resp_404 = await client.get(f"/imoveis/{imovel_admin_id}", headers={"Authorization": f"Bearer {corretor_token}"})
    assert resp_404.status_code == 404

    resp_ok = await client.get(f"/imoveis/{imovel_corretor_id}", headers={"Authorization": f"Bearer {corretor_token}"})
    assert resp_ok.status_code == 200


# --- T083: GET /imoveis ----------------------------------------------------------------


async def test_listar_imoveis_filtros_combinam_em_and(client):
    token = await _signup(client, email="filtros@example.com")

    await client.post(
        "/imoveis",
        json={**_PAYLOAD_BASE, "titulo": "A", "bairro": "Centro", "cidade": "São Paulo", "valor_anunciado": 100000},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/imoveis",
        json={**_PAYLOAD_BASE, "titulo": "B", "bairro": "Jardins", "cidade": "São Paulo", "valor_anunciado": 500000},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/imoveis",
        json={
            **_PAYLOAD_BASE,
            "titulo": "C",
            "bairro": "Centro",
            "cidade": "Campinas",
            "valor_anunciado": 100000,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        "/imoveis",
        params={"bairro": "Centro", "cidade": "São Paulo"},
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["titulo"] == "A"

    resp_valor = await client.get(
        "/imoveis",
        params={"valor_min": 200000, "valor_max": 600000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_valor.json()["total"] == 1
    assert resp_valor.json()["items"][0]["titulo"] == "B"


async def test_listar_imoveis_paginacao_retorna_total_correto(client):
    token = await _signup(client, email="paginacao@example.com")
    for i in range(5):
        await client.post(
            "/imoveis", json={**_PAYLOAD_BASE, "titulo": f"Imóvel {i}"}, headers={"Authorization": f"Bearer {token}"}
        )

    resp = await client.get("/imoveis", params={"skip": 2, "limit": 2}, headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["total"] == 5
    assert body["skip"] == 2
    assert body["limit"] == 2
    assert len(body["items"]) == 2


async def test_listar_imoveis_nunca_retorna_de_outro_tenant(client):
    token_a = await _signup(client, email="tenant-a@example.com")
    token_b = await _signup(client, email="tenant-b@example.com")

    await client.post(
        "/imoveis", json={**_PAYLOAD_BASE, "titulo": "Só do tenant A"}, headers={"Authorization": f"Bearer {token_a}"}
    )

    resp_b = await client.get("/imoveis", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.json()["total"] == 0


# --- CRUD complementar (contrato OpenAPI) -----------------------------------------------


async def test_atualizar_imovel_altera_status(client):
    token = await _signup(client, email="update@example.com")
    criado = await client.post("/imoveis", json=_PAYLOAD_BASE, headers={"Authorization": f"Bearer {token}"})
    imovel_id = criado.json()["id"]

    resp = await client.put(
        f"/imoveis/{imovel_id}",
        json={**_PAYLOAD_BASE, "status": "reservado"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "reservado"


async def test_inativar_imovel_remove_da_listagem(client):
    token = await _signup(client, email="inativar@example.com")
    criado = await client.post("/imoveis", json=_PAYLOAD_BASE, headers={"Authorization": f"Bearer {token}"})
    imovel_id = criado.json()["id"]

    resp = await client.delete(f"/imoveis/{imovel_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204

    lista = await client.get("/imoveis", headers={"Authorization": f"Bearer {token}"})
    assert lista.json()["total"] == 0
