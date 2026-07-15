from urllib.parse import parse_qs, urlparse

import pyotp


def _secret_from_otpauth_url(url: str) -> str:
    query = parse_qs(urlparse(url).query)
    return query["secret"][0]


async def _signup(client, email="duda@example.com", senha="senha12345"):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária 2FA", "nome": "Duda", "email": email, "senha": senha},
    )
    return resp.json()["access_token"]


async def _setup_totp(client, token: str) -> str:
    resp = await client.post("/auth/2fa/setup", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    return _secret_from_otpauth_url(resp.json()["secret_otpauth_url"])


async def test_2fa_setup_and_verify_activates_and_returns_10_recovery_codes(client):
    token = await _signup(client)
    secret = await _setup_totp(client, token)

    codigo = pyotp.TOTP(secret).now()
    resp = await client.post(
        "/auth/2fa/verify", json={"codigo": codigo}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ativado"] is True
    assert len(body["recovery_codes"]) == 10
    assert len({*body["recovery_codes"]}) == 10  # todos únicos


async def test_2fa_verify_wrong_code_does_not_activate(client):
    token = await _signup(client)
    await _setup_totp(client, token)

    resp = await client.post(
        "/auth/2fa/verify", json={"codigo": "12345"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422  # min_length=6 no schema


async def test_2fa_verify_incorrect_but_well_formed_code_returns_400(client):
    token = await _signup(client)
    secret = await _setup_totp(client, token)

    correto = pyotp.TOTP(secret).now()
    errado = "0" * 6 if correto != "0" * 6 else "1" * 6

    resp = await client.post(
        "/auth/2fa/verify", json={"codigo": errado}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 400


async def test_login_with_2fa_enabled_requires_valid_code(client):
    token = await _signup(client)
    secret = await _setup_totp(client, token)
    codigo = pyotp.TOTP(secret).now()
    await client.post("/auth/2fa/verify", json={"codigo": codigo}, headers={"Authorization": f"Bearer {token}"})

    sem_codigo = await client.post("/auth/login", json={"email": "duda@example.com", "senha": "senha12345"})
    assert sem_codigo.status_code == 401

    novo_codigo = pyotp.TOTP(secret).now()
    com_codigo = await client.post(
        "/auth/login",
        json={"email": "duda@example.com", "senha": "senha12345", "codigo_totp": novo_codigo},
    )
    assert com_codigo.status_code == 200


async def test_login_with_recovery_code_is_consumed_once(client):
    token = await _signup(client, email="rec@example.com")
    secret = await _setup_totp(client, token)
    codigo = pyotp.TOTP(secret).now()
    verify_resp = await client.post(
        "/auth/2fa/verify", json={"codigo": codigo}, headers={"Authorization": f"Bearer {token}"}
    )
    recovery_code = verify_resp.json()["recovery_codes"][0]

    first = await client.post(
        "/auth/login", json={"email": "rec@example.com", "senha": "senha12345", "codigo_totp": recovery_code}
    )
    assert first.status_code == 200

    second = await client.post(
        "/auth/login", json={"email": "rec@example.com", "senha": "senha12345", "codigo_totp": recovery_code}
    )
    assert second.status_code == 401
