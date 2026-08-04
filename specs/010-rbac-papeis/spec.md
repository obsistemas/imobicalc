# Feature 010 — RBAC: 4 Papéis (Dono, Gerente, Corretor, Assistente)

**Status:** Em implementação | **Fase do roadmap:** 6 (Fase 6 do documento
`Proptech_Avaliador_Especificacao_v1.2.0.pdf` — "Multi-usuário e SaaS Completo") | **Release
alvo:** v0.10.0
**Fonte:** especificação ("Autenticação JWT multi-usuário por tenant (dono, gerente, corretor,
assistente)" + "Permissões granulares por perfil (RBAC)") | **Depende de:** 001-fundacao
(`Papel`, convites), 004-leads, 005-dashboard

## Resumo

Hoje o sistema só tem 2 papéis (`admin`/`corretor`) com uma checagem binária espalhada pelo
código (`if user.papel == Papel.CORRETOR: só vê o próprio`) — não uma matriz de permissões de
verdade. Esta feature expande para os 4 papéis do documento e centraliza a lógica de visibilidade
e permissão num único lugar (`app/core/rbac.py`), em vez de continuar espalhando checagens
ad-hoc módulo por módulo.

`admin` é renomeado para `dono` (mesma pessoa, nome novo — é uma migração de dado, não um papel
novo). `gerente` e `assistente` são genuinamente novos.

**Matriz de permissões (confirmada com o usuário antes de implementar):**

| Ação | Dono | Gerente | Corretor | Assistente |
|---|---|---|---|---|
| Ver imóveis/leads de todos os corretores do tenant | ✅ | ✅ | ❌ (só os próprios) | ❌ (só os do corretor que atende) |
| Cadastrar/editar imóvel e lead | ✅ | ✅ | ✅ (próprios) | ✅ (do corretor que atende) |
| Excluir imóvel | ✅ | ✅ | ✅ (próprios) | ❌ |
| Fazer avaliação / sugestão de preço | ✅ | ✅ | ✅ | ❌ |
| Convidar/gerenciar equipe | ✅ | ❌ | ❌ | ❌ |
| Assinatura, plano, faturas | ✅ | ❌ | ❌ | ❌ |
| Gerenciar integração de portais (feed/webhook API key) | ✅ | ❌ | ❌ | ❌ |

## Histórias de usuário (priorizadas)

**US1 (P0) — Migração do papel `admin` para `dono`.** Como usuário que já era admin de um
tenant, quero continuar com as mesmas permissões depois da atualização, só com o nome do papel
mudado.
- AC1: migration de dado converte toda linha `users.papel = 'admin'` para `'dono'` — nenhum
  usuário existente perde acesso.
- AC2: todo lugar que checava `Papel.ADMIN` passa a checar `Papel.DONO` com o mesmo efeito.

**US2 (P0) — Visibilidade por papel centralizada.** Como desenvolvedor mantendo o sistema, quero
uma única função que decida "o que este usuário pode ver", para não reimplementar essa lógica em
cada módulo novo.
- AC1: `escopo_visibilidade(user)` (novo, `app/core/rbac.py`) retorna `None` (vê tudo do tenant)
  para dono/gerente, `user.uuid` para corretor, `user.assistente_de_id` para assistente.
- AC2: `imoveis` e `leads` (listagem e obtenção individual) usam essa função — nenhum dos dois
  reimplementa a checagem por conta própria.
- AC3: `dashboard` usa a mesma função para as métricas (hoje já filtra por corretor de forma
  ad-hoc — passa a usar a função central).

**US3 (P0) — Assistente vinculado a um corretor.** Como dono/gerente, quero convidar um
assistente e dizer qual corretor ele atende, para que ele veja e cadastre imóveis/leads em nome
desse corretor.
- AC1: `User.assistente_de_id` (novo, nullable) guarda o `uuid` do corretor atendido — só
  populado quando `papel=assistente`.
- AC2: ao criar imóvel/lead como assistente, `corretor_id` do registro criado é o
  `assistente_de_id` do assistente (não o `uuid` do próprio assistente) — o imóvel/lead é
  atribuído ao corretor, não ao assistente.
- AC3: convite de assistente exige `assistente_de_id` apontando para um `User` existente, ativo,
  com `papel=corretor`, do mesmo tenant — senão o convite é rejeitado.

**US4 (P0) — Exclusão restrita.** Como assistente, não posso excluir um imóvel mesmo de um
imóvel que eu vejo/edito normalmente.
- AC1: `DELETE /imoveis/{id}` bloqueia (404, mesmo padrão de não revelar) quando
  `user.papel == assistente`, independente de visibilidade.

**US5 (P0) — Avaliação restrita.** Como assistente, não posso rodar avaliação nem sugestão de
preço.
- AC1: `POST /avaliacao/*` e `POST /avaliacao/sugerir-preco/*` retornam 403 para assistente.

**US6 (P0) — Convite com papel.** Como dono, quero escolher o papel (gerente/corretor/
assistente) ao convidar alguém — hoje todo convite vira corretor, sem escolha.
- AC1: `POST /users/convites` aceita `papel` (obrigatório, um dos 3 — nunca `dono`, não se
  convida um segundo dono por este fluxo) e `assistente_de_id` (obrigatório só se
  `papel=assistente`).
- AC2: `require_dono_com_2fa` (renomeado de `require_admin_with_2fa`) continua exigindo 2FA —
  gerente/corretor/assistente nunca convidam ninguém (só dono, igual já era pra admin).

**US7 (P1) — Listar equipe do tenant.** Como dono/gerente, quero ver quem já está na equipe (não
só convites pendentes), para escolher o corretor certo ao convidar um assistente.
- AC1: `GET /users` (novo endpoint, dono/gerente) retorna `uuid`, `nome`, `email`, `papel`,
  `assistente_de_id` de todos os usuários ativos do tenant.

## Fora de escopo

**Permissões por recurso além de imóvel/lead/avaliação** (ex.: quem pode ver o mapa de calor,
quem pode ver o dashboard) — a matriz confirmada não menciona esses casos; ficam com a regra
atual (qualquer usuário autenticado). · **Múltiplos corretores por assistente** — um assistente
atende exatamente um corretor nesta v1 (`assistente_de_id` é um campo único, não uma lista);
simplificação consciente para o público-alvo (pequenas imobiliárias). · **Remover/trocar membro
de equipe** — convite e aceite já existem; edição de papel de alguém já ativo (ex.: promover
corretor a gerente) fica para uma iteração futura, não pedida na matriz. · **Dono duplo/
transferência de posse** — o fluxo de convite nunca oferece o papel `dono`.

## Regras de negócio

- **RN1 (migração sem perda de acesso):** todo usuário com `papel=admin` antes desta feature
  vira `papel=dono` depois — mesmas permissões, nome novo.
- **RN2 (visibilidade centralizada):** nenhum módulo novo deveria reimplementar a checagem de
  visibilidade por conta própria — sempre via `escopo_visibilidade()`/`corretor_id_efetivo()`
  (`app/core/rbac.py`).
- **RN3 (assistente sem corretor não vê nada):** um assistente com `assistente_de_id=None`
  (estado que não deveria existir em uso normal, já que o convite exige o vínculo) não enxerga
  nenhum imóvel/lead — nunca cai para "vê tudo" por omissão.
- **RN4 (exclusão é mais restrita que visibilidade):** ver/editar um recurso não implica poder
  excluí-lo — assistente é o primeiro papel onde essas duas coisas divergem.
