# Plano de Implementação — Feature 007: Superadmin

**Spec:** ./spec.md | **Constitution Check:** ⚠️ — esta é a primeira feature que introduz um
caminho de acesso cross-tenant acionado por requisição de usuário final (não só por job de
sistema). Mitigado mantendo `system_scope()` só dentro do novo módulo `superadmin/`, nunca
exposto como helper genérico reutilizável por outros módulos. Sem dependência nova de
backend/frontend.

## Contexto técnico

Novo módulo `backend/app/modules/superadmin/` (models, service, router, schemas) + duas
alterações pontuais fora dele: `core/security.py` (funções de token de superadmin),
`core/deps.py` (`require_superadmin`), `modules/tenancy/deps.py` ou `core/deps.py`
(`get_current_user` passa a checar `Tenant.status`). Frontend: novo bundle/rota separada
(decisão de design #1 abaixo).

## Pontos de design

1. **Painel superadmin como rotas separadas dentro do bundle `corretor` existente (não um
   bundle Vue novo), atrás de um path próprio (`/admin`) com guarda de rota por `papel`.**
   *Por quê:* criar um segundo bundle Vue inteiro (build, Dockerfile, nginx, porta) para uma
   tela de uso interno pouco frequente é overhead de infra desproporcional ao valor (Artigo
   VIII); o Vue Router já suporta guardas de rota, e o layout pode ser visualmente distinto sem
   ser um projeto separado. *Alternativa rejeitada:* app Vue dedicado — reconsiderar só se o
   painel crescer a ponto de precisar de deploy/release independente do app de corretor.

2. **Token de superadmin sem `tenant_id`, não um `tenant_id` mágico/nulo tratado como
   "wildcard".** *Por quê:* um valor sentinela (`tenant_id=null` tratado como "todos os
   tenants") é o tipo de atalho que um dia vaza para o código tenant-scoped comum e vira bypass
   de isolamento por acidente; a ausência do campo + uma dependency completamente separada
   (`require_superadmin`, nunca `require_admin`) deixa os dois mundos estruturalmente
   impossíveis de confundir no nível de tipo/payload. *Alternativa rejeitada:* reaproveitar
   `tenancy.User` com um `Papel.SUPERADMIN` a mais — foi a opção descartada explicitamente com o
   dono do produto (conta separada, fora do modelo de tenant).

3. **RN2 (bloqueio de tenant suspenso) verificado em `get_current_user`, não em middleware
   novo.** *Por quê:* `get_current_user` já é o ponto único por onde toda rota autenticada
   tenant-scoped passa (Artigo I); adicionar a checagem ali garante que nenhuma rota existente
   ou futura escape dela. *Alternativa rejeitada:* checar em `IdentifyTenantMiddleware` — está
   mais cedo no pipeline, mas roda para requisições não-autenticadas também (endpoints
   públicos por subdomínio) onde "tenant suspenso" não deveria virar erro de auth.

4. **`system_scope()` só usado dentro de `superadmin/service.py`.** *Por quê:* concentrar o
   único ponto de bypass acionável por request comum minimiza a superfície de auditoria — quem
   revisar isolamento multi-tenant no futuro só precisa olhar um módulo, não grep o projeto
   inteiro. *Alternativa rejeitada:* expor um helper tipo `admin_query()` genérico em
   `core/` — tentador de mais reutilizável, maior risco de uso indevido fora do contexto
   superadmin.

5. **Bootstrap do superadmin por variável de ambiente no boot, sem endpoint de criação.**
   *Por quê:* consistente com o workflow de deploy já estabelecido (zip com `.env.prod` contendo
   segredos gerados) — adicionar `SUPERADMIN_EMAIL`/`SUPERADMIN_PASSWORD` ao `.env.prod` é o
   mesmo padrão já usado para `JWT_SECRET`/`ENCRYPTION_KEY`, sem exigir SSH nem endpoint público
   de auto-cadastro para uma conta tão privilegiada. *Alternativa rejeitada:* CLI/comando de
   management interativo — exigiria acesso ao terminal do servidor, que o workflow deste projeto
   evita.

## Fases

**P1 — Auth do superadmin**
`superadmin_users` (model + migration). `create_superadmin_access_token`/
`decode`+`require_superadmin` em `core/security.py`+`core/deps.py`. Bootstrap por env no
startup. `POST /admin/auth/login`. TDD: login válido retorna token sem `tenant_id`; token de
tenant rejeitado por `require_superadmin` e vice-versa (RN3); bootstrap idempotente (rodar boot
duas vezes não duplica nem reseta senha).

**P2 — RN2: bloqueio de tenant suspenso**
*Independente de P1 (mexe em `get_current_user`, não em superadmin).* TDD: usuário de tenant com
`status=SUSPENDED` recebe 403 mesmo com `User.ativo=True` e token válido; tenant `ACTIVE` segue
normal; reativar volta o acesso sem novo login.

**P3 — Tenants e suspensão/reativação**
*Depende de P1.* `GET /admin/tenants`, `GET /admin/tenants/{id}/metricas`,
`POST /admin/tenants/{id}/suspender`, `POST /admin/tenants/{id}/reativar` (reaproveita RN2 de
P2). TDD: listagem cross-tenant via `system_scope()`; suspender seta status + audit log; reativar
idem; ações exigem `require_superadmin` (403 para token de tenant, mesmo se `admin`).

**P4 — Dashboard consolidado**
*Depende de P1.* `GET /admin/uso/plataforma`, `GET /admin/faturamento/consolidado`. TDD: MRR
soma só licenses `ACTIVE` com preço congelado (RN4); contagem de tenants por status bate com
fixtures de múltiplos tenants em status diferentes.

**P5 — Auditoria centralizada**
*Depende de P1.* `GET /admin/auditoria/logs` (paginado, filtros `tenant_id`/`acao`/data). TDD:
retorna logs de múltiplos tenants na mesma resposta (prova de `system_scope()` funcionando);
filtro por `tenant_id` restringe corretamente.

**P6 — UI**
Rota `/admin` no bundle `corretor` (guarda por token de superadmin, layout próprio): tela de
login, dashboard (US2), lista de tenants com ação suspender/reativar (US3/US4), auditoria (US5).

## Riscos

| Risco | Mitigação |
|---|---|
| Sem 2FA no superadmin — conta única de altíssimo privilégio protegida só por senha | Aceito nesta v1 (poucas contas, uso interno); documentado como próximo hardening antes de dar a mais de uma pessoa acesso |
| `system_scope()` usado por engano fora do módulo `superadmin/` no futuro | Concentração no único módulo (Decisão #4) + `TenantContextMissingError` já explode alto (fail-loud) se uma query tenant-scoped rodar sem contexto em qualquer outro lugar |
| RN2 quebrar algum fluxo existente que dependia de tenant suspenso ainda funcionar (nenhum conhecido hoje) | Rodar suíte completa dos módulos existentes (imoveis/leads/avaliacoes/dashboard) após a mudança em `get_current_user`, não só os testes novos |
| Bootstrap de superadmin rodando em ambiente sem as env vars (dev local) | Boot segue normal sem criar nada — só ativa se as duas env vars estiverem presentes, mesmo padrão opcional de `mercadopago_access_token` |

## Critério de conclusão

ACs de US1-US5 verdes · RN2 comprovado com teste que hoje falharia (tenant suspenso continua
acessando) e passa depois da mudança · nenhum teste dos módulos 001-006 quebra com a checagem
nova em `get_current_user` · cobertura ≥80% no módulo `superadmin` · fluxo manual: subir com
`SUPERADMIN_EMAIL`/`SUPERADMIN_PASSWORD`, logar em `/admin`, ver dashboard consolidado com pelo
menos 2 tenants de teste, suspender um e confirmar 403 no login daquele tenant, reativar e
confirmar volta → tag **v0.7.0**.
