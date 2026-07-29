# Tasks — Feature 008: Captação Automática de Leads

Formato: `T7## [P?] [US?] descrição` — [P] = paralelizável. Cada task termina com testes verdes +
commit convencional. Numeração: feature 008 usa T7xx.

## Bloco A — Schema
- T700 Migration: `leads.corretor_id` nullable (era NOT NULL).
- T701 Migration + model: `tenant_api_keys` (uuid, tenant_id único, key_hash único, created_at,
  last_used_at nullable), `TenantScopedMixin`.

## Bloco B — Página pública do imóvel
*Depende do Bloco A só para não conflitar de migration; sem dependência funcional.*
- T710 Contrato OpenAPI de `GET /imoveis/publico/{id}`.
- T711 `imoveis/service.py`: `obter_imovel_publico` (sem `user`, filtra
  `status=disponivel`+`ativo=True`, incrementa `views`). TDD: imóvel disponível retorna DTO
  público; vendido/alugado/reservado/inativo = não encontrado; tenant não resolvido pelo Host =
  não encontrado; `views` incrementa a cada chamada.
- T712 Endpoint `GET /imoveis/publico/{id}` (sem `Depends(get_current_user)`, resolve tenant via
  `request.state.tenant_id`, 404 se ausente). DTO público sem campos internos (matrícula, IPTU,
  valor_avaliado, valor_mercado).

## Bloco C — Formulário público de interesse
*Depende do Bloco B (reaproveita a mesma resolução de tenant público).*
- T720 Contrato OpenAPI de `POST /leads/publico`.
- T721 `leads/schemas.py`: `LeadPublicoCreate` (nome, email, telefone, imovel_id obrigatório) com
  validação "telefone ou email obrigatório" (RN3).
- T722 `leads/service.py`: `criar_lead_publico` — cria Lead (corretor_id=None, origem=SITE),
  incrementa `Imovel.contatos`, emite `lead_criado`. TDD: cria lead corretamente; sem telefone
  nem email = erro de validação; imóvel de outro tenant/indisponível = não encontrado.
- T723 Endpoint `POST /leads/publico`. TDD ponta a ponta via WS (reaproveita padrão de
  `test_notificacoes_ws.py`): corretor do tenant certo recebe `lead_novo`; outro tenant nunca
  recebe.
- T724 `imoveis/service.py`/`leads/service.py`: `Imovel.contatos` também incrementa em
  `POST /leads` manual (004-leads) quando `imovel_id` informado — fecha lacuna RF006 original
  (RN6). TDD: cadastro manual de lead vinculado a imóvel incrementa o contador.

## Bloco D — Gestão de API key
*Independente dos blocos B/C.*
- T730 Contrato OpenAPI de `POST`/`GET /leads/integracao/api-key`.
- T731 `leads/service.py`: `gerar_api_key` (upsert por tenant, retorna texto plano) e
  `obter_status_api_key` (created_at/last_used_at, nunca a chave). TDD: gerar duas vezes
  invalida a primeira (hash antigo não autentica mais); status nunca inclui a chave em si.
- T732 Endpoints `POST`/`GET /leads/integracao/api-key` (admin-only). TDD: corretor recebe 403.

## Bloco E — Webhook de leads
*Depende do Bloco D (precisa de uma chave existente para testar).*
- T740 Contrato OpenAPI de `POST /webhooks/leads`.
- T741 `leads/service.py`: `criar_lead_webhook` — resolve tenant via hash da API key
  (`system_scope()`, mesmo padrão documentado para login por e-mail), cria Lead
  (corretor_id=None), incrementa contatos se `imovel_id`, atualiza `last_used_at`, emite
  `lead_criado`. TDD: chave válida cria no tenant certo; chave inexistente/removida = 401;
  `origem` ausente vira `outro`; `imovel_id` de outro tenant = erro (não cria lead "órfão"
  silenciosamente).
- T742 Endpoint `POST /webhooks/leads` (header `X-API-Key`, sem `Depends(get_current_user)`).

## Bloco F — Ajuste de visibilidade (RN7)
*Pode rodar em paralelo aos blocos B-E — só toca `leads/service.py` em funções já existentes.*
- T750 `_garante_visivel`/`listar_leads`: `corretor_id=None` visível para qualquer corretor do
  tenant (e para admin, como já era). TDD: corretor A vê lead sem dono; corretor A não vê lead
  do corretor B (comportamento antigo preservado); admin vê tudo.

## Bloco G — UI
- T760 [P] `PublicoImovelView.vue` — rota pública (`meta: { public: true }`), fora do guard de
  autenticação, mostra dados do imóvel + formulário de interesse.
- T761 [P] Tela de gestão da API key (área admin): gerar (mostra a chave uma vez, com aviso de
  "copie agora"), status (criada em/última vez usada).

## Fechamento
- T770 Rodar suíte completa dos módulos 001-007 para confirmar que `corretor_id` nullable não
  quebra nenhum teste existente.
- T771 Cobertura ≥80% no que foi adicionado.
- T772 Fluxo manual completo (ver "Critério de conclusão" do plan.md) → tag **v0.8.0**.

**Dependências entre blocos:** A é pré-requisito de tudo (migration). B é pré-requisito de C
(reaproveita resolução pública de tenant). D é pré-requisito de E. F é independente, paralelo a
B-E. G depende de C (form) e D/E (tela de api key). Fechamento depende de todos.
