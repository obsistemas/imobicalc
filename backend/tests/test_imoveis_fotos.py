import io

from sqlalchemy import select

from app.core.tenant_context import system_scope
from app.main import app
from app.modules.imoveis.viacep_driver import FakeViaCepDriver, get_cep_driver

CEP_PADRAO = "01310-100"

_IMOVEL_PAYLOAD = {
    "titulo": "Apartamento com fotos",
    "cep": CEP_PADRAO,
    "bairro": "Centro",
    "cidade": "São Paulo",
    "estado": "sp",
    "tipo": "apartamento",
    "area_total": 80,
    "finalidade": "venda",
}

# Menor PNG válido possível (1x1 pixel transparente) — suficiente pra passar na checagem de
# content-type sem precisar de uma biblioteca de imagem nos testes.
_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a4944415478da6360000002000155bfaad4000000004945"
    "4e44ae426082"
)


def _override_cep_driver() -> None:
    driver = FakeViaCepDriver(sempre_falha=True)

    async def _get():
        return driver

    app.dependency_overrides[get_cep_driver] = _get


async def _signup_and_imovel(client, email):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Fotos", "nome": "Admin", "email": email, "senha": "senha12345"},
    )
    token = resp.json()["access_token"]
    imovel_resp = await client.post("/imoveis", json=_IMOVEL_PAYLOAD, headers={"Authorization": f"Bearer {token}"})
    return token, imovel_resp.json()["id"]


async def test_upload_de_foto_valida_adiciona_url_absoluta(client):
    _override_cep_driver()
    token, imovel_id = await _signup_and_imovel(client, "fotos1@example.com")

    resp = await client.post(
        f"/imoveis/{imovel_id}/fotos",
        files={"arquivo": ("foto.png", io.BytesIO(_PNG_1X1), "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    fotos = resp.json()["fotos"]
    assert len(fotos) == 1
    assert fotos[0].startswith("http://")
    assert "/uploads/imoveis/" in fotos[0]


async def test_upload_tipo_invalido_retorna_422(client):
    _override_cep_driver()
    token, imovel_id = await _signup_and_imovel(client, "fotos2@example.com")

    resp = await client.post(
        f"/imoveis/{imovel_id}/fotos",
        files={"arquivo": ("arquivo.txt", io.BytesIO(b"nao e imagem"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_upload_arquivo_grande_demais_retorna_413(client):
    _override_cep_driver()
    token, imovel_id = await _signup_and_imovel(client, "fotos3@example.com")

    conteudo_grande = b"\x00" * (7 * 1024 * 1024 + 1)
    resp = await client.post(
        f"/imoveis/{imovel_id}/fotos",
        files={"arquivo": ("foto.png", io.BytesIO(conteudo_grande), "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 413


async def test_upload_imovel_de_outro_corretor_retorna_404(client, db_sessionmaker):
    import pyotp
    from urllib.parse import parse_qs, urlparse

    _override_cep_driver()
    admin_token, imovel_id = await _signup_and_imovel(client, "fotosadmin@example.com")

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
        json={"email": "fotoscorretor@example.com", "papel": "corretor"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    from app.modules.tenancy.models import Convite

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Convite).where(Convite.email == "fotoscorretor@example.com"))
            token_convite = result.scalar_one().token
    aceitar_resp = await client.post(
        f"/convites/{token_convite}/aceitar", json={"nome": "Corretor", "senha": "senha12345"}
    )
    corretor_token = aceitar_resp.json()["access_token"]

    resp = await client.post(
        f"/imoveis/{imovel_id}/fotos",
        files={"arquivo": ("foto.png", io.BytesIO(_PNG_1X1), "image/png")},
        headers={"Authorization": f"Bearer {corretor_token}"},
    )
    assert resp.status_code == 404


async def test_remover_foto_por_indice(client):
    _override_cep_driver()
    token, imovel_id = await _signup_and_imovel(client, "fotos4@example.com")
    await client.post(
        f"/imoveis/{imovel_id}/fotos",
        files={"arquivo": ("foto.png", io.BytesIO(_PNG_1X1), "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.delete(f"/imoveis/{imovel_id}/fotos/0", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["fotos"] == []


async def test_remover_foto_indice_invalido_retorna_404(client):
    _override_cep_driver()
    token, imovel_id = await _signup_and_imovel(client, "fotos5@example.com")

    resp = await client.delete(f"/imoveis/{imovel_id}/fotos/0", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


async def test_upload_imovel_inexistente_retorna_404(client):
    import uuid

    _override_cep_driver()
    resp_signup = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária X", "nome": "Admin", "email": "fotosx@example.com", "senha": "senha12345"},
    )
    token = resp_signup.json()["access_token"]

    resp = await client.post(
        f"/imoveis/{uuid.uuid4()}/fotos",
        files={"arquivo": ("foto.png", io.BytesIO(_PNG_1X1), "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
