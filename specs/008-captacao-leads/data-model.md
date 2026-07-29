# Modelo de Dados — Feature 008: Captação Automática de Leads

Uma tabela nova (`tenant_api_keys`), duas alterações de schema: `leads.corretor_id` vira
opcional; `imoveis` ganha `views`/`contatos` (`INTEGER`, default 0) — citados na especificação
desde a v1.0.0 mas nunca antes implementados como coluna.

## Alteração em `leads` (004-leads)

**`corretor_id`** vira `NULLABLE` (era obrigatório). `NULL` significa "lead sem dono" — criado
por um canal automático (página pública, webhook) sem nenhum corretor logado no momento. Um
lead sem dono é visível para todos os corretores do tenant (e para o admin), não só para quem
o criou (RN7 do spec.md) — não existe FK de banco para `users.uuid` (mesmo padrão já usado:
`corretor_id` guarda `User.uuid`, não a PK interna, sem constraint literal).

## Tabela nova: `tenant_api_keys`

Tenant-scoped (`TenantScopedMixin`), no máximo uma linha por tenant.

| Campo | Tipo | Notas |
|---|---|---|
| id | int PK | |
| uuid | UUID unique | |
| tenant_id | UUID (herdado) | `UniqueConstraint` — só uma chave por tenant |
| key_hash | string(64) unique index | SHA-256 hex da chave em texto plano — lookup direto, não bcrypt (chave já é alta entropia, não senha humana; precisa de busca por igualdade, não verificação lenta) |
| created_at | datetime | |
| last_used_at | datetime nullable | atualizado a cada `POST /webhooks/leads` bem-sucedido com essa chave |

Gerar uma nova chave faz `INSERT ... ON CONFLICT (tenant_id) DO UPDATE` (upsert) — substitui a
linha existente, nunca acumula. A chave em texto plano (`secrets.token_urlsafe(32)`) nunca é
persistida — só o hash.

## Colunas novas em `imoveis`: `views` e `contatos`

`INTEGER NOT NULL DEFAULT 0`. `views` incrementa em todo `GET /imoveis/publico/{id}`
bem-sucedido (imóvel encontrado e público). `contatos` incrementa toda vez que um `Lead` é
criado com `imovel_id` preenchido — isso passa a valer também para `POST /leads` (004-leads,
cadastro manual pelo corretor), não só para os dois caminhos novos desta feature (RN6).

## Invariantes

- **Invariante (RN1/Artigo I):** `GET /imoveis/publico/{id}` e `POST /leads/publico` resolvem o
  tenant via Host header (mesmo `resolve_tenant_uuid_by_host` de 001-fundacao) *antes* de tocar
  `Imovel`/`Lead`; `POST /webhooks/leads` resolve via hash da API key, também antes de qualquer
  acesso a tabela tenant-scoped — em nenhum dos três casos o tenant vem de um campo do payload.
- **Invariante (RN2):** a busca pública de imóvel sempre filtra `status=disponivel AND
  ativo=True` — nunca existe um caminho público que exponha um imóvel vendido, alugado,
  reservado ou soft-deletado.
- **Invariante (RN4):** `tenant_api_keys` nunca tem mais de uma linha por `tenant_id` — reforçado
  por `UniqueConstraint`, não só por convenção do código de aplicação.
