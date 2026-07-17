from urllib.parse import parse_qs, urlparse

import pyotp
from sqlalchemy import select

from app.core.tenant_context import system_scope
from app.modules.tenancy.models import Convite

_IMOVEL_PADRAO = {
    "titulo": "Apartamento para lead",
    "cep": "01310-100",
    "bairro": "Centro",
    "cidade": "São Paulo",
    "estado": "SP",
    "tipo": "apartamento",
    "area_total": 100,
}


async def _signup(client, email="leads@example.com"):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": f"Imobiliária {email}", "nome": "Admin", "email": email, "senha": "senha12345"},
    )
    return resp.json()["access_token"]


async def _criar_imovel(client, token, **overrides):
    payload = {**_IMOVEL_PADRAO, **overrides}
    resp = await client.post("/imoveis", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _criar_lead(client, token, **overrides):
    payload = {"nome": "Fulano de Tal", "origem": "site", **overrides}
    resp = await client.post("/leads", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    return resp.json()


# --- T310: POST /leads --------------------------------------------------------------------


async def test_criar_lead_sem_imovel(client):
    token = await _signup(client)
    lead = await _criar_lead(client, token)
    assert lead["estagio"] == "novo"
    assert lead["imovel_id"] is None
    assert lead["origem"] == "site"


async def test_criar_lead_com_imovel_do_mesmo_tenant(client):
    token = await _signup(client, email="lead-com-imovel@example.com")
    imovel_id = await _criar_imovel(client, token)
    lead = await _criar_lead(client, token, imovel_id=imovel_id)
    assert lead["imovel_id"] == imovel_id


async def test_criar_lead_com_imovel_de_outro_tenant_retorna_404(client):
    token_a = await _signup(client, email="lead-tenant-a@example.com")
    token_b = await _signup(client, email="lead-tenant-b@example.com")
    imovel_id = await _criar_imovel(client, token_a)

    resp = await client.post(
        "/leads",
        json={"nome": "Fulano", "origem": "site", "imovel_id": imovel_id},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


# --- T311: PUT /leads/{id}/estagio ---------------------------------------------------------


async def test_mover_estagio_livremente_entre_nao_terminais(client):
    token = await _signup(client, email="lead-mover@example.com")
    lead = await _criar_lead(client, token)

    resp = await client.put(
        f"/leads/{lead['id']}/estagio", json={"estagio": "visita"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["estagio"] == "visita"


async def test_mover_estagio_a_partir_de_fechado_retorna_422(client):
    token = await _signup(client, email="lead-terminal@example.com")
    lead = await _criar_lead(client, token)
    await client.put(f"/leads/{lead['id']}/estagio", json={"estagio": "fechado"}, headers={"Authorization": f"Bearer {token}"})

    resp = await client.put(
        f"/leads/{lead['id']}/estagio", json={"estagio": "contatado"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422


async def test_mover_estagio_para_fechado_preenche_fechado_em(client):
    token = await _signup(client, email="lead-fechado-em@example.com")
    lead = await _criar_lead(client, token)
    assert lead["fechado_em"] is None

    resp = await client.put(
        f"/leads/{lead['id']}/estagio", json={"estagio": "fechado"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["fechado_em"] is not None


async def test_mover_estagio_para_nao_fechado_nao_preenche_fechado_em(client):
    token = await _signup(client, email="lead-nao-fechado-em@example.com")
    lead = await _criar_lead(client, token)

    resp = await client.put(
        f"/leads/{lead['id']}/estagio", json={"estagio": "visita"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["fechado_em"] is None


async def test_mover_estagio_gera_nota_automatica(client):
    token = await _signup(client, email="lead-nota-automatica@example.com")
    lead = await _criar_lead(client, token)
    await client.put(f"/leads/{lead['id']}/estagio", json={"estagio": "contatado"}, headers={"Authorization": f"Bearer {token}"})

    resp = await client.get(f"/leads/{lead['id']}/notas", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    notas = resp.json()
    assert len(notas) == 1
    assert notas[0]["automatica"] is True
    assert "novo" in notas[0]["texto"] and "contatado" in notas[0]["texto"]


# --- T312: notas ------------------------------------------------------------------------


async def test_adicionar_nota_manual(client):
    token = await _signup(client, email="lead-nota-manual@example.com")
    lead = await _criar_lead(client, token)

    resp = await client.post(
        f"/leads/{lead['id']}/notas", json={"texto": "Cliente pediu para ligar amanhã"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["automatica"] is False

    listagem = await client.get(f"/leads/{lead['id']}/notas", headers={"Authorization": f"Bearer {token}"})
    assert len(listagem.json()) == 1


# --- GET /leads/{id} (detalhe) ------------------------------------------------------------


async def test_obter_lead_por_id(client):
    token = await _signup(client, email="lead-obter@example.com")
    lead = await _criar_lead(client, token)

    resp = await client.get(f"/leads/{lead['id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["id"] == lead["id"]


async def test_obter_lead_de_outro_tenant_retorna_404(client):
    token_a = await _signup(client, email="lead-obter-tenant-a@example.com")
    token_b = await _signup(client, email="lead-obter-tenant-b@example.com")
    lead = await _criar_lead(client, token_a)

    resp = await client.get(f"/leads/{lead['id']}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404


# --- T313: GET /leads (listagem + visibilidade) --------------------------------------------


async def test_listar_leads_filtra_por_estagio(client):
    token = await _signup(client, email="lead-filtro@example.com")
    lead1 = await _criar_lead(client, token)
    await _criar_lead(client, token)
    await client.put(f"/leads/{lead1['id']}/estagio", json={"estagio": "proposta"}, headers={"Authorization": f"Bearer {token}"})

    resp = await client.get("/leads?estagio=proposta", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == lead1["id"]


async def test_corretor_visibilidade_leads(client, db_sessionmaker):
    admin_token = await _signup(client, email="lead-vis-admin@example.com")

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
        "/users/convites", json={"email": "lead-vis-corretor@example.com"}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Convite).where(Convite.email == "lead-vis-corretor@example.com"))
            convite = result.scalar_one()
    aceitar = await client.post(f"/convites/{convite.token}/aceitar", json={"nome": "Corretor", "senha": "senha12345"})
    corretor_token = aceitar.json()["access_token"]

    lead_admin = await _criar_lead(client, admin_token, nome="Lead do Admin")
    lead_corretor = await _criar_lead(client, corretor_token, nome="Lead do Corretor")

    resp_corretor = await client.get("/leads", headers={"Authorization": f"Bearer {corretor_token}"})
    ids_corretor = {lead["id"] for lead in resp_corretor.json()}
    assert ids_corretor == {lead_corretor["id"]}

    resp_admin = await client.get("/leads", headers={"Authorization": f"Bearer {admin_token}"})
    ids_admin = {lead["id"] for lead in resp_admin.json()}
    assert ids_admin == {lead_admin["id"], lead_corretor["id"]}
