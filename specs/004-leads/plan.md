# Plano de Implementação — Feature 004: Gestão de Leads / Pipeline

**Spec:** ./spec.md | **Constitution Check:** ✅ — nenhuma dependência nova de terceiros; usa
Redis já provisionado (RQ/pub-sub) e o barramento de eventos in-process já existente
(`app.core.events`, hoje usado por `licenciamento`).

## Contexto técnico

Dois módulos novos: `backend/app/modules/leads` (M6 — CRUD, pipeline, notas) e
`backend/app/modules/notificacoes` (endpoint WebSocket, infraestrutura cross-cutting reutilizável
por futuros eventos em tempo real, hoje usada só por `leads`). Reuso: `TenantScopedMixin`,
`tenant_scope`, `get_current_user`, visibilidade por corretor/admin (`_garante_visivel`, mesmo
padrão de `imoveis`), `app.core.events.on/emit`, `app.core.redis_client.get_redis`.

## Pontos de design

1. **Lead é mutável, notas são append-only:** ao contrário de `avaliacoes`/`sugestoes_preco`
   (histórico imutável), o registro do lead reflete o estado atual do pipeline e é atualizado
   in-place; cada mudança de estágio gera uma `LeadNota` automática, preservando o histórico sem
   duplicar o registro principal. *Alternativa rejeitada:* lead também append-only — obrigaria
   reconstruir o estado atual a partir do histórico a cada leitura, sem necessidade real no MVP.

2. **Notificação via evento de domínio, não acoplamento direto:** `leads/service.py` emite
   `lead_criado` (`app.core.events.emit`) em vez de chamar diretamente um `publish` do Redis;
   `leads/listeners.py` reage e publica no canal do tenant. *Por quê:* mesmo padrão já usado por
   `licenciamento` (ARQUITETURA-REFERENCIA.md §1) — mantém `leads` sem conhecimento do transporte
   de notificação; se o mecanismo de tempo real mudar (ex.: SSE) só o listener muda.
   *Alternativa rejeitada:* `leads/service.py` chamar `redis.publish` diretamente — acopla o
   domínio de leads ao transporte de notificação.

3. **Cliente Redis passado explicitamente (dependency injection), não um singleton oculto no
   listener:** o router recebe `redis: Redis = Depends(get_redis)` e repassa para
   `service.criar_lead(..., redis=redis)`, que inclui `redis=redis` no `emit`. *Por quê:* testes
   usam `FakeAsyncRedis` via override de `get_redis` (já estabelecido em `conftest.py`); se o
   listener resolvesse um singleton global, os testes precisariam de um Redis real. *Alternativa
   rejeitada:* singleton global de Redis no listener — quebra isolamento de teste.

4. **WebSocket autenticado por JWT em query param:** `GET /ws/notificacoes?token=<access_token>`
   decodifica com a mesma `decode_token` de `app.core.security`. *Por quê:* a API nativa
   `WebSocket` do navegador não permite enviar header `Authorization` customizado no handshake —
   query param é o padrão pragmático usado amplamente para WS. *Alternativa rejeitada:* cookie de
   sessão dedicado para WS — mais infraestrutura do que o MVP precisa, o access token de curta
   duração já existente é suficiente.

## Fases

**P1 — Migration + Models**
`Lead` e `LeadNota` (`TenantScopedMixin`), migration encadeada no head atual.

**P2 — Service/Router de Leads (CRUD + pipeline + notas)**
`criar_lead` (valida `imovel_id` quando informado, emite `lead_criado`), `listar_leads`
(filtro por estágio/origem, visibilidade por papel), `mover_estagio` (rejeita transição a partir
de estágio terminal, cria `LeadNota` automática), `adicionar_nota`, `listar_notas`.

**P3 — WebSocket de Notificação**
`app/modules/notificacoes/router.py` (endpoint WS) + `leads/listeners.py` (publica no canal do
tenant). Registrar listener em `main.py` (mesmo padrão de `licenciamento_listeners`).

**P4 — UI**
Lista de leads com filtro por estágio (`LeadsListView.vue`), formulário de criação
(`LeadFormView.vue`), detalhe do lead com transição de estágio + notas (`LeadDetailView.vue`),
cliente WebSocket global (composable `useNotificacoes`) exibindo um toast quando um lead novo
chega, conectado a partir do `App.vue` assim que autenticado.

## Riscos

| Risco | Mitigação |
|---|---|
| Conexão WebSocket cai silenciosamente e o corretor para de receber notificações | Reconexão automática simples (retry com backoff fixo) no composable do frontend |
| Teste de integração do WebSocket ficar acoplado a timing de pub/sub assíncrono | Usar `FakeAsyncRedis` (já usado no projeto) + `TestClient` síncrono do Starlette só para o teste de WS, com timeout curto e explícito |

## Critério de conclusão

ACs de US1-US5 verdes · cobertura ≥80% no módulo `leads` · teste de isolamento de tenant em
`leads`/`leads_notas` (Artigo I) · teste confirmando que a notificação de um tenant nunca chega
no canal de outro tenant · fluxo manual completo: cadastrar lead → ver notificação em tempo real
→ mover pelo pipeline → registrar nota → tag **v0.4.0**.
