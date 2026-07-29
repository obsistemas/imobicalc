import uuid

from sqlalchemy import select

from app.core.tenant_context import system_scope
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
    "valor_anunciado": 500000,
}


def _override_cep_driver() -> None:
    driver = FakeViaCepDriver(sempre_falha=True)

    async def _get():
        return driver

    app.dependency_overrides[get_cep_driver] = _get


async def _signup_and_slug(client, db_sessionmaker, email="publico@example.com"):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": "Imobiliária Pública", "nome": "Admin", "email": email, "senha": "senha12345"},
    )
    token = resp.json()["access_token"]
    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            tenant_result = await session.execute(select(Tenant).where(Tenant.uuid == user.tenant_id))
            slug = tenant_result.scalar_one().slug
    return token, slug


def _host(slug: str) -> str:
    return f"{slug}.proptechavaliador.com.br"


async def _criar_imovel(client, token, **overrides):
    payload = {**_PAYLOAD_BASE, **overrides}
    resp = await client.post("/imoveis", json=payload, headers={"Authorization": f"Bearer {token}"})
    return resp.json()


async def test_imovel_publico_disponivel_retorna_dto_sem_campos_internos(client, db_sessionmaker):
    _override_cep_driver()
    token, slug = await _signup_and_slug(client, db_sessionmaker)
    imovel = await _criar_imovel(client, token, matricula="12345", iptu_quitado=True)

    resp = await client.get(f"/imoveis/publico/{imovel['id']}", headers={"Host": _host(slug)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["titulo"] == _PAYLOAD_BASE["titulo"]
    assert "matricula" not in body
    assert "iptu_quitado" not in body
    assert "corretor_id" not in body


async def test_imovel_publico_incrementa_views_a_cada_chamada(client, db_sessionmaker):
    _override_cep_driver()
    token, slug = await _signup_and_slug(client, db_sessionmaker, email="views@example.com")
    imovel = await _criar_imovel(client, token)

    await client.get(f"/imoveis/publico/{imovel['id']}", headers={"Host": _host(slug)})
    await client.get(f"/imoveis/publico/{imovel['id']}", headers={"Host": _host(slug)})

    async with db_sessionmaker() as session:
        with system_scope():
            result = await session.execute(select(Imovel).where(Imovel.uuid == uuid.UUID(imovel["id"])))
            assert result.scalar_one().views == 2


async def test_imovel_vendido_nao_aparece_na_pagina_publica(client, db_sessionmaker):
    _override_cep_driver()
    token, slug = await _signup_and_slug(client, db_sessionmaker, email="vendido@example.com")
    imovel = await _criar_imovel(client, token)
    await client.put(
        f"/imoveis/{imovel['id']}",
        json={**_PAYLOAD_BASE, "status": "vendido"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(f"/imoveis/publico/{imovel['id']}", headers={"Host": _host(slug)})
    assert resp.status_code == 404


async def test_imovel_de_outro_tenant_nao_aparece_via_host_errado(client, db_sessionmaker):
    _override_cep_driver()
    token_a, _ = await _signup_and_slug(client, db_sessionmaker, email="tenanta@example.com")
    _, slug_b = await _signup_and_slug(client, db_sessionmaker, email="tenantb@example.com")
    imovel_a = await _criar_imovel(client, token_a)

    resp = await client.get(f"/imoveis/publico/{imovel_a['id']}", headers={"Host": _host(slug_b)})
    assert resp.status_code == 404


async def test_host_nao_resolvido_retorna_404(client, db_sessionmaker):
    _override_cep_driver()
    token, _ = await _signup_and_slug(client, db_sessionmaker, email="semhost@example.com")
    imovel = await _criar_imovel(client, token)

    resp = await client.get(f"/imoveis/publico/{imovel['id']}")
    assert resp.status_code == 404
