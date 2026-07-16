from app.modules.precos_mercado.service import ensure_custo_construcao_seeded, ensure_precos_mercado_seeded

_IMOVEL_PADRAO = {
    "titulo": "Apartamento para sugestão de preço",
    "cep": "01310-100",
    "bairro": "Centro",
    "cidade": "São Paulo",
    "estado": "SP",
    "tipo": "apartamento",
    "area_total": 100,
    "idade_anos": 10,
    "conservacao": "boa",
}


async def _signup(client, email="sugestao@example.com"):
    resp = await client.post(
        "/auth/signup",
        json={"nome_tenant": f"Imobiliária {email}", "nome": "Admin", "email": email, "senha": "senha12345"},
    )
    return resp.json()["access_token"]


async def _seed_precos(db_sessionmaker):
    async with db_sessionmaker() as session:
        await ensure_precos_mercado_seeded(session)
        await ensure_custo_construcao_seeded(session)


async def _criar_imovel(client, token, **overrides):
    payload = {**_IMOVEL_PADRAO, **overrides}
    resp = await client.post("/imoveis", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _criar_avaliacao(client, token, imovel_id):
    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes", json={"metodo": "comparativo"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# --- T221: POST /imoveis/{id}/avaliacoes/{id}/sugestoes-preco -----------------------------


async def test_sugestao_rapido_persiste_fatores_completos(client, db_sessionmaker):
    token = await _signup(client)
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token)
    avaliacao_id = await _criar_avaliacao(client, token, imovel_id)

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes/{avaliacao_id}/sugestoes-preco",
        json={"urgencia": "rapido"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["urgencia"] == "rapido"
    assert body["avaliacao_id"] == avaliacao_id
    assert body["valor_minimo_aceitavel"] is not None
    assert "fator_urgencia" in body["fatores"]
    assert "margem_negociacao_pct" in body["fatores"]
    assert "clamp_aplicado" in body["fatores"]


async def test_sugestao_normal_preco_igual_ao_valor_estimado_da_avaliacao(client, db_sessionmaker):
    token = await _signup(client, email="sug-normal@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token)
    avaliacao_resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes", json={"metodo": "comparativo"}, headers={"Authorization": f"Bearer {token}"}
    )
    avaliacao = avaliacao_resp.json()

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes/{avaliacao['id']}/sugestoes-preco",
        json={"urgencia": "normal"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert float(body["preco_anuncio_sugerido"]) == float(avaliacao["valor_estimado"])


async def test_sugestao_maximo_preco_acima_do_valor_estimado(client, db_sessionmaker):
    token = await _signup(client, email="sug-maximo@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token)
    avaliacao_id = await _criar_avaliacao(client, token, imovel_id)

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes/{avaliacao_id}/sugestoes-preco",
        json={"urgencia": "maximo"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert float(body["fatores"]["fator_urgencia"]) == 1.08


async def test_sugestao_avaliacao_de_outro_tenant_retorna_404(client, db_sessionmaker):
    token_a = await _signup(client, email="sug-tenant-a@example.com")
    token_b = await _signup(client, email="sug-tenant-b@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token_a)
    avaliacao_id = await _criar_avaliacao(client, token_a, imovel_id)

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes/{avaliacao_id}/sugestoes-preco",
        json={"urgencia": "normal"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


async def test_sugestao_avaliacao_inexistente_retorna_404(client, db_sessionmaker):
    token = await _signup(client, email="sug-aval-inexistente@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token)
    outro_imovel_id = await _criar_imovel(client, token, titulo="Outro imóvel")
    avaliacao_id = await _criar_avaliacao(client, token, outro_imovel_id)

    resp = await client.post(
        f"/imoveis/{imovel_id}/avaliacoes/{avaliacao_id}/sugestoes-preco",
        json={"urgencia": "normal"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# --- T222: GET /imoveis/{id}/avaliacoes/{id}/sugestoes-preco (histórico) ------------------


async def test_listar_sugestoes_ordenadas_por_data_desc(client, db_sessionmaker):
    token = await _signup(client, email="sug-historico@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token)
    avaliacao_id = await _criar_avaliacao(client, token, imovel_id)

    await client.post(
        f"/imoveis/{imovel_id}/avaliacoes/{avaliacao_id}/sugestoes-preco",
        json={"urgencia": "rapido"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/imoveis/{imovel_id}/avaliacoes/{avaliacao_id}/sugestoes-preco",
        json={"urgencia": "maximo"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(
        f"/imoveis/{imovel_id}/avaliacoes/{avaliacao_id}/sugestoes-preco",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["urgencia"] == "maximo"  # mais recente primeiro
    assert body[1]["urgencia"] == "rapido"
    for sugestao in body:
        assert sugestao["valor_minimo_aceitavel"] is not None


async def test_listar_sugestoes_de_avaliacao_de_outro_tenant_retorna_404(client, db_sessionmaker):
    token_a = await _signup(client, email="sug-hist-tenant-a@example.com")
    token_b = await _signup(client, email="sug-hist-tenant-b@example.com")
    await _seed_precos(db_sessionmaker)
    imovel_id = await _criar_imovel(client, token_a)
    avaliacao_id = await _criar_avaliacao(client, token_a, imovel_id)

    resp = await client.get(
        f"/imoveis/{imovel_id}/avaliacoes/{avaliacao_id}/sugestoes-preco",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
