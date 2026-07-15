# Modelo de Dados — Feature 001: Fundação

Convenções: PK `id` (bigint); `uuid` público em recursos expostos por API; `tenant_id` em toda tabela operacional (indexado, presente em índices compostos); dinheiro/quantidade `NUMERIC(12,4)`; soft delete via `ativo boolean default true` onde há histórico associado; tabelas de trilha (`payment_events`) são append-only.

## Tenancy

**tenants** — uuid, nome, slug (unique, indexado), status (`trial`|`active`|`past_due`|`suspended`|`cancelled`), created_at, updated_at. *(central — é a própria unidade de isolamento, não carrega tenant_id)*

**users** — tenant_id, uuid, nome, email (**unique global**, indexado — login não seleciona tenant), password_hash, papel (`admin`|`corretor`), totp_secret (encrypted, nullable), totp_enabled (boolean, default false), totp_recovery_codes (encrypted json, nullable), ativo (boolean, default true), created_at, updated_at. *(email único na plataforma inteira, não só por tenant)*

**convites** — tenant_id, uuid, email, papel, token (unique), expires_at, aceito_em (nullable), criado_por (FK users), created_at. *(convite expira em 7 dias; um e-mail só pode ter 1 convite pendente por tenant)*

## Licenciamento

**plans** — uuid, nome (`solo`|`pro`|`enterprise`), max_users, max_imoveis (nullable = ilimitado), preco_mensal NUMERIC(12,4), features (json), ativo (boolean). *(central, sem tenant_id — catálogo compartilhado)*

**licenses** — tenant_id (**unique** — 1 license por tenant), plan_id (FK plans), preco_congelado NUMERIC(12,4), status (`trial`|`active`|`past_due`|`suspended`|`cancelled`), trial_termina_em (datetime), suspensa_em (nullable), cancelada_em (nullable), created_at, updated_at.

**invoices** — tenant_id, uuid, license_id (FK licenses), valor NUMERIC(12,4), status (`pending`|`paid`|`failed`|`refunded`), ciclo_mes (1-12), ciclo_ano, vencimento (date), pago_em (nullable datetime), created_at. *(1 fatura por ciclo mensal por tenant)*

**payment_events** — tenant_id, uuid, invoice_id (FK invoices, nullable), event_id_externo (**unique** — chave natural do Mercado Pago), payload (json), processado_em (datetime), created_at. *(append-only, garante idempotência do webhook — RN5)*

## Imóveis

**imoveis** — tenant_id, uuid, corretor_id (FK users — quem cadastrou), titulo, descricao (nullable), cep, logradouro (nullable), bairro, cidade, estado, latitude (nullable), longitude (nullable), tipo (`apartamento`|`casa`|`terreno`|`comercial`|`galpao`), area_total, area_util (nullable), quartos (nullable), banheiros (nullable), suites (nullable), vagas (nullable), andar (nullable), idade_anos (nullable), conservacao (`otima`|`boa`|`regular`|`ruim`, nullable), valor_anunciado (nullable NUMERIC(12,4)), status (`disponivel`|`vendido`|`alugado`|`reservado`), matricula (nullable), iptu_quitado (nullable boolean), escritura_ok (nullable boolean), fotos (json, array de URLs), ativo (boolean, default true — soft delete), created_at, updated_at, data_venda (nullable).

## Relações-chave e invariantes

- 1 `tenant` → N `users` (1:N); papel `admin`/`corretor` controla escopo de visão.
- 1 `tenant` → 1 `license` (1:1) → 1 `plan` (N:1; `license` guarda `preco_congelado`, independente de mudanças futuras no preço do `plan`).
- 1 `license` → N `invoices` (1:N, uma por ciclo mensal).
- 1 `invoice` → N `payment_events` (1:N — reentregas de webhook geram múltiplos eventos, só o primeiro com efeito).
- 1 `tenant` → N `imoveis`; 1 `user` (corretor) → N `imoveis` cadastrados por ele.
- **Invariante (RN3):** `COUNT(users WHERE tenant_id=X AND ativo=true) <= (SELECT max_users FROM licenses JOIN plans WHERE tenant_id=X)` — validado com lock pessimista na criação, vira teste de integração com concorrência simulada.
- **Invariante (RN3):** `COUNT(imoveis WHERE tenant_id=X AND ativo=true) <= max_imoveis` (quando `max_imoveis` não é nulo).
- **Invariante (RN5):** `payment_events.event_id_externo` é `UNIQUE` — garante que o mesmo evento do Mercado Pago nunca é aplicado duas vezes.
- **Invariante:** `users.email` é `UNIQUE` na tabela inteira (cross-tenant) — um e-mail pertence a exatamente um tenant como usuário.
- **Invariante (Artigo I):** toda query a `users`/`imoveis`/`invoices`/`payment_events`/`convites` é automaticamente filtrada por `tenant_id` do contexto da requisição — sem exceção.

## Estados

- `tenants.status` / `licenses.status`: `trial` → `active` (pagamento confirmado, pode ser síncrono) → `past_due` (falha de cobrança, meia-noite) → `suspended` (N dias em `past_due`, meia-noite) → `cancelled` (meia-noite, retenção de dados 30 dias) — todas as transições exceto `trial→active` só ocorrem no job agendado de meia-noite (RN6); todas são auditadas.
- `invoices.status`: `pending` → `paid` | `failed` → (retry via novo evento) → `paid` | `refunded`.
- `imoveis.status`: `disponivel` → `reservado` → `vendido`|`alugado` — transição manual pelo corretor/admin, sem automação nesta feature.
- `convites`: `pendente` (implícito, `aceito_em is null` e `expires_at > now`) → `aceito` (`aceito_em` preenchido) | `expirado` (`expires_at <= now` e `aceito_em is null`).
