# Feature 007 — Superadmin (Painel da Plataforma)

**Status:** Em planejamento | **Fase do roadmap:** 7 (Fase 4 do documento
`Proptech_Avaliador_Especificacao_v1.1.0.pdf` — "Multi-tenant e Superadmin [NOVA]") | **Release
alvo:** v0.7.0
**Fonte:** `Proptech_Avaliador_Especificacao_v1.1.0.pdf` §Fase 4 (p.21-22) | **Depende de:**
001-fundacao (isolamento multi-tenant, `Tenant`/`User`), 002-avaliacao, 004-leads,
005-dashboard, licenciamento (MRR/faturamento), auditoria (`audit_logs`)

## Resumo

A Fase 4 do documento descreve dois blocos: "Arquitetura Multi-Tenant" e "Painel Superadmin". O
primeiro **já está implementado** desde a 001-fundacao (isolamento por `tenant_id` via
`TenantScopedMixin`, subdomínio por tenant, planos com limites de usuários/imóveis) — não há
trabalho novo aí, exceto um gap encontrado durante o levantamento desta spec: `Tenant.status =
SUSPENDED` hoje é só um campo de leitura (setado pelo dunning de cobrança), **nada bloqueia
acesso de um tenant suspenso**. Esta feature fecha esse gap como parte da ação de suspensão.

O segundo bloco — Painel Superadmin — é 100% novo: um papel de plataforma, fora do modelo de
tenant, com visão consolidada cross-tenant (algo que o Artigo I deliberadamente nunca permitiu
para usuários normais). Decisão de arquitetura (confirmada com o dono do produto): o superadmin
**não pertence a nenhum tenant** — conta própria (`superadmin_users`), login próprio, token JWT
próprio sem `tenant_id`, dependency própria (`require_superadmin`), nunca reaproveita
`tenancy.User`/`Papel`.

## Histórias de usuário (priorizadas)

**US1 (P0) — Login do superadmin.** Como dono da plataforma, quero logar num painel separado do
login de imobiliária, para acessar dados cross-tenant sem me passar por um tenant.
- AC1: `POST /admin/auth/login` (email+senha) retorna um access token cujo payload não contém
  `tenant_id` e tem `papel=superadmin`; nunca aceito por nenhuma rota tenant-scoped existente.
- AC2: um token de tenant (`papel=admin`/`corretor`) é rejeitado com 401/403 em toda rota
  `/admin/*` desta feature, e vice-versa (token de superadmin não abre rota de tenant).
- AC3: conta de superadmin é provisionada por variável de ambiente no boot (`SUPERADMIN_EMAIL`/
  `SUPERADMIN_PASSWORD`), idempotente — sem endpoint de auto-cadastro público (mesmo racional de
  não existir um "vire admin" público no modelo de tenant).

**US2 (P0) — Dashboard consolidado da plataforma.** Como dono da plataforma, quero ver total de
tenants por status, MRR e uso agregado, para entender a saúde do negócio de relance.
- AC1: `GET /admin/uso/plataforma` retorna contagem de tenants por `TenantStatus`
  (trial/active/past_due/suspended/cancelled) e totais agregados (usuários, imóveis, leads,
  avaliações) somados de todos os tenants.
- AC2: `GET /admin/faturamento/consolidado` retorna MRR (soma de `License.preco_congelado` das
  licenses `ACTIVE`), receita paga no mês corrente (soma de `Invoice.valor` com status `PAID` no
  ciclo atual) e contagem de invoices por status.

**US3 (P0) — Detalhe e ranking de tenants.** Como dono da plataforma, quero listar todos os
tenants com uso individual, para identificar quem está perto do limite do plano ou inativo.
- AC1: `GET /admin/tenants` lista todos os tenants (nome, slug, status, plano, criado em),
  paginado, sem qualquer filtro de tenant (cross-tenant por natureza — usa `system_scope()`).
- AC2: `GET /admin/tenants/{id}/metricas` retorna uso individual do tenant (usuários ativos,
  imóveis ativos, leads, avaliações no mês) e dados da license (plano, status, próximo
  vencimento).

**US4 (P0) — Suspensão/reativação manual de tenant.** Como dono da plataforma, quero suspender
ou reativar um tenant manualmente (ex.: abuso, solicitação de cancelamento, inadimplência fora
do fluxo automático de dunning), com efeito imediato de bloqueio de acesso.
- AC1: `POST /admin/tenants/{id}/suspender` marca `Tenant.status = SUSPENDED`; a partir desse
  momento, **qualquer requisição autenticada de um usuário daquele tenant recebe 403** (fecha o
  gap descrito no Resumo) — verificado em `get_current_user` (Artigo I: verificação central, não
  espalhada por router).
- AC2: `POST /admin/tenants/{id}/reativar` marca `Tenant.status = ACTIVE` e o acesso volta
  imediatamente, sem precisar de novo login.
- AC3: as duas ações geram entrada em `audit_logs` do tenant afetado (`ator_user_id=None`,
  `acao="tenant_suspenso_por_superadmin"`/`"tenant_reativado_por_superadmin"`) — auditável mesmo
  sendo uma ação de fora do tenant.

**US5 (P1) — Auditoria centralizada.** Como dono da plataforma, quero consultar logs de
auditoria de qualquer tenant num só lugar, para investigar incidentes sem precisar de acesso ao
banco.
- AC1: `GET /admin/auditoria/logs` retorna logs paginados de todos os tenants (via
  `system_scope()`), filtráveis por `tenant_id`, `acao` e intervalo de data.
- AC2: somente leitura — superadmin nunca cria/edita/apaga entradas de auditoria (append-only
  vale também cross-tenant).

**US6 (P1) — Painel (frontend).** Como dono da plataforma, quero uma UI própria para as US1-US5,
separada do app de corretor/imobiliária.

## Fora de escopo

**Sistema de tickets de suporte** — feature própria de tamanho comparável a esta inteira
(modelo de dados, fluxo de atendimento, notificação); fica para uma spec dedicada. ·
**Rate limiting por tenant** — é uma preocupação de infraestrutura (proxy/gateway), não de
código de aplicação; melhor resolvida no nginx/reverse proxy de produção do que replicada em
Python. · **Backup isolado por tenant (export)** — feature própria de exportação de dados, com
suas próprias questões de formato/streaming/tamanho de arquivo. · **Gestão de planos/preços via
UI (CRUD)** — hoje `Plan` é seed fixo (`PLAN_SEED`); esta feature só **lê** planos existentes,
CRUD fica para quando houver necessidade real de mudar preços sem deploy. · **Customização de
logo/cores/nome por tenant (white-label)** — já não fazia parte de nenhuma feature anterior,
segue fora. · **2FA para o superadmin** — o modelo de tenant tem TOTP para admin
(`require_admin_with_2fa`); o superadmin, sendo uma conta única/poucas contas de uso interno,
fica só com email+senha nesta v1 — risco aceito e documentado, não esquecido (ver Riscos no
plan.md). · **Refresh token para superadmin** — só access token (expiração curta, ~60min);
sessão expira e exige novo login, sem rotação — simplificação aceitável para painel de uso
interno pouco frequente.

## Regras de negócio

- **RN1 (isolamento invertido):** toda leitura desta feature que atravessa tenants **precisa**
  usar `system_scope()` explicitamente — é a única parte do sistema autorizada a fazer isso por
  requisição de usuário final (até aqui `system_scope()` só era usado por jobs de sistema como o
  dunning).
- **RN2 (bloqueio por suspensão):** `Tenant.status == SUSPENDED` bloqueia toda rota autenticada
  tenant-scoped (401/403), independente de `User.ativo` — hoje só `User.ativo` é checado.
- **RN3 (papéis nunca se misturam):** um token com `papel=superadmin` nunca é aceito por
  `get_current_user`/`require_admin` (rotas de tenant); um token de tenant nunca é aceito por
  `require_superadmin`. Verificado por teste cruzado (US1/AC2).
- **RN4 (MRR):** MRR = soma de `License.preco_congelado` de todas as licenses com
  `status=ACTIVE` (preço já congelado no momento da contratação — não recalcula pelo preço atual
  do plano).
