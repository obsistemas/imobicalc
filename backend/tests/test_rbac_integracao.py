"""010-rbac-papeis: testes de integração ponta a ponta (via HTTP) da matriz de permissões —
complementam tests/test_rbac.py (unitários e puros de app/core/rbac.py)."""

from urllib.parse import parse_qs, urlparse

import pyotp
from sqlalchemy import select

from app.core.tenant_context import system_scope
from app.modules.tenancy.models import Convite

CEP_PADRAO = "01310-100"

_IMOVEL_PAYLOAD = {
    "titulo": "Apartamento com vista para o parque",
    "cep": CEP_PADRAO,
    "bairro": "Centro",
    "cidade": "São Paulo",
    "estado": "sp",
    "tipo": "apartamento",
    "area_total": 80,
}


async def _dono_com_2fa_e_pro(client, email="rbac-dono@example.com", senha="senha12345") -> str:
    resp = await client.post(
        "/auth/signup", json={"nome_tenant": f"Imobiliária {email}", "nome": "Dono", "email": email, "senha": senha}
    )
    token = resp.json()["access_token"]

    setup = await client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {token}"})
    secret = parse_qs(urlparse(setup.json()["secret_otpauth_url"]).query)["secret"][0]
    codigo = pyotp.TOTP(secret).now()
    await client.post("/auth/2fa/verify", json={"codigo": codigo}, headers={"Authorization": f"Bearer {token}"})

    planos_resp = await client.get("/plans")
    plano_pro = next(p for p in planos_resp.json() if p["nome"] == "pro")
    await client.post(
        "/license/upgrade", json={"plan_id": plano_pro["id"]}, headers={"Authorization": f"Bearer {token}"}
    )
    return token


async def _convidar_e_aceitar(client, db_sessionmaker, dono_token, *, email, papel, assistente_de_id=None, nome="Fulano"):
    payload = {"email": email, "papel": papel}
    if assistente_de_id is not None:
        payload["assistente_de_id"] = assistente_de_id
    convite_resp = await client.post(
        "/users/convites", json=payload, headers={"Authorization": f"Bearer {dono_token}"}
    )
    assert convite_resp.status_code == 201, convite_resp.text

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Convite).where(Convite.email == email))
            convite = result.scalar_one()

    aceitar_resp = await client.post(
        f"/convites/{convite.token}/aceitar", json={"nome": nome, "senha": "senha12345"}
    )
    assert aceitar_resp.status_code == 200, aceitar_resp.text
    body = aceitar_resp.json()
    return body["access_token"], body["user"]["id"]


# --- US6: convite com papel -----------------------------------------------------------


async def test_convite_papel_dono_e_rejeitado(client):
    token = await _dono_com_2fa_e_pro(client, email="conv-dono-invalido@example.com")
    resp = await client.post(
        "/users/convites",
        json={"email": "novo-dono@example.com", "papel": "dono"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_convite_assistente_sem_assistente_de_id_e_rejeitado(client):
    token = await _dono_com_2fa_e_pro(client, email="conv-assistente-sem-vinculo@example.com")
    resp = await client.post(
        "/users/convites",
        json={"email": "assistente-sem-vinculo@example.com", "papel": "assistente"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_convite_assistente_de_id_com_papel_nao_assistente_e_rejeitado(client):
    token = await _dono_com_2fa_e_pro(client, email="conv-assistente-de-id-invalido@example.com")
    resp = await client.post(
        "/users/convites",
        json={"email": "gerente-com-vinculo@example.com", "papel": "gerente", "assistente_de_id": "00000000-0000-0000-0000-000000000000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_convite_assistente_de_id_apontando_para_corretor_inexistente_retorna_422(client):
    token = await _dono_com_2fa_e_pro(client, email="conv-assistente-corretor-inexistente@example.com")
    resp = await client.post(
        "/users/convites",
        json={
            "email": "assistente-orfao@example.com",
            "papel": "assistente",
            "assistente_de_id": "00000000-0000-0000-0000-000000000000",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_convite_assistente_com_corretor_valido_ok_e_aceite_propaga_vinculo(client, db_sessionmaker):
    token = await _dono_com_2fa_e_pro(client, email="conv-assistente-ok@example.com")
    _, corretor_id = await _convidar_e_aceitar(
        client, db_sessionmaker, token, email="corretor-vinculo@example.com", papel="corretor"
    )

    convite_resp = await client.post(
        "/users/convites",
        json={"email": "assistente-vinculado@example.com", "papel": "assistente", "assistente_de_id": corretor_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert convite_resp.status_code == 201
    assert convite_resp.json()["assistente_de_id"] == corretor_id

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Convite).where(Convite.email == "assistente-vinculado@example.com"))
            convite = result.scalar_one()

    aceitar_resp = await client.post(
        f"/convites/{convite.token}/aceitar", json={"nome": "Assistente", "senha": "senha12345"}
    )
    assert aceitar_resp.status_code == 200
    assert aceitar_resp.json()["user"]["papel"] == "assistente"


# --- US7: GET /users --------------------------------------------------------------------


async def test_get_users_requer_dono_ou_gerente(client, db_sessionmaker):
    dono_token = await _dono_com_2fa_e_pro(client, email="get-users-corretor@example.com")
    corretor_token, _ = await _convidar_e_aceitar(
        client, db_sessionmaker, dono_token, email="get-users-corretor2@example.com", papel="corretor"
    )

    resp_dono = await client.get("/users", headers={"Authorization": f"Bearer {dono_token}"})
    assert resp_dono.status_code == 200
    emails = {u["email"] for u in resp_dono.json()}
    assert {"get-users-corretor@example.com", "get-users-corretor2@example.com"} <= emails

    resp_corretor = await client.get("/users", headers={"Authorization": f"Bearer {corretor_token}"})
    assert resp_corretor.status_code == 403


# --- US1/US3: visibilidade de imóveis/leads por escopo -----------------------------------


async def test_gerente_ve_imoveis_de_todos_os_corretores(client, db_sessionmaker):
    dono_token = await _dono_com_2fa_e_pro(client, email="gerente-ve-tudo@example.com")
    gerente_token, _ = await _convidar_e_aceitar(
        client, db_sessionmaker, dono_token, email="gerente-vt@example.com", papel="gerente"
    )
    corretor_token, _ = await _convidar_e_aceitar(
        client, db_sessionmaker, dono_token, email="corretor-vt@example.com", papel="corretor"
    )

    resp_imovel = await client.post(
        "/imoveis", json=_IMOVEL_PAYLOAD, headers={"Authorization": f"Bearer {corretor_token}"}
    )
    assert resp_imovel.status_code == 201

    lista_gerente = await client.get("/imoveis", headers={"Authorization": f"Bearer {gerente_token}"})
    assert lista_gerente.json()["total"] == 1


async def test_assistente_ve_apenas_imoveis_do_corretor_vinculado(client, db_sessionmaker):
    dono_token = await _dono_com_2fa_e_pro(client, email="assistente-escopo@example.com")
    corretor_a_token, corretor_a_id = await _convidar_e_aceitar(
        client, db_sessionmaker, dono_token, email="corretor-a@example.com", papel="corretor"
    )
    corretor_b_token, _ = await _convidar_e_aceitar(
        client, db_sessionmaker, dono_token, email="corretor-b@example.com", papel="corretor"
    )
    assistente_token, _ = await _convidar_e_aceitar(
        client,
        db_sessionmaker,
        dono_token,
        email="assistente-a@example.com",
        papel="assistente",
        assistente_de_id=corretor_a_id,
    )

    resp_a = await client.post(
        "/imoveis", json=_IMOVEL_PAYLOAD, headers={"Authorization": f"Bearer {corretor_a_token}"}
    )
    assert resp_a.status_code == 201
    resp_b = await client.post(
        "/imoveis",
        json={**_IMOVEL_PAYLOAD, "titulo": "Imóvel do corretor B"},
        headers={"Authorization": f"Bearer {corretor_b_token}"},
    )
    assert resp_b.status_code == 201

    lista_assistente = await client.get("/imoveis", headers={"Authorization": f"Bearer {assistente_token}"})
    assert lista_assistente.json()["total"] == 1
    assert lista_assistente.json()["items"][0]["id"] == resp_a.json()["id"]


async def test_imovel_criado_por_assistente_e_atribuido_ao_corretor_vinculado(client, db_sessionmaker):
    dono_token = await _dono_com_2fa_e_pro(client, email="assistente-atribuicao@example.com")
    corretor_token, corretor_id = await _convidar_e_aceitar(
        client, db_sessionmaker, dono_token, email="corretor-atrib@example.com", papel="corretor"
    )
    assistente_token, _ = await _convidar_e_aceitar(
        client,
        db_sessionmaker,
        dono_token,
        email="assistente-atrib@example.com",
        papel="assistente",
        assistente_de_id=corretor_id,
    )

    resp = await client.post(
        "/imoveis", json=_IMOVEL_PAYLOAD, headers={"Authorization": f"Bearer {assistente_token}"}
    )
    assert resp.status_code == 201

    lista_corretor = await client.get("/imoveis", headers={"Authorization": f"Bearer {corretor_token}"})
    assert lista_corretor.json()["total"] == 1


# --- US4: exclusão restrita ---------------------------------------------------------------


async def test_assistente_nao_pode_excluir_imovel_mesmo_do_corretor_vinculado(client, db_sessionmaker):
    dono_token = await _dono_com_2fa_e_pro(client, email="assistente-exclusao@example.com")
    corretor_token, corretor_id = await _convidar_e_aceitar(
        client, db_sessionmaker, dono_token, email="corretor-exclusao@example.com", papel="corretor"
    )
    assistente_token, _ = await _convidar_e_aceitar(
        client,
        db_sessionmaker,
        dono_token,
        email="assistente-exclusao2@example.com",
        papel="assistente",
        assistente_de_id=corretor_id,
    )

    resp_imovel = await client.post(
        "/imoveis", json=_IMOVEL_PAYLOAD, headers={"Authorization": f"Bearer {corretor_token}"}
    )
    imovel_id = resp_imovel.json()["id"]

    resp = await client.delete(f"/imoveis/{imovel_id}", headers={"Authorization": f"Bearer {assistente_token}"})
    assert resp.status_code == 404


async def test_gerente_pode_excluir_imovel_de_qualquer_corretor(client, db_sessionmaker):
    dono_token = await _dono_com_2fa_e_pro(client, email="gerente-exclusao@example.com")
    corretor_token, _ = await _convidar_e_aceitar(
        client, db_sessionmaker, dono_token, email="corretor-ge@example.com", papel="corretor"
    )
    gerente_token, _ = await _convidar_e_aceitar(
        client, db_sessionmaker, dono_token, email="gerente-ge@example.com", papel="gerente"
    )

    resp_imovel = await client.post(
        "/imoveis", json=_IMOVEL_PAYLOAD, headers={"Authorization": f"Bearer {corretor_token}"}
    )
    imovel_id = resp_imovel.json()["id"]

    resp = await client.delete(f"/imoveis/{imovel_id}", headers={"Authorization": f"Bearer {gerente_token}"})
    assert resp.status_code == 204


# --- US5: avaliação/sugestão bloqueada para assistente -------------------------------------


async def test_assistente_recebe_403_ao_tentar_avaliar(client, db_sessionmaker):
    dono_token = await _dono_com_2fa_e_pro(client, email="assistente-avalia@example.com")
    corretor_token, corretor_id = await _convidar_e_aceitar(
        client, db_sessionmaker, dono_token, email="corretor-avalia@example.com", papel="corretor"
    )
    assistente_token, _ = await _convidar_e_aceitar(
        client,
        db_sessionmaker,
        dono_token,
        email="assistente-avalia2@example.com",
        papel="assistente",
        assistente_de_id=corretor_id,
    )

    resp_imovel = await client.post(
        "/imoveis", json=_IMOVEL_PAYLOAD, headers={"Authorization": f"Bearer {corretor_token}"}
    )
    imovel_id = resp_imovel.json()["id"]

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes",
        json={"metodo": "comparativo"},
        headers={"Authorization": f"Bearer {assistente_token}"},
    )
    assert resp.status_code == 403


async def test_corretor_continua_podendo_avaliar(client, db_sessionmaker):
    dono_token = await _dono_com_2fa_e_pro(client, email="corretor-avalia-ok@example.com")
    corretor_token, _ = await _convidar_e_aceitar(
        client, db_sessionmaker, dono_token, email="corretor-avalia-ok2@example.com", papel="corretor"
    )

    resp_imovel = await client.post(
        "/imoveis", json=_IMOVEL_PAYLOAD, headers={"Authorization": f"Bearer {corretor_token}"}
    )
    imovel_id = resp_imovel.json()["id"]

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes",
        json={"metodo": "comparativo"},
        headers={"Authorization": f"Bearer {corretor_token}"},
    )
    # Sem preço de mercado cadastrado a avaliação falha por outro motivo (422) — o que importa
    # aqui é que o corretor passa pela guarda de papel (não recebe 403).
    assert resp.status_code != 403
