from urllib.parse import parse_qs, urlparse

import pyotp


async def test_get_current_user_without_authorization_header_returns_401(client):
    resp = await client.post("/auth/2fa/setup")
    assert resp.status_code == 401


async def test_get_current_user_with_malformed_bearer_returns_401(client):
    resp = await client.post("/auth/2fa/setup", headers={"Authorization": "Bearer nao-e-jwt"})
    assert resp.status_code == 401


async def test_get_current_user_without_bearer_prefix_returns_401(client):
    resp = await client.post("/auth/2fa/setup", headers={"Authorization": "algum-token-sem-prefixo"})
    assert resp.status_code == 401


async def test_non_admin_cannot_create_convite(client, db_sessionmaker):
    from sqlalchemy import select

    from app.core.tenant_context import system_scope
    from app.modules.tenancy.models import Convite

    def secret_from_url(url):
        return parse_qs(urlparse(url).query)["secret"][0]

    admin_signup = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Papel", "nome": "Admin", "email": "papeladmin@example.com", "senha": "senha12345"},
    )
    admin_token = admin_signup.json()["access_token"]

    setup = await client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {admin_token}"})
    secret = secret_from_url(setup.json()["secret_otpauth_url"])
    codigo = pyotp.TOTP(secret).now()
    await client.post("/auth/2fa/verify", json={"codigo": codigo}, headers={"Authorization": f"Bearer {admin_token}"})

    planos_resp = await client.get("/plans")
    plano_pro = next(p for p in planos_resp.json() if p["nome"] == "pro")
    await client.post(
        "/license/upgrade",
        json={"plan_id": plano_pro["id"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    await client.post(
        "/users/convites",
        json={"email": "corretorpapel@example.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Convite).where(Convite.email == "corretorpapel@example.com"))
            token = result.scalar_one().token

    accept_resp = await client.post(
        f"/convites/{token}/aceitar", json={"nome": "Corretor Papel", "senha": "senha12345"}
    )
    corretor_token = accept_resp.json()["access_token"]

    resp = await client.post(
        "/users/convites",
        json={"email": "outro@example.com"},
        headers={"Authorization": f"Bearer {corretor_token}"},
    )
    assert resp.status_code == 403
