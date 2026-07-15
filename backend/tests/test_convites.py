from urllib.parse import parse_qs, urlparse

import pyotp


def _secret_from_otpauth_url(url: str) -> str:
    return parse_qs(urlparse(url).query)["secret"][0]


async def _upgrade_to_pro(client, token: str) -> None:
    # Plano padrão do signup é "solo" (max_users=1) — convidar corretor exige mais vagas.
    planos_resp = await client.get("/plans")
    plano_pro = next(p for p in planos_resp.json() if p["nome"] == "pro")
    resp = await client.post(
        "/license/upgrade", json={"plan_id": plano_pro["id"]}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200


async def _admin_with_2fa(client, email="admin@example.com", senha="senha12345"):
    signup_resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Convites", "nome": "Admin", "email": email, "senha": senha},
    )
    token = signup_resp.json()["access_token"]

    setup_resp = await client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {token}"})
    secret = _secret_from_otpauth_url(setup_resp.json()["secret_otpauth_url"])
    codigo = pyotp.TOTP(secret).now()
    await client.post("/auth/2fa/verify", json={"codigo": codigo}, headers={"Authorization": f"Bearer {token}"})
    await _upgrade_to_pro(client, token)

    return token


async def _admin_without_2fa(client, email="admin-sem-2fa@example.com", senha="senha12345"):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Sem 2FA", "nome": "Admin", "email": email, "senha": senha},
    )
    return resp.json()["access_token"]


async def test_criar_convite_sem_2fa_retorna_403(client):
    token = await _admin_without_2fa(client)
    resp = await client.post(
        "/users/convites", json={"email": "novo@example.com"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


async def test_criar_convite_com_2fa_ok(client):
    token = await _admin_with_2fa(client)
    resp = await client.post(
        "/users/convites", json={"email": "corretor@example.com"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "corretor@example.com"
    assert body["papel"] == "corretor"


async def test_criar_convite_duplicado_pendente_retorna_409(client):
    token = await _admin_with_2fa(client)
    payload = {"email": "duplicado@example.com"}
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post("/users/convites", json=payload, headers=headers)
    assert first.status_code == 201

    second = await client.post("/users/convites", json=payload, headers=headers)
    assert second.status_code == 409


async def test_criar_convite_para_email_ja_cadastrado_retorna_409(client):
    token = await _admin_with_2fa(client, email="admin2@example.com")
    resp = await client.post(
        "/users/convites", json={"email": "admin2@example.com"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 409


async def test_aceitar_convite_cria_corretor_e_retorna_sessao(client, db_sessionmaker):
    from sqlalchemy import select

    from app.core.tenant_context import system_scope
    from app.modules.tenancy.models import Convite

    token = await _admin_with_2fa(client, email="admin3@example.com")
    await client.post(
        "/users/convites", json={"email": "novocorretor@example.com"}, headers={"Authorization": f"Bearer {token}"}
    )

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Convite).where(Convite.email == "novocorretor@example.com"))
            convite = result.scalar_one()

    resp = await client.post(
        f"/convites/{convite.token}/aceitar", json={"nome": "Corretor Novo", "senha": "outrasenha123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "novocorretor@example.com"
    assert body["user"]["papel"] == "corretor"

    login_resp = await client.post(
        "/auth/login", json={"email": "novocorretor@example.com", "senha": "outrasenha123"}
    )
    assert login_resp.status_code == 200


async def test_aceitar_convite_token_invalido_retorna_410(client):
    resp = await client.post(
        "/convites/token-que-nao-existe/aceitar", json={"nome": "Xavier", "senha": "senha12345"}
    )
    assert resp.status_code == 410


async def test_aceitar_convite_ja_usado_retorna_410(client, db_sessionmaker):
    from sqlalchemy import select

    from app.core.tenant_context import system_scope
    from app.modules.tenancy.models import Convite

    token = await _admin_with_2fa(client, email="admin4@example.com")
    await client.post(
        "/users/convites", json={"email": "usaduasvezes@example.com"}, headers={"Authorization": f"Bearer {token}"}
    )

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Convite).where(Convite.email == "usaduasvezes@example.com"))
            convite_token = result.scalar_one().token

    first = await client.post(
        f"/convites/{convite_token}/aceitar", json={"nome": "Xavier", "senha": "senha12345"}
    )
    assert first.status_code == 200

    second = await client.post(
        f"/convites/{convite_token}/aceitar", json={"nome": "Xavier", "senha": "senha12345"}
    )
    assert second.status_code == 410
