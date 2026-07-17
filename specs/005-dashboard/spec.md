# Feature 005 — Dashboard Analítico

**Status:** Pronta para /speckit.clarify | **Fase do roadmap:** 5 | **Release alvo:** v0.5.0
**Fonte:** docs/ESPECIFICACAO-MASTER.md §4 (M7, RF007) | **Depende de:** 001-fundacao (imóveis),
004-leads (leads/pipeline)

## Resumo

Painel de métricas agregadas do tenant — sem novo domínio de escrita, só leitura/agregação
sobre `imoveis` e `leads` já existentes. Cartões de estado acionáveis primeiro, gráficos onde há
decisão a tomar (PADROES-DE-INTERFACE.md §6). **Atualização em tempo real fica fora de escopo**
(Decisão #4 da Especificação Master: o único evento em tempo real do MVP é notificação de novo
lead — feature 004; contadores de dashboard em tempo real ficam para fase futura, se houver
demanda). Nesta feature o dashboard atualiza ao carregar a página / botão de atualizar manual.

## Histórias de usuário (priorizadas)

**US1 (P0) — Cartões de estado acionáveis.** Como usuário do tenant, quero ver de imediato o
estado do meu negócio, para saber onde agir sem precisar navegar.
- AC1: cartões mostram total de imóveis por status, total de leads ativos (não terminais), taxa
  de conversão do período e ticket médio.
- AC2: cartão de "leads sem contato há mais de N dias" (estágio `novo` há mais de N dias, N
  configurável, padrão 3) linka diretamente para a listagem de leads já filtrada.
- AC3: `corretor` vê métricas só da própria carteira; `admin` vê o tenant inteiro.

**US2 (P0) — Vendas por mês.** Como `admin`, quero ver o volume de vendas por mês, para
identificar sazonalidade e comparar períodos.
- AC1: gráfico de barras/linha com contagem e valor total de imóveis vendidos por mês, últimos
  N meses (padrão 12, configurável via query param).
- AC2: mês sem venda aparece com valor zero (não é omitido do eixo do tempo).

**US3 (P0) — Leads por origem.** Como `admin`, quero ver de onde vêm meus leads, para saber
onde investir aquisição.
- AC1: gráfico com contagem de leads por origem no período selecionado.

**US4 (P0) — Taxa de conversão e tempo médio.** Como `admin`, quero ver a taxa de conversão de
leads e o tempo médio de venda, para identificar gargalos no funil (US-M7 da Especificação
Master).
- AC1: taxa de conversão = leads em estágio `fechado` / total de leads criados no período.
- AC2: tempo médio de fechamento de lead = média de dias entre criação do lead e o momento em
  que atingiu o estágio `fechado`.
- AC3: tempo médio de venda de imóvel = média de dias entre cadastro do imóvel e `data_venda`,
  para imóveis com status `vendido` no período.

**US5 (P1) — Drill-down simples.** Como usuário, quero clicar num cartão/métrica e ir direto ao
registro de origem, para investigar sem precisar refiltrar manualmente.
- AC1: cartões e legendas de gráfico linkam para a listagem já filtrada (imóveis ou leads)
  quando aplicável.

## Fora de escopo

Atualização em tempo real via WebSocket (decisão #4, fase futura) · exportação de dados do
dashboard (CSV/PDF) · métricas por corretor individual num painel comparativo de equipe (só
`admin` vê o tenant agregado, sem comparação nomeada entre corretores nesta fase) · metas/OKRs
configuráveis · previsão/projeção de vendas (IA, M9, fora de escopo desta feature).

## Regras de negócio críticas

- RN1: toda métrica é escopada ao tenant (Artigo I) — `corretor` vê só a própria carteira,
  `admin` vê o tenant inteiro; nenhuma agregação cruza tenants.
- RN2: mês sem dado aparece como zero na série temporal (não quebra o gráfico, não é omitido).
- RN3: `Lead.fechado_em` é preenchido automaticamente no momento em que o lead atinge o estágio
  `fechado` (nunca recalculado/retroativo) — é a base do tempo médio de fechamento (AC US4).
- RN4: agregações são calculadas sob demanda (query ao vivo), sem tabela de cache/pré-agregação
  nesta fase (Artigo VIII/YAGNI) — volume de dados do MVP não justifica a complexidade extra.

## Requisitos não funcionais aplicáveis

Artigo I (isolamento multi-tenant) · Artigo VIII (YAGNI — sem pré-agregação/cache prematuros) ·
RNF001 (API <500ms — agregações simples com `GROUP BY` sobre tabelas pequenas no MVP) · padrão
de interface "cartões de estado acionáveis primeiro, gráficos só onde há decisão a tomar"
(PADROES-DE-INTERFACE.md §6).
