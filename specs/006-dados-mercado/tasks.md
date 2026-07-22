# Tasks — Feature 006: Dados de Mercado

Formato: `T5## [P?] [US?] descrição` — [P] = paralelizável. Cada task termina com testes verdes +
commit convencional. Numeração: feature 006 usa T5xx.

## Bloco A — Geocodificação + schema
- T500 Migration + model: `preco_mercado.latitude`/`longitude` (nullable).
- T501 `GeocodingDriver` (Protocol + `NominatimGeocodingDriver` via httpx + `FakeGeocodingDriver`
  para testes) em `precos_mercado/geocoding_driver.py`, mesmo padrão do `ViaCepDriver`.
- T502 TDD: geocodificação bem-sucedida preenche lat/long; falha/timeout/sem resultado deixa
  nulo sem levantar exceção para quem chama.

## Bloco B — Importação CSV
*Depende do Bloco A (cada linha tenta geocodificar).*
- T510 Contrato OpenAPI de `POST /admin/precos-mercado/importar`.
- T511 TDD: `importar_precos_csv`. Casos: bairro+cidade+tipo já existente atualiza (upsert);
  combinação nova cria; linha malformada (campo faltando, tipo inválido, preço não-numérico)
  reportada no resultado sem interromper as demais linhas; arquivo vazio retorna relatório
  vazio (não erro).
- T512 Endpoint `POST /admin/precos-mercado/importar` (multipart, `admin`-only; `corretor`
  recebe 403).

## Bloco C — Alerta de subprecificação
*Depende do Bloco A (comparação usa preco_mercado já existente da 002) — reaproveita canal WS
da 004-leads.*
- T520 Setting `subprecificado_threshold` (padrão 0.15) em `app/config.py`.
- T521 TDD: comparação de subprecificação (função pura). Casos: valor abaixo do threshold
  retorna o percentual; valor dentro/acima não retorna alerta; sem preço de mercado disponível
  não calcula (retorna None, não erro).
- T522 `imoveis/service.py`: emite `imovel_subprecificado` ao criar/atualizar imóvel com
  valor_anunciado abaixo do threshold. TDD: emite nos casos esperados; não emite sem
  valor_anunciado; não altera o registro do imóvel (puramente notificação).
- T523 Listener em `precos_mercado/listeners.py` publica no canal
  `tenant.{tenant_id}.notificacoes`. TDD (mesmo padrão de `test_notificacoes_ws.py`): conexão WS
  do tenant certo recebe; outro tenant nunca recebe.

## Bloco D — Mapa de calor
*Depende do Bloco A (só entradas geocodificadas aparecem).*
- T530 Contrato OpenAPI de `GET /precos-mercado/mapa-calor`.
- T531 TDD: `obter_mapa_calor`. Casos: só retorna entradas com lat/long preenchidos; entrada sem
  coordenada não aparece mas não quebra a resposta.
- T532 Endpoint `GET /precos-mercado/mapa-calor`.

## Bloco E — UI
- T540 [P] Adicionar `leaflet` + `leaflet.heat` ao `package.json` do bundle `corretor`.
- T541 [P] `MapaCalorView.vue`: mapa com pontos de calor por bairro/cidade (US3).
- T542 [P] Tela de importação de CSV (`admin`): upload + relatório de linhas
  importadas/atualizadas/erros (US1).
- T543 [P] Toast de "imóvel subprecificado" reaproveitando o `useNotificacoes` já existente
  (`App.vue`, 004-leads) — só adiciona o novo `tipo` de mensagem ao handler existente.

## Fechamento
- T550 Cobertura ≥80% no módulo `precos_mercado` (incluindo geocoding/import/mapa de calor).
- T551 Fluxo manual completo: importar CSV de exemplo → cadastrar imóvel abaixo do mercado →
  confirmar notificação em tempo real → abrir mapa de calor → tag **v0.6.0**.

**Dependências entre blocos:** A é pré-requisito de B, C e D. B/C/D paralelizam entre si depois
de A. E (UI) depende de B+C+D. Fechamento depende de A+B+C+D+E completos.
