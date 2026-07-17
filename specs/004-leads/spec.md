# Feature 004 — Gestão de Leads / Pipeline + Notificação em Tempo Real

**Status:** Em implementação | **Fase do roadmap:** 4 | **Release alvo:** v0.4.0
**Fonte:** docs/ESPECIFICACAO-MASTER.md §4 (M6, RF006) | **Depende de:** 001-fundacao (tenancy, imóveis)

## Resumo

Cadastro e acompanhamento de leads (oportunidades de venda) com pipeline de estágios,
vinculação opcional a um imóvel, notas/histórico, e notificação em tempo real (WebSocket) quando
um novo lead é criado — único evento em tempo real do MVP (decisão #4 da Especificação Master:
contadores de dashboard em tempo real ficam para fase futura).

## Histórias de usuário (priorizadas)

**US1 (P0) — Cadastrar lead.** Como corretor, quero cadastrar um lead com origem e,
opcionalmente, o imóvel de interesse, para começar a acompanhar a oportunidade.
- AC1: lead pertence ao corretor que o cadastrou; `admin` vê todos os leads do tenant.
- AC2: `imovel_id` é opcional (um lead pode não ter um imóvel específico ainda associado).

**US2 (P0) — Mover lead pelo pipeline.** Como corretor, quero mover um lead entre estágios
(novo → contatado → visita → proposta → fechado/perdido), para refletir o progresso da negociação.
- AC1: qualquer transição entre estágios não-terminais é permitida (não é estritamente sequencial —
  o corretor pode pular etapas conforme a realidade da negociação).
- AC2: `fechado` e `perdido` são estágios terminais — uma vez lá, o lead não pode ser reaberto
  (decisão de MVP: reabrir exigiria um novo lead, mantém o histórico do funil íntegro).

**US3 (P0) — Notas e histórico.** Como corretor, quero registrar notas em um lead, para manter
contexto da negociação ao longo do tempo.
- AC1: notas são append-only (histórico nunca editado/apagado).
- AC2: toda mudança de estágio do pipeline também gera uma nota automática de histórico.

**US4 (P0) — Notificação em tempo real de novo lead.** Como corretor, quero ser notificado
imediatamente quando um lead novo chega, para responder rapidamente (RNF de tempo real).
- AC1: ao criar um lead, uma notificação é publicada no canal WebSocket do tenant
  (`tenant.{tenant_id}.notificacoes`).
- AC2: apenas usuários autenticados do mesmo tenant recebem a notificação (isolamento — Artigo I
  aplicado também ao canal de tempo real).

**US5 (P1) — Listagem e filtro de leads.** Como corretor, quero listar/filtrar meus leads por
estágio e origem, para organizar o dia de trabalho.
- AC1: `corretor` só lista os próprios leads; `admin` lista todos do tenant.

## Fora de escopo

Contadores de dashboard em tempo real (fase futura, decisão #4 da Especificação Master) ·
atribuição automática/round-robin de leads entre corretores · integração com formulários de
portais externos para captura automática de lead (entrada é manual/API própria no MVP) ·
reabertura de lead fechado/perdido (cria-se um novo lead) · SLA/alertas de lead parado
(fase futura).

## Regras de negócio críticas

- RN1: lead pertence a um `corretor_id` (dono) dentro do tenant; mesma visibilidade de
  `imoveis`/`avaliacoes` — `corretor` só vê/gerencia os próprios leads, `admin` vê todos.
- RN2: pipeline com 6 estágios fixos (`novo`, `contatado`, `visita`, `proposta`, `fechado`,
  `perdido`); `fechado`/`perdido` são terminais — transição para fora deles é rejeitada (422).
- RN3: toda transição de estágio gera uma `LeadNota` automática registrando de/para (histórico
  append-only, nunca editado).
- RN4: `imovel_id` é opcional; quando informado, deve pertencer ao mesmo tenant (404 caso
  contrário — mesmo padrão de `avaliacoes`/`sugestoes_preco`).
- RN5: ao criar um lead, o evento de domínio `lead_criado` é emitido (barramento in-process,
  `app.core.events`) e um listener publica a notificação no canal Redis do tenant — desacopla
  `leads` do transporte de notificação (Artigo VIII/YAGNI: outros tipos de evento em tempo real
  só são adicionados quando houver demanda real).

## Requisitos não funcionais aplicáveis

Artigo I (isolamento multi-tenant, inclusive no canal de notificação) · Artigo IV (contrato
OpenAPI antes da rota) · Artigo VII (RBAC por papel) · RNF do documento master sobre tempo real
(WebSockets nativos do FastAPI + Redis pub/sub, canais namespaced por tenant — ver
ARQUITETURA-REFERENCIA.md §3.4).
