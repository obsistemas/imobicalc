# Tasks — Feature 004: Gestão de Leads / Pipeline + Notificação em Tempo Real

Formato: `T3## [P?] [US?] descrição` — [P] = paralelizável. Cada task termina com testes verdes +
commit convencional. Numeração: feature 004 usa T3xx.

## Bloco A — Migration + Models
- T300 Migration + Models: `leads`, `leads_notas` (tenant-scoped, `TenantScopedMixin`).

## Bloco B — Service/Router de Leads (CRUD + pipeline + notas)
- T310 TDD: `criar_lead`. Casos: `imovel_id` nulo aceito; `imovel_id` de outro tenant retorna 404;
  emite evento `lead_criado` com os dados corretos.
- T311 TDD: `mover_estagio`. Casos: transição livre entre não-terminais; transição a partir de
  `fechado`/`perdido` rejeitada (422); gera `LeadNota` automática de/para.
- T312 TDD: `adicionar_nota` / `listar_notas`. Casos: nota manual (`automatica=False`); ordenação
  por data.
- T313 TDD: `listar_leads`. Casos: `corretor` só vê os próprios; `admin` vê todos; filtro por
  estágio/origem.
- T314 Teste de isolamento de tenant obrigatório (`assert_tenant_isolated`) para `leads` e
  `leads_notas` (Artigo I, gate de CI).

## Bloco C — WebSocket de Notificação
*Depende do Bloco B (evento `lead_criado` precisa existir).*
- T320 `app/modules/notificacoes/router.py`: endpoint `GET /ws/notificacoes?token=...`, autentica
  via JWT, assina canal `tenant.{tenant_id}.notificacoes`.
- T321 `leads/listeners.py`: publica no canal do tenant ao receber `lead_criado`; registrado em
  `main.py`.
- T322 TDD: conexão WS recebe a notificação de um lead criado no mesmo tenant; conexão de outro
  tenant nunca recebe a mensagem (isolamento também no canal de tempo real).

## Bloco D — UI
- T330 [P] `LeadsListView.vue`: lista com filtro por estágio/origem.
- T331 [P] `LeadFormView.vue`: criação de lead (imóvel opcional).
- T332 [P] `LeadDetailView.vue`: transição de estágio + notas (manuais e automáticas visíveis
  juntas, ordenadas por data).
- T333 Composable `useNotificacoes` (conexão WS + reconexão simples) + toast de "novo lead" a
  partir de `App.vue`.

## Fechamento
- T340 Cobertura ≥80% no módulo `leads`.
- T341 Fluxo manual completo: cadastrar lead → notificação em tempo real aparece → mover pelo
  pipeline → registrar nota → tag **v0.4.0**.

**Dependências entre blocos:** A é pré-requisito de B. C depende de B (evento `lead_criado`). D
depende de B+C. Fechamento depende de A+B+C+D completos.
