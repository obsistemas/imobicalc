# Modelo de Dados — Feature 007: Superadmin

Uma tabela nova, sem `tenant_id` (deliberadamente fora do isolamento multi-tenant — é a própria
definição do papel). Nenhuma tabela existente muda de schema; `Tenant.status` já existia
(001-fundacao) e passa só a ser **aplicado** (RN2), não alterado estruturalmente.

## Tabela nova: `superadmin_users`

Não herda `TenantScopedMixin` — vive fora do listener de isolamento por design (mesma decisão
de `Plan`, que também não tem `tenant_id`, mas aqui é uma conta de acesso, não um catálogo).

| Campo | Tipo | Notas |
|---|---|---|
| id | int PK | |
| uuid | UUID unique | |
| nome | string(120) | |
| email | string(255) unique index | |
| password_hash | string(255) | bcrypt, mesmo `app/core/security.py` já usado por `tenancy.User` |
| ativo | bool default True | desativação lógica (sem soft-delete no schema, só flag) |
| created_at | datetime | |

Provisionamento: **sem endpoint de cadastro**. No boot da aplicação, se `SUPERADMIN_EMAIL` e
`SUPERADMIN_PASSWORD` estiverem setados (`.env`/`.env.prod`) e não existir superadmin com aquele
email, cria um — idempotente, mesmo padrão de `ensure_plans_seeded`. Rodar de novo com a mesma
env não duplica nem reseta a senha de uma conta já existente (evita reset acidental de senha a
cada deploy).

## JWT do superadmin

Reaproveita `app/core/security.py` (`jwt.encode`/`decode`, mesmo segredo `JWT_SECRET`), mas com
payload estruturalmente diferente do token de tenant — **sem `tenant_id`**:

```json
{
  "sub": "<superadmin_user.uuid>",
  "papel": "superadmin",
  "type": "access",
  "iat": ...,
  "exp": ...,
  "jti": "..."
}
```

A ausência de `tenant_id` no payload é o discriminador usado por `IdentifyTenantMiddleware`
(não tenta abrir `tenant_scope()` para esse token) e por `require_superadmin` (rejeita qualquer
token que *tenha* `tenant_id` — não é um superadmin). Sem refresh token nesta v1 (ver "Fora de
escopo" no spec.md) — expiração curta (`superadmin_token_expire_minutes`, padrão 60min), exige
novo login ao expirar.

## Leituras cross-tenant (sem tabela nova)

US2/US3/US5 são consultas agregadas sobre tabelas já existentes, sempre dentro de
`system_scope()`:

- **Uso agregado:** `COUNT`/`SUM` sobre `User`, `Imovel`, `Lead`, `Avaliacao` sem filtro de
  tenant (RN1).
- **Faturamento:** `SUM(License.preco_congelado)` onde `status=ACTIVE` (MRR, RN4);
  `SUM(Invoice.valor)` onde `status=PAID` e `ciclo_mes/ciclo_ano` = mês corrente.
- **Auditoria:** `SELECT * FROM audit_logs` sem filtro de tenant, paginado, com filtros opcionais
  (`tenant_id`, `acao`, intervalo de data) — mesma tabela de 001-fundacao/licenciamento, sem
  alteração de schema.

## Invariantes

- **Invariante (RN1/Artigo I invertido):** todo acesso cross-tenant desta feature passa por
  `system_scope()` explícito — nunca por remoção implícita do filtro (ex.: nunca por comparar
  `tenant_id != None`, que seria fácil de esquecer em uma tabela nova amanhã).
- **Invariante (RN3):** `superadmin_users` nunca aparece em nenhuma query dentro de
  `tenant_scope()` nem é acessível por `get_current_user` (dependency de tenant) — são
  dependencies e tabelas paralelas, sem ponto de junção no código de request.
- **Invariante (RN2):** a partir do momento em que `Tenant.status = SUSPENDED`,
  `get_current_user` (usado por toda rota tenant-scoped autenticada) rejeita a requisição — não
  há rota "esquecida" que ignore o status do tenant, porque a checagem vive na dependency
  central, não em cada router.
