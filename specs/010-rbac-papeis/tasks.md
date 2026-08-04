# Tasks — Feature 010: RBAC 4 Papéis

Formato: `T9## [P?] [US?] descrição` — [P] = paralelizável. Cada task termina com testes verdes +
commit convencional. Numeração: feature 010 usa T9xx.

## Bloco A — Schema
- T900 Migration: `UPDATE users SET papel='dono' WHERE papel='admin'` + `users.assistente_de_id`
  (UUID, nullable) + `convites.assistente_de_id` (UUID, nullable).
- T901 Model: `Papel` com `DONO`, `GERENTE`, `CORRETOR`, `ASSISTENTE`; `User.assistente_de_id`;
  `Convite.assistente_de_id`.

## Bloco B — Núcleo de permissões
*Depende do Bloco A (precisa do enum novo e do campo assistente_de_id).*
- T910 `app/core/rbac.py`: `escopo_visibilidade`, `corretor_id_efetivo`, `pode_excluir`. TDD
  (função pura, sem banco): dono/gerente → `None`; corretor → próprio uuid; assistente com
  vínculo → uuid do corretor; assistente sem vínculo → sentinela (nunca `None`); `pode_excluir`
  falso para assistente sempre, verdadeiro para dono/gerente sempre, condicional para corretor.

## Bloco C — Aplicar nos módulos existentes
*Depende do Bloco B.*
- T920 `imoveis/service.py`: `_garante_visivel`, `listar_imoveis`, `criar_imovel` usam
  `escopo_visibilidade`/`corretor_id_efetivo`. TDD: gerente vê imóvel de qualquer corretor;
  assistente só vê do corretor vinculado; imóvel criado por assistente é atribuído ao corretor,
  não ao assistente.
- T921 `imoveis/service.py`: `inativar_imovel` ganha checagem `pode_excluir` (404 se assistente).
  TDD: assistente não exclui mesmo vendo o imóvel.
- T922 `leads/service.py`: mesmo padrão de T920 para leads.
- T923 `dashboard/service.py`: troca filtro ad-hoc por `escopo_visibilidade`. TDD: métricas de
  gerente somam todos os corretores; de assistente somam só o corretor vinculado.
- T924 `avaliacoes/router.py` + `sugestoes_preco/router.py`: novo `require_pode_avaliar` em
  `core/deps.py`, aplicado nas rotas de cálculo. TDD: assistente recebe 403; corretor/gerente/
  dono continuam funcionando.
- T925 Renomear `require_admin`→`require_dono`, `require_admin_with_2fa`→`require_dono_com_2fa`
  em `core/deps.py`; atualizar chamadores (`licenciamento/router.py`, `precos_mercado/router.py`,
  `leads/router.py` api-key, `tenancy/convites_router.py`). TDD: gerente recebe 403 nessas rotas
  (só dono passa).

## Bloco D — Convites com papel + equipe
*Depende dos Blocos A e C (usa require_dono_com_2fa já renomeado).*
- T930 `ConviteCreateRequest` ganha `papel` (gerente/corretor/assistente — nunca dono) e
  `assistente_de_id` (obrigatório só se papel=assistente). `create_convite` valida: assistente
  exige `assistente_de_id` de um `User` ativo, papel=corretor, do mesmo tenant. TDD: convite de
  assistente sem vínculo é rejeitado; vínculo apontando pra corretor de outro tenant é rejeitado;
  convite de gerente/corretor funciona sem vínculo.
- T931 `aceitar_convite` propaga `assistente_de_id` do convite pro `User` criado.
- T932 `GET /users` (novo, dono/gerente) lista `uuid`/`nome`/`email`/`papel`/`assistente_de_id`
  dos usuários ativos do tenant. TDD: corretor/assistente recebem 403.

## Bloco E — Frontend
- T940 [P] `auth.js`: `isDono`, `isGerente`, `isAssistente`, `temGestao` (dono|gerente),
  `podeAvaliar` (não-assistente) — substitui `isAdmin` em todos os usos.
- T941 [P] `InviteTeamView.vue`: seletor de papel; se assistente, seletor de corretor (via novo
  `GET /users`, filtrado a papel=corretor).
- T942 [P] Esconder botão de excluir imóvel e de avaliar para assistente nas telas relevantes.

## Fechamento
- T950 ✅ `grep -rn "Papel.ADMIN"` no código-fonte não retorna nada.
- T951 ✅ Suíte completa (327 testes) verde, incluindo os módulos 001-009 pré-existentes.
- T952 ✅ Cobertura 97% no total (novo código coberto por `test_rbac.py` +
  `test_rbac_integracao.py`).
- T953 ✅ Fluxo ponta a ponta validado via `test_rbac_integracao.py` (HTTP, não manual no
  navegador): signup→dono, convite+aceite de corretor/gerente/assistente, imóvel criado por
  assistente atribuído ao corretor, exclusão bloqueada pro assistente e liberada pro gerente,
  avaliação/sugestão bloqueada pro assistente. Migração `53f31a2b4f63` validada rodando de fato
  contra Postgres real (Docker) — pegou um bug real (VARCHAR(8) truncando "assistente") que os
  testes com SQLite não detectavam; corrigido antes do push. Tag v0.10.0 pendente do push.

**Dependências entre blocos:** A → B → C → D. E depende de C (gates) e D (endpoint de equipe).
Fechamento depende de todos.
