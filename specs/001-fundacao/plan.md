# Plano de Implementação — Feature 001: Fundação

**Spec:** ./spec.md | **Constitution Check:** ✅ — novas dependências (primeira feature, base técnica inteira é nova):
`fastapi`, `sqlalchemy[asyncio]`, `alembic`, `psycopg[binary]`, `pydantic-settings`, `pyjwt`, `passlib[bcrypt]`, `pyotp` (2FA TOTP), `redis`, `rq` + `rq-scheduler` (dunning agendado), `mercadopago` (SDK oficial), `httpx` (ViaCEP), `structlog`, `pytest`/`pytest-asyncio`/`pytest-cov`, `ruff`, `mypy`. Justificativa: conjunto mínimo para cumprir Artigos I, III, V, VII da constituição — nenhuma biblioteca substitui decisão de domínio, todas são infraestrutura já prevista em ARQUITETURA-REFERENCIA.md.

## Contexto técnico

Módulos criados (todos novos, é a feature fundacional): `backend/app/modules/tenancy` (tenants, users, convites, auth, 2FA), `backend/app/modules/licenciamento` (plans, licenses, invoices, payment_events, webhook Mercado Pago, dunning), `backend/app/modules/imoveis` (CRUD + filtros). Bundle frontend: `frontend/apps/corretor` — apenas as telas mínimas desta feature (signup, login, setup 2FA, convite, upgrade de plano, cadastro/listagem de imóvel). Reuso: nenhum, é a base para as próximas features (avaliação, leads, dashboard, preço de mercado) consumirem tenant/auth/licenciamento prontos.

## Pontos de design

1. **Autenticação stateless com JWT curto + refresh em cookie httpOnly:** access token (15 min, carrega `tenant_id`+`papel`) e refresh token (7 dias, cookie httpOnly/secure). *Por quê:* reduz superfície de XSS comparado a guardar token em localStorage, mantém backend stateless (Artigo do blueprint de escalabilidade horizontal). *Alternativa rejeitada:* sessão server-side pura — mais estado, dificulta escalar múltiplas instâncias do backend.

2. **Isolamento de tenant via contextvar + listener SQLAlchemy, não filtro manual:** `IdentifyTenantMiddleware` resolve o tenant (JWT ou subdomínio) e seta um `contextvars.ContextVar`; um listener `do_orm_execute` do SQLAlchemy aplica `WHERE tenant_id = :ctx` automaticamente em todo `Select`. *Por quê:* Artigo I exige que seja impossível esquecer o filtro — automatizar no nível do ORM elimina a classe inteira de erro "esqueci o `.filter(tenant_id=...)`". *Alternativa rejeitada:* filtro manual em cada query/service — funciona, mas um único `service` esquecido vaza dado entre tenants.

3. **2FA via TOTP (pyotp) + recovery codes, sem SMS:** `admin` configura um app autenticador (Google Authenticator/Authy) via QR code; 10 recovery codes de uso único gerados no setup, armazenados com hash. *Por quê:* SMS tem custo recorrente e dependência de provedor externo não decidida; TOTP é padrão, gratuito, sem infra extra. *Alternativa rejeitada:* SMS OTP — mais familiar ao usuário leigo, mas custo/complexidade não justificados no MVP.

4. **Enforcement de limite de plano com lock pessimista:** ao criar usuário/imóvel, a transação faz `SELECT ... FOR UPDATE` na linha de `licenses` do tenant antes do `COUNT` + `INSERT`. *Por quê:* RN3 exige que o limite nunca seja ultrapassado mesmo sob concorrência (duas abas criando imóvel ao mesmo tempo perto do limite). *Alternativa rejeitada:* `COUNT` sem lock antes do insert — sujeito a race condition clássica (TOCTOU).

5. **Idempotência de webhook via tabela `payment_events` com unique constraint:** o `event_id` do Mercado Pago é chave natural única; o handler insere o evento antes de aplicar qualquer efeito colateral (ativar tenant, marcar fatura paga) — se a inserção falhar por duplicidade, retorna 200 sem reprocessar. *Por quê:* RN5, webhooks são reentregues pelo gateway em caso de timeout. *Alternativa rejeitada:* deduplicar em memória/cache — não sobrevive a restart do worker, risco de duplo processamento.

6. **Dunning como job agendado (RQ Scheduler) rodando à meia-noite America/Sao_Paulo:** um job diário varre licenças e aplica a transição de estado devida (RN6), idempotente (recalcula o estado esperado a partir de `trial_termina_em`/`invoices` em vez de incrementar contador). *Por quê:* evita interromper o corretor no meio do expediente (regra do blueprint) e sobrevive a atraso/reinício do worker sem duplicar efeito. *Alternativa rejeitada:* transição síncrona disparada por request do usuário — imprevisível, foge da regra de "sempre à meia-noite".

7. **Resolução de subdomínio com cache Redis (host→tenant_id):** `IdentifyTenantMiddleware` lê o `Host` header, consulta cache Redis (TTL curto), fallback no Postgres em cache miss. *Por quê:* evita 1 query extra por request no caminho crítico. *Alternativa rejeitada:* resolver tenant só pelo JWT (sem subdomínio) — mais simples, mas contraria US10/decisão de acesso por subdomínio da especificação master.

## Fases

**P1 — Tenancy + Auth (semana 1-2)**
Models `tenants`/`users`, signup (US1), login/JWT/refresh (US2), middleware de isolamento (US5) com teste `assert_tenant_isolated`, resolução por subdomínio (US10). Contrato OpenAPI dos endpoints de auth primeiro.

**P2 — 2FA + Convites (semana 2-3)**
Setup/verify TOTP + recovery codes (US3), fluxo de convite por e-mail + aceite (US4), enforcement de `max_users` com lock (RN3, parte de US4).

**P3 — Licenciamento e Cobrança (semana 3-5)**
Models `plans`/`licenses`/`invoices`/`payment_events`, checkout inicial (trial sem cartão), integração Mercado Pago (checkout + webhook idempotente, US8), enforcement de `max_imoveis` (RN3), job de dunning agendado (US9). TDD obrigatório aqui (Artigo III, 100% caminhos de dinheiro) antes de qualquer UI.

**P4 — Cadastro de Imóveis (semana 5-6)**
Model `imoveis`, integração ViaCEP síncrona com fallback manual (US6), CRUD + filtros/paginação (US6, US7), telas de formulário e listagem no frontend.

## Riscos

| Risco | Mitigação |
|---|---|
| Webhook do Mercado Pago atrasa ou nunca chega | Job de reconciliação diário que confere faturas `pending` vencidas direto na API do Mercado Pago, além do webhook |
| Bug de isolamento vaza dado entre tenants | Teste de isolamento obrigatório (Artigo I) bloqueia merge no CI; listener automático no ORM reduz superfície de erro humano |
| Admin perde acesso ao 2FA (trocou de celular) | Recovery codes gerados no setup, guardados com hash, uso único |
| Race condition no limite de plano sob carga | Lock pessimista (`SELECT FOR UPDATE`) na license durante criação de recurso |
| Trial sem cartão gera baixa conversão/inadimplência silenciosa | Métrica simples de conversão trial→pago monitorada desde o dia 1 (log estruturado + consulta manual, sem dashboard dedicado nesta feature) |
| Job de dunning falha silenciosamente (worker caiu à meia-noite) | Job idempotente por design (recalcula estado esperado, não incrementa) — reexecução tardia corrige o estado sem duplicar efeito |

## Critério de conclusão

Todos os ACs de US1-US10 verdes em staging · cobertura ≥80% geral nos módulos desta feature e 100% nos caminhos de dinheiro (cálculo de fatura, aplicação de plano, webhook — Artigo III) · teste de isolamento de tenant passando no CI (Artigo I) · fluxo manual completo testado em staging: signup → trial 7 dias (simulado) → 2FA → convite de corretor → cadastro de imóvel até o limite do plano (bloqueio confirmado) → pagamento via sandbox Mercado Pago → dunning simulado (adiantando `trial_termina_em` em ambiente de teste) → tag **v0.1.0**.
