# Plano de Implementação — Feature 005: Dashboard Analítico

**Spec:** ./spec.md | **Constitution Check:** ✅ com uma dependência nova: `chart.js` +
`vue-chartjs` (renderização de gráficos) — primeira necessidade de visualização gráfica do
projeto; biblioteca leve (canvas, sem servidor/licença), amplamente adotada, sem alternativa já
presente no stack. Backend não ganha dependência nova (agregação via SQLAlchemy/`func` puro).

## Contexto técnico

Módulo novo `backend/app/modules/dashboard` — só leitura, sem models próprios (lê `imoveis` e
`leads` de outros módulos) e sem router de escrita. Uma migration pequena em `leads`
(`fechado_em`). Frontend: `DashboardView.vue` (novo), reaproveita `api/client.js` existente;
adiciona os dois pacotes de gráfico ao `frontend/apps/corretor/package.json`.

## Pontos de design

1. **Sem tabela de cache/pré-agregação (RN4/Artigo VIII):** cada métrica é uma query SQL direta
   com `func.count`/`func.avg`/`func.sum` + `GROUP BY`, calculada a cada request. *Por quê:*
   volume de dados por tenant no MVP (dezenas/centenas de imóveis e leads, não milhões) não
   justifica a complexidade de invalidação de cache; adicionar isso agora seria otimização
   prematura. *Alternativa rejeitada:* tabela `dashboard_snapshot` recalculada por job — reintroduz
   o problema de estado assíncrono (dado desatualizado) que o resto do produto evita.

2. **Série temporal preenchida no código, não só no SQL:** a query de "vendas por mês" retorna
   só os meses com venda; o serviço completa os meses faltantes com zero em Python antes de
   devolver a resposta. *Por quê:* RN2 exige que a série sempre tenha N pontos (gráfico de linha/
   barra não pode "pular" um mês sem venda) — fazer isso em SQL puro (ex.: `generate_series`)
   funciona só em Postgres, quebra os testes que usam SQLite; preencher em Python funciona nos
   dois bancos sem duplicar lógica de datas entre dialetos. *Alternativa rejeitada:*
   `generate_series` do Postgres — acopla o código a um dialeto específico sem necessidade.

3. **`fechado_em` denormalizado em `leads`, não derivado de `leads_notas`:** ao mover um lead
   para `fechado`, o service já grava `fechado_em = now()` na própria linha, em vez de a query de
   dashboard procurar a nota automática de transição por texto. *Por quê:* string-matching em
   `leads_notas.texto` para achar "quando fechou" é frágil (quebra se o texto da nota mudar) e
   lento (scan de texto em vez de comparação de coluna indexável); um campo dedicado é a mesma
   lição de `licenses.trial_termina_em`/`invoices.pago_em` já aplicada em 001/002. *Alternativa
   rejeitada:* parsear `leads_notas` — acopla uma métrica de negócio ao texto de uma nota
   pensada para leitura humana.

4. **Sem WebSocket/tempo real (decisão #4 já tomada):** dashboard só atualiza no carregamento da
   página ou botão "Atualizar" manual. *Por quê:* já decidido na Especificação Master antes desta
   feature — não é uma escolha de implementação, é escopo já fechado. *Alternativa rejeitada:*
   nenhuma — fora de escopo por decisão anterior, não por análise técnica desta feature.

5. **Visibilidade por papel replicada da regra de `imoveis`/`leads`:** `corretor` vê métricas só
   da própria carteira (filtro `corretor_id`), `admin` vê o tenant inteiro — mesmo padrão já
   implementado nos dois módulos de origem dos dados, sem introduzir uma regra de RBAC nova.

## Fases

**P1 — Migration `leads.fechado_em`**
Migration expand-only (Artigo VI) adicionando a coluna nullable; `mover_estagio` (004-leads)
passa a setar `fechado_em` quando `novo_estagio == FECHADO`.

**P2 — Service de agregação (funções puras de composição de query + 1 função de preenchimento
de série temporal)**
TDD nas funções de cálculo de período/preenchimento de meses faltantes (lógica de data é fácil
de errar em borda de mês/ano — mesmo racional de rigor usado no motor de avaliação, por analogia).

**P3 — Endpoints**
`GET /dashboard/resumo`, `GET /dashboard/vendas-por-mes`, `GET /dashboard/leads-por-origem` —
todos `GET`, autenticados, sem parâmetro de escrita.

**P4 — UI**
`DashboardView.vue`: cartões de estado no topo (com link de drill-down), gráfico de vendas por
mês, gráfico de leads por origem, seletor de período (meses) e botão de atualizar manual.

## Riscos

| Risco | Mitigação |
|---|---|
| Query de agregação lenta conforme a base cresce | Volume do MVP é pequeno; se necessário no futuro, adicionar índice em `data_venda`/`fechado_em` é mudança isolada, sem quebrar contrato |
| `ticket_medio`/`tempo_medio_venda` sem dado no período confundido com zero | Serializados como `null` explícito no contrato, distinto de `0` (RN da spec) |
| Nova dependência de gráfico aumenta bundle do frontend | `chart.js` é leve (~200KB) e carregado só na rota do dashboard, sem impacto nas demais telas |

## Critério de conclusão

ACs de US1-US5 verdes · `fechado_em` populado corretamente em testes de transição de estágio
(reforça 004-leads) · isolamento por tenant e por papel testado (Artigo I) · mês sem venda
aparece como zero na série (teste automatizado) · fluxo manual: criar imóveis/leads variados →
abrir dashboard → conferir cartões e gráficos batem com os dados → tag **v0.5.0**.
