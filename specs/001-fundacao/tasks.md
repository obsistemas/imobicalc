# Tasks — Feature 001: Fundação (Tenancy + Licenciamento + Cadastro de Imóveis)

Formato: `T### [P?] [US?] descrição` — [P] = paralelizável. TDD obrigatório em **todos** os blocos desta feature (fundação + Artigo III da constituição: 100% de cobertura nos caminhos de dinheiro, ≥80% no restante); teste descrito na própria task. Cada task termina com testes verdes + commit convencional. Numeração: feature 001 usa T0xx.

## Bloco A — Tenancy, Auth, Isolamento, Subdomínio (US1, US2, US5, US10)
- T000 [US1][US2] Revisar/ajustar contrato OpenAPI dos endpoints de auth (`contracts/openapi.yaml` já rascunhado — validar contra os schemas Pydantic finais).
- T001 [US1][US2][US5] Migrations + Models: `tenants`, `users`, com `TenantScopedMixin` (base SQLAlchemy que injeta `tenant_id` + participa do listener de isolamento).
- T002 [US5] TDD: listener `do_orm_execute` de isolamento de tenant + helper `assert_tenant_isolated`. Casos: query direta em `users` sem contexto de tenant levanta erro; query com contexto A não retorna linha de tenant B; job assíncrono (RQ) restaura o contextvar corretamente a partir do `tenant_id` serializado.
- T003 [US1] TDD: `POST /auth/signup` cria `tenant` (status `trial`) + `user` admin. Casos: e-mail já usado por outro tenant retorna 409; `trial_termina_em = created_at + 7 dias`; senha é armazenada com hash (nunca em texto plano, nem em log).
- T004 [US2] TDD: `POST /auth/login` e `/auth/refresh`. Casos: senha errada retorna 401 com mensagem genérica (não revela se o e-mail existe); access token expira em 15 min; refresh token rotaciona a cada uso; refresh revogado após `/auth/logout`.
- T005 [P] [US1][US2][US10] `IdentifyTenantMiddleware`: resolve tenant via JWT (rotas autenticadas) e via subdomínio (`Host` header, rotas públicas como `/auth/signup`), seta o contextvar consumido pelo listener de T002.
- T006 [US10] TDD: resolução por subdomínio com cache Redis (host→tenant_id). Casos: cache hit; cache miss cai para consulta no Postgres e populaciona o cache; subdomínio inexistente retorna 404.
- T007 [P] [US1][US2] UI: telas de Signup e Login (`frontend/apps/corretor`) — após a API dos itens acima estar de pé.
- T008 [P] Infra: healthcheck `/health` (status Postgres + Redis), inicialização do Sentry e `structlog` configurado para nunca logar dado sensível (senha, token, PII de lead) — Artigo XI da constituição. Smoke test cobrindo `/health`.

## Bloco B — 2FA e Convites (US3, US4)
*Depende do Bloco A (users/auth prontos). T034 depende de T050 (Bloco C) para validar `max_users`.*
- T030 [US3] Migration: colunas `totp_secret` (encrypted), `totp_enabled`, `totp_recovery_codes` (encrypted json) em `users`.
- T031 [US3] TDD: `POST /auth/2fa/setup` e `/auth/2fa/verify` com `pyotp`. Casos: código TOTP correto ativa 2FA e gera 10 recovery codes (armazenados com hash); código errado não ativa; recovery code é aceito uma única vez e depois invalidado.
- T032 [US3] Dependency FastAPI `requires_2fa()` aplicada às rotas administrativas sensíveis (`/users/convites`, `/license/upgrade`, `/invoices`).
- T033 [US4] Migration + Model: `convites`.
- T034 [US4] TDD: `POST /users/convites`. Casos: convite expira em 7 dias; bloqueado com 403 se `admin` não tem 2FA ativo (T032); bloqueado com 402 se `COUNT(users ativos) >= max_users` do plano vigente (requer T050 para `licenses`/`plans` existirem); e-mail com convite pendente não gera duplicata.
- T035 [US4] TDD: `POST /convites/{token}/aceitar`. Casos: token válido ativa usuário `corretor` e retorna sessão (mesmo formato de `AuthResponse`); token expirado ou já aceito retorna 410.
- T036 [P] [US3][US4] UI: tela de setup de 2FA (QR code + lista de recovery codes para o usuário salvar) e fluxo de convite/aceite.

## Bloco C — Licenciamento e Cobrança (US8, US9)
*Depende do Bloco A. Domínio crítico — TDD com 100% de cobertura nos caminhos de dinheiro (Artigo III), sem exceção.*
- T050 [US8] Migrations + Models: `plans` (com seed dos 3 planos — Solo/Pro/Enterprise, valores da Especificação Master §9), `licenses`, `invoices`, `payment_events`.
- T051 [US8] TDD: aplicação do plano no signup. Casos: `license` criada com `preco_congelado = plan.preco_mensal` no momento do cadastro; status inicial `trial`.
- T052 [US8] `MercadoPagoDriver` (Protocol + implementação): criar cobrança recorrente, verificar assinatura de webhook. Testado com fake driver (sem chamar API real nos testes unitários).
- T053 [US8] TDD: enforcement de `max_users`/`max_imoveis` com lock pessimista (`SELECT ... FOR UPDATE` na `license`). Casos: duas criações simultâneas perto do limite — teste de concorrência com sessões paralelas — nunca ultrapassam o limite; upgrade de plano libera o limite imediatamente para a próxima criação.
- T054 [US8] TDD: `POST /webhooks/mercadopago` idempotente. Casos: mesmo `event_id` processado duas vezes só aplica efeito (marcar fatura paga, reativar tenant) uma vez; evento com assinatura inválida é rejeitado sem efeito; evento desconhecido é armazenado mas não altera estado.
- T055 [US8] TDD: fatura paga reativa o tenant automaticamente (`trial`/`past_due` → `active`), sem intervenção manual.
- T056 [US9] Job RQ Scheduler de dunning, agendado para meia-noite `America/Sao_Paulo`, recalculando o estado esperado de cada `license` a partir de `trial_termina_em`/`invoices.vencimento` (não incrementa contador).
- T057 [US9] TDD: régua de dunning. Casos: trial expirado sem pagamento vira `past_due`; `past_due` há N dias configuráveis vira `suspended`; tenant `suspended` continua respondendo aos endpoints de exportação de dados; execução do job atrasada ou repetida no mesmo dia não duplica efeito (idempotência por recálculo).
- T058 [P] [US8] UI: tela de planos/upgrade e histórico de faturas (admin).
- T059 [US8] Auditoria de escrita sensível (Artigo VII): registro (quem/quê/quando/antes/depois) em toda mudança de plano e toda transição de status de `license`/`invoice`. TDD: mudança de plano gera 1 registro de auditoria com valores antes/depois; transição de dunning (T057) gera 1 registro por transição.

## Bloco D — Cadastro de Imóveis (US6, US7)
*Model e CRUD básico (T080-T081) podem iniciar em paralelo ao Bloco C; enforcement de limite (T082) depende de T050.*
- T080 [P] [US6] Migration + Model: `imoveis`.
- T081 [P] [US6] `ViaCepDriver` (Protocol + implementação httpx) com fallback: falha ou timeout do ViaCEP não bloqueia o salvamento, apenas deixa campos de endereço vazios para preenchimento manual.
- T082 [US6] TDD: `POST /imoveis`. Casos: campos obrigatórios (título, CEP, bairro, cidade, estado, tipo, área total) validados; CEP não encontrado no ViaCEP não impede a criação; criação além de `max_imoveis` do plano retorna 402 (depende de T050/T053); `corretor` só edita/visualiza imóveis que ele mesmo cadastrou, `admin` vê todos.
- T083 [US7] TDD: `GET /imoveis`. Casos: filtros por status/tipo/bairro/cidade/faixa de valor combinam em AND; paginação `skip`/`limit` retorna `total` correto; usuário nunca recebe imóvel de outro tenant (reforça T002).
- T084 [P] [US6][US7] UI: formulário de cadastro de imóvel em seções (Localização/Características/Valores/Documentação) + listagem com filtros.

## Fechamento
- T090 E2E (Playwright): fluxo completo signup → trial (7 dias simulados) → ativação de 2FA → convite e aceite de corretor → cadastro de imóveis até o limite do plano (bloqueio confirmado) → upgrade de plano → pagamento via sandbox Mercado Pago → dunning simulado (adiantando `trial_termina_em`/`vencimento` em ambiente de teste).
- T091 Homologação em sandbox do Mercado Pago: bateria de webhooks (aprovado, recusado, estornado, duplicado) documentada.
- T092 `/speckit.analyze` + cobertura ≥80% geral e 100% nos caminhos de dinheiro (Artigo III); teste de isolamento de tenant (Artigo I) confirmado no CI.
- T093 UAT com piloto real (1 corretor de verdade usando por alguns dias, incluindo passar pelo trial); tag **v0.1.0**.

**Dependências entre blocos:** A → (B, C, D-model). B (enforcement de convite) e D (enforcement de imóvel) dependem de C apenas nas tasks de limite (T034, T082) — o restante de B e D paraleliza com C. Fechamento depende de A+B+C+D completos.
