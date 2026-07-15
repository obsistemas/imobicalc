async def _signup(client, email="carla@example.com", senha="senha12345"):
    return await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Login", "nome": "Carla", "email": email, "senha": senha},
    )


async def test_login_success(client):
    await _signup(client)
    resp = await client.post("/auth/login", json={"email": "carla@example.com", "senha": "senha12345"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "carla@example.com"
    assert "refresh_token" in resp.cookies


async def test_login_wrong_password_returns_401_generic(client):
    await _signup(client)
    resp = await client.post("/auth/login", json={"email": "carla@example.com", "senha": "errada123"})
    assert resp.status_code == 401
    assert "inválid" in resp.json()["detail"].lower()


async def test_login_unknown_email_returns_same_401(client):
    resp_unknown = await client.post("/auth/login", json={"email": "ninguem@example.com", "senha": "qualquer123"})
    await _signup(client)
    resp_wrong_pw = await client.post("/auth/login", json={"email": "carla@example.com", "senha": "errada123"})

    assert resp_unknown.status_code == resp_wrong_pw.status_code == 401
    assert resp_unknown.json() == resp_wrong_pw.json()


async def test_refresh_rotates_token_and_old_refresh_becomes_invalid(client):
    signup_resp = await _signup(client)
    old_refresh_cookie = signup_resp.cookies["refresh_token"]

    refresh_resp = await client.post("/auth/refresh")
    assert refresh_resp.status_code == 200
    assert refresh_resp.json()["access_token"] != signup_resp.json()["access_token"]

    client.cookies.set("refresh_token", old_refresh_cookie)
    reuse_resp = await client.post("/auth/refresh")
    assert reuse_resp.status_code == 401


async def test_refresh_without_cookie_returns_401(client):
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


async def test_logout_revokes_refresh_token(client):
    await _signup(client)
    logout_resp = await client.post("/auth/logout")
    assert logout_resp.status_code == 204

    refresh_resp = await client.post("/auth/refresh")
    assert refresh_resp.status_code == 401


async def test_refresh_with_malformed_cookie_returns_401(client):
    client.cookies.set("refresh_token", "isso-nao-e-um-jwt")
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


async def test_logout_with_malformed_cookie_still_succeeds(client):
    client.cookies.set("refresh_token", "isso-nao-e-um-jwt")
    resp = await client.post("/auth/logout")
    assert resp.status_code == 204


async def test_refresh_for_deactivated_user_returns_401(client, db_sessionmaker):
    from sqlalchemy import select

    from app.core.tenant_context import system_scope
    from app.modules.tenancy.models import User

    signup_resp = await _signup(client, email="inativa@example.com")

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == "inativa@example.com"))
            user = result.scalar_one()
            user.ativo = False
            await session.commit()

    client.cookies.set("refresh_token", signup_resp.cookies["refresh_token"])
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401
