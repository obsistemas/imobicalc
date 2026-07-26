# Tasks — Feature 007: Superadmin

Formato: `T6## [P?] [US?] descrição` — [P] = paralelizável. Cada task termina com testes verdes +
commit convencional. Numeração: feature 007 usa T6xx.

## Bloco A — Auth do superadmin
- T600 Migration + model: `superadmin_users` (id, uuid, nome, email, password_hash, ativo,
  created_at), sem `TenantScopedMixin`.
- T601 `core/security.py`: `create_superadmin_access_token`/`decode_superadmin_token` — payload
  sem `tenant_id`, `papel="superadmin"`, expiração própria
  (`settings.superadmin_token_expire_minutes`, padrão 60).
- T602 `core/deps.py`: `require_superadmin` — decodifica, rejeita token com `tenant_id` presente
  ou `papel != superadmin`, carrega `SuperadminUser` ativo.
- T603 Bootstrap idempotente no startup (`main.py`/`lifespan`): se `SUPERADMIN_EMAIL` +
  `SUPERADMIN_PASSWORD` setados e não existe superadmin com aquele email, cria um. TDD: roda
  duas vezes, não duplica nem reseta senha existente; sem as env vars, não faz nada.
- T604 [US1] `POST /admin/auth/login`. TDD: credenciais válidas retornam token sem `tenant_id`;
  inválidas retornam 401; conta `ativo=False` retorna 401.
- T605 [US1] TDD cruzado (RN3): token de tenant (`admin`/`corretor`) rejeitado por
  `require_superadmin`; token de superadmin rejeitado por `get_current_user`/`require_admin`.

## Bloco B — RN2: bloqueio de tenant suspenso
*Independente do Bloco A.*
- T610 `core/deps.py` (`get_current_user`): carrega `Tenant` do `tenant_id` do payload, rejeita
  com 403 se `Tenant.status == SUSPENDED`.
- T611 TDD: usuário `ativo=True` de tenant `SUSPENDED` recebe 403 em qualquer rota autenticada
  (usar uma rota existente simples, ex. `GET /imoveis`, como sonda); tenant `ACTIVE`/`TRIAL`/
  `PAST_DUE` segue passando (só `SUSPENDED` bloqueia).
- T612 Rodar suíte completa dos módulos 001-006 para confirmar que a checagem nova não quebra
  nenhum teste existente (dunning já seta `PAST_DUE` em fluxo normal — não deve virar 403).

## Bloco C — Tenants e suspensão/reativação
*Depende do Bloco A (require_superadmin) e Bloco B (RN2 é o efeito da suspensão).*
- T620 Contrato OpenAPI de `GET /admin/tenants`, `GET /admin/tenants/{id}/metricas`,
  `POST /admin/tenants/{id}/suspender`, `POST /admin/tenants/{id}/reativar`.
- T621 [US3] `service.listar_tenants` (paginado, `system_scope()`) + endpoint. TDD: retorna
  tenants de fixtures diferentes na mesma chamada (prova cross-tenant).
- T622 [US3] `service.metricas_tenant` (uso individual: usuários/imóveis/leads/avaliações +
  dados da license) + endpoint. TDD: números batem com fixtures de um tenant específico, sem
  vazar contagem de outro tenant.
- T623 [US4] `service.suspender_tenant`/`reativar_tenant` (seta `Tenant.status` + grava
  `audit_logs` do tenant afetado) + endpoints. TDD: suspender seta status e audit log; reativar
  idem; usuário do tenant recebe 403 imediatamente após suspender (integra com T611) sem precisar
  de novo login.
- T624 Ambos endpoints exigem `require_superadmin`: token de tenant `admin` recebe 403 (não basta
  ser admin de imobiliária).

## Bloco D — Dashboard consolidado
*Depende do Bloco A.*
- T630 Contrato OpenAPI de `GET /admin/uso/plataforma` e `GET /admin/faturamento/consolidado`.
- T631 [US2] `service.uso_plataforma` (contagem de tenants por `TenantStatus` + totais agregados
  de usuários/imóveis/leads/avaliações) + endpoint. TDD: fixtures com tenants em 3+ status
  diferentes, contagem bate exata.
- T632 [US2] `service.faturamento_consolidado` (MRR = soma `preco_congelado` de licenses
  `ACTIVE`, RN4; receita paga no ciclo atual; contagem de invoices por status) + endpoint. TDD:
  license `TRIAL`/`CANCELLED` não entra no MRR; preço atual do plano mudar não afeta MRR de
  license já congelada.

## Bloco E — Auditoria centralizada
*Depende do Bloco A.*
- T640 Contrato OpenAPI de `GET /admin/auditoria/logs`.
- T641 [US5] `service.listar_auditoria_cross_tenant` (`system_scope()`, paginado, filtros
  `tenant_id`/`acao`/`desde`/`ate`) + endpoint. TDD: retorna logs de tenants diferentes na mesma
  resposta; filtro por `tenant_id` restringe; somente leitura (nenhuma rota de escrita).

## Bloco F — UI
- T650 [P] Guarda de rota `/admin/*` no Vue Router (token de superadmin em storage separado do
  token de tenant — nunca no mesmo slot, para não colidir com sessão de corretor/imobiliária no
  mesmo navegador).
- T651 [P] Tela de login do superadmin.
- T652 [P] Dashboard: cards de uso/faturamento consolidado (US2).
- T653 [P] Lista de tenants com métricas + botão suspender/reativar (US3/US4).
- T654 [P] Tela de auditoria com filtros (US5).

## Fechamento
- T660 Cobertura ≥80% no módulo `superadmin`.
- T661 Fluxo manual completo (ver "Critério de conclusão" do plan.md) → tag **v0.7.0**.

**Dependências entre blocos:** A e B são independentes entre si e podem paralelizar. C, D, E
dependem de A (e C também depende de B). F depende de C+D+E. Fechamento depende de todos.
