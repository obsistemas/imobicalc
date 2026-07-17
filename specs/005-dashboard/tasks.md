# Tasks — Feature 005: Dashboard Analítico

Formato: `T4## [P?] [US?] descrição` — [P] = paralelizável. Cada task termina com testes verdes +
commit convencional. Numeração: feature 005 usa T4xx.

## Bloco A — Migration
- T400 Migration + alteração de model: `leads.fechado_em` (datetime, nullable); `mover_estagio`
  (004-leads) passa a setar `fechado_em = now()` quando `novo_estagio == FECHADO`. TDD: mover para
  `fechado` preenche `fechado_em`; mover para qualquer outro estágio não altera `fechado_em`.

## Bloco B — Service de agregação
*Depende de T400 (tempo médio de fechamento usa `fechado_em`).*
- T410 TDD: preenchimento de série temporal de N meses (função pura). Casos: mês sem venda entra
  como zero; série sempre tem exatamente N pontos; funciona corretamente na virada de ano
  (dezembro→janeiro).
- T411 TDD: `obter_resumo` (cartões). Casos: `corretor` só agrega a própria carteira, `admin`
  agrega o tenant inteiro; `taxa_conversao` retorna `0` (não erro) sem leads no período;
  `ticket_medio`/`tempo_medio_venda_imovel` retornam `null` (não `0`) sem venda no período;
  `leads_sem_contato` respeita o parâmetro `dias_sem_contato`.
- T412 TDD: `obter_vendas_por_mes`. Casos: quantidade e valor total corretos por mês; mês sem
  venda com zero (reforça T410 integrado à query real).
- T413 TDD: `obter_leads_por_origem`. Casos: contagem correta por origem; origem sem lead no
  período não aparece na resposta.
- T414 Teste de isolamento de tenant (`assert_tenant_isolated` ou equivalente) confirmando que
  nenhuma métrica soma dado de outro tenant (Artigo I).

## Bloco C — Endpoints
- T420 `GET /dashboard/resumo?dias_sem_contato=&meses=` — contrato OpenAPI antes da rota.
- T421 `GET /dashboard/vendas-por-mes?meses=`.
- T422 `GET /dashboard/leads-por-origem?meses=`.

## Bloco D — UI
- T430 [P] Adicionar `chart.js`+`vue-chartjs` ao `package.json` do bundle `corretor`.
- T431 [P] `DashboardView.vue`: cartões de estado com link de drill-down (US1, US5).
- T432 [P] Gráfico de vendas por mês (US2) e gráfico de leads por origem (US3), com seletor de
  período e botão de atualizar manual.
- T433 [P] Link "Dashboard" no menu (`HomeView.vue`), visível para `admin` e `corretor` (com
  escopo de dados diferente conforme RN1).

## Fechamento
- T440 Cobertura ≥80% no módulo `dashboard`.
- T441 Fluxo manual completo: cadastrar imóveis/leads variados (incluindo vendas em meses
  diferentes e leads de origens diferentes) → abrir dashboard → conferir cartões e gráficos
  batem com os dados cadastrados → tag **v0.5.0**.

**Dependências entre blocos:** A é pré-requisito de B (tempo médio de fechamento). B é
pré-requisito de C. C é pré-requisito de D. Fechamento depende de A+B+C+D completos.
