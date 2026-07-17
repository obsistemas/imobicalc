# Modelo de Dados — Feature 004: Gestão de Leads / Pipeline

Convenções herdadas de 001-003: PK `id` (bigint), `uuid` público, tabela tenant-scoped via
`TenantScopedMixin`.

## Leads (M6)

**leads** — `tenant_id`, `uuid`, `corretor_id` (uuid do User dono do lead), `imovel_id` (uuid do
Imovel, nullable — RN4), `nome`, `email` (nullable), `telefone` (nullable), `origem`
(`site`|`indicacao`|`portal`|`redes_sociais`|`outro`), `estagio`
(`novo`|`contatado`|`visita`|`proposta`|`fechado`|`perdido`, default `novo`), `created_at`,
`updated_at`. *(mutável — ao contrário de `avaliacoes`/`sugestoes_preco`, o registro principal do
lead é atualizado in-place conforme avança no pipeline; o histórico fica em `leads_notas`)*

**leads_notas** — `tenant_id`, `uuid`, `lead_id` (uuid do Lead), `autor_id` (uuid do User),
`texto`, `automatica` (bool — `true` quando gerada por uma transição de estágio, RN3),
`created_at`. *(append-only — nunca editada)*

## Relações-chave e invariantes

- 1 `lead` → N `leads_notas` (histórico, nunca sobrescrito — RN3).
- **Invariante (RN2):** `estagio` só transiciona livremente entre estágios não-terminais;
  uma vez `fechado` ou `perdido`, nenhuma nova transição é aceita.
- **Invariante (RN4):** `imovel_id`, quando não nulo, referencia um `Imovel` do mesmo tenant.
- **Invariante (Artigo I):** toda query a `leads`/`leads_notas` é filtrada por `tenant_id` do
  contexto da requisição; o canal de notificação em tempo real (`tenant.{tenant_id}.notificacoes`)
  também é namespaced por tenant — nenhum outro tenant recebe a mensagem.

## Notificação em tempo real (RN5)

Ao criar um lead (`leads/service.py::criar_lead`), após o commit é emitido o evento de domínio
`lead_criado` (via `app.core.events.emit`, barramento in-process síncrono já usado por
`licenciamento`). Um listener em `leads/listeners.py` publica no canal Redis
`tenant.{tenant_id}.notificacoes` um payload `{"tipo": "lead_novo", "lead": {...campos básicos...}}`.
O endpoint WebSocket (`app/modules/notificacoes/router.py`, `GET /ws/notificacoes?token=<jwt>`)
autentica pelo próprio JWT de acesso (query param — WebSocket do navegador não permite header
`Authorization` customizado), assina o canal do `tenant_id` do token e retransmite qualquer
mensagem publicada para o cliente conectado.
