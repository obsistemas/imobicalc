# Plano de Implementação — Feature 006: Dados de Mercado

**Spec:** ./spec.md | **Constitution Check:** ✅ — uma dependência nova de frontend
(`leaflet` + `leaflet.heat`, mapa de calor — leve, sem chave de API, amplamente adotada).
Backend não ganha dependência nova: geocodificação via `httpx` (já usado pelo `ViaCepDriver`)
contra a API pública do Nominatim/OpenStreetMap (sem SDK, sem chave).

## Contexto técnico

Estende `backend/app/modules/precos_mercado` (geocodificação + import CSV + endpoint de mapa de
calor) e `backend/app/modules/imoveis/service.py` (emite o evento de subprecificação ao
criar/atualizar). Novo listener em `precos_mercado/listeners.py` (reaproveita o canal WS de
004-leads via `notificacoes`). Frontend: nova view de mapa de calor + tela de importação CSV no
bundle `corretor` existente.

## Pontos de design

1. **Geocodificação via Nominatim, mesmo padrão de driver do `ViaCepDriver`:** `Protocol` +
   implementação real (HTTP contra `nominatim.openstreetmap.org`) + fake para testes, igual ao
   já validado em 001-fundacao. *Por quê:* consistência com o padrão já estabelecido no projeto
   (ARQUITETURA-REFERENCIA.md §5); Nominatim é gratuito, sem chave, suficiente para geocodificar
   bairro+cidade (não precisa de precisão de endereço exato). *Alternativa rejeitada:* Google
   Geocoding API — exige chave paga, contraria RNF009 (custo controlado) e Artigo VIII.

2. **Import CSV com `csv` da stdlib, sem biblioteca de planilha:** parse linha a linha,
   validação e erro por linha, sem `pandas`/`openpyxl`. *Por quê:* YAGNI — o volume esperado
   (algumas centenas de linhas, curadoria manual/mensal) não justifica uma dependência pesada
   como pandas só para ler CSV; `csv.DictReader` da stdlib já resolve. *Alternativa rejeitada:*
   `pandas` — dependência grande e com sua própria superfície de bugs para um parse simples.

3. **Alerta via evento in-process, não polling nem job agendado:** a comparação acontece
   síncrona, dentro da mesma transação de criar/atualizar o imóvel — reaproveita `emit()` já
   usado por `lead_criado`. *Por quê:* mesmo racional de 004-leads (Decisão #4 da Especificação
   Master: só notificação de lead é tempo real no MVP — esta feature estende o mesmo mecanismo
   já validado, não cria um segundo caminho de "tempo real"). *Alternativa rejeitada:* job
   periódico varrendo todos os imóveis — mais complexo, exigiria infra de scheduler que o
   projeto ainda não tem (RQ Scheduler existe como dependência mas sem entrypoint configurado).

4. **`preco_mercado` geocodificado, não `imovel`:** só a tabela central de preços ganha
   lat/long; imóveis individuais continuam sem coordenada. *Por quê:* o mapa de calor (US3) é
   sobre preço regional agregado, não sobre imóveis específicos — geocodificar todo imóvel
   cadastrado seria trabalho e chamada de rede extra sem uso nesta feature (Artigo VIII).
   *Alternativa rejeitada:* geocodificar imóvel também — adiado para quando houver uma feature
   que realmente precise de mapa por imóvel (ex.: busca por proximidade).

## Fases

**P1 — Geocodificação + schema**
Migration `preco_mercado.latitude/longitude`. `GeocodingDriver` (Protocol + Nominatim + Fake).
TDD: geocodificação bem-sucedida preenche lat/long; falha/timeout deixa nulo sem quebrar o
fluxo chamador.

**P2 — Importação CSV**
`POST /admin/precos-mercado/importar` (multipart, admin-only). TDD: upsert por bairro+cidade+
tipo; linha malformada reportada sem interromper as demais; geocodificação best-effort por
linha.

**P3 — Alerta de subprecificação**
Comparação em `imoveis/service.py` (criar/atualizar) + listener em `precos_mercado/listeners.py`
publicando no canal já existente. TDD: abaixo do threshold emite; acima não; sem preço de
mercado ou sem valor_anunciado não emite (nunca erro).

**P4 — Mapa de calor**
`GET /precos-mercado/mapa-calor` (só pontos com coordenada). UI: `MapaCalorView.vue` com
Leaflet + Leaflet.heat.

**P5 — UI de importação**
Tela de upload de CSV para `admin`, com relatório de linhas importadas/erros.

## Riscos

| Risco | Mitigação |
|---|---|
| Nominatim tem rate limit agressivo (1 req/s documentado) | Import processa linhas sequencialmente (não paralelo); volume esperado (curadoria mensal, centenas de linhas) é compatível |
| CSV com encoding/separador diferente do esperado | Detecção simples de delimitador (`,` ou `;`) documentada na tela de importação; linha ilegível cai no relatório de erro, não quebra o restante |
| Geocodificação imprecisa para bairros com nome ambíguo | Aceitável para mapa de calor regional (não precisa de precisão de endereço); documentado como limitação conhecida |

## Critério de conclusão

ACs de US1-US3 verdes · geocodificação nunca bloqueia import/cadastro em nenhum teste (best
effort confirmado) · alerta de subprecificação testado ponta a ponta via WebSocket (reaproveita
o padrão de teste já validado em `test_notificacoes_ws.py`) · cobertura ≥80% no módulo · fluxo
manual: importar CSV de exemplo → cadastrar imóvel abaixo do mercado → confirmar notificação em
tempo real → abrir mapa de calor e ver os pontos → tag **v0.6.0**.
