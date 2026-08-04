# Plano de Implementação — Feature 010: RBAC 4 Papéis

**Spec:** ./spec.md | **Constitution Check:** ✅ — sem dependência nova. Maior superfície de
mudança desta feature: renomear `Papel.ADMIN`→`Papel.DONO` toca ~9 arquivos já existentes
(mapeado antes de começar via grep, não por tentativa e erro).

## Contexto técnico

Novo módulo `app/core/rbac.py` (funções puras, sem I/O) + migration de dado + coluna nova em
`users`/`convites` + aplicar as funções novas em `imoveis`, `leads`, `dashboard`,
`avaliacoes`/`sugestoes_preco` (bloqueio de assistente), `licenciamento`/`precos_mercado`/
`leads` (rotas hoje `require_admin`→`require_dono`), `tenancy` (convites com papel).

## Pontos de design

1. **`app/core/rbac.py` como módulo central, não métodos espalhados em cada service.** *Por
   quê:* a spec (RN2) é explícita sobre isso — o problema que motivou a feature era justamente
   checagem de papel duplicada e inconsistente; um módulo central com funções puras é testável
   isoladamente (sem precisar de sessão de banco) e vira o único lugar a revisar quando um papel
   novo aparecer no futuro. *Alternativa rejeitada:* manter `if user.papel == Papel.CORRETOR`
   em cada service, só adicionando mais branches para gerente/assistente — exatamente o padrão
   que a feature existe para eliminar.

2. **Sentinela (`uuid.UUID(int=0)`) para assistente sem vínculo, não `None`.** *Por quê:**
   `escopo_visibilidade() -> None` já tem um significado forte ("vê tudo do tenant") — se
   `assistente_de_id` for `None` e a função devolvesse `None` também, um assistente mal
   configurado acidentalmente enxergaria tudo (o oposto do papel mais restrito do sistema).
   Um sentinel que nunca bate com um `corretor_id` real é mais seguro por padrão (fail-closed).
   *Alternativa rejeitada:* levantar exceção nesse caso — mais "correto" em teoria, mas
   transformaria um estado de dado incomum (não deveria acontecer, mas pode por edição manual)
   em erro 500 em vez de simplesmente não mostrar nada.

3. **`corretor_id_efetivo` só é usado na criação, nunca reavaliado depois.** *Por quê:* se um
   assistente for reatribuído a outro corretor no futuro (fora de escopo desta versão), os
   imóveis/leads já criados continuam com o `corretor_id` de quando foram criados — histórico não
   deveria mudar retroativamente. *Alternativa rejeitada:* recalcular dinamicamente — mais
   "atual", mas reescreveria silenciosamente a atribuição de registros antigos.

4. **Migração de nome (`admin`→`dono`) é só dado, não descontinuar o valor no enum Python de
   forma incompatível.** *Por quê:* como a coluna é `native_enum=False` (string simples), a
   migração de fato é um `UPDATE` — não precisa recriar tipo/coluna, só popular o Python enum
   novo e migrar as linhas existentes na mesma migration.

## Fases

**P1 — Schema**
Migration: `UPDATE users SET papel='dono' WHERE papel='admin'` + `users.assistente_de_id` +
`convites.assistente_de_id` (ambas nullable). Model: `Papel` com os 4 valores.

**P2 — Núcleo de permissões**
`app/core/rbac.py`: `escopo_visibilidade`, `corretor_id_efetivo`, `pode_excluir`. TDD puro (sem
banco): cada papel devolve o escopo esperado; assistente sem vínculo nunca devolve `None`.

**P3 — Aplicar nos módulos existentes**
`imoveis`/`leads` (`_garante_visivel`, `listar_*`, `criar_*` usam as funções do P2);
`dashboard` (troca o filtro ad-hoc); `inativar_imovel` ganha checagem `pode_excluir`;
`avaliacoes`/`sugestoes_preco` ganham `require_pode_avaliar` (bloqueia assistente);
`licenciamento`/`precos_mercado`/`leads` (api-key) trocam `require_admin`→`require_dono`;
`convites_router` troca `require_admin_with_2fa`→`require_dono_com_2fa`.

**P4 — Convites com papel + equipe**
`ConviteCreateRequest` ganha `papel`+`assistente_de_id` (validação: assistente exige vínculo com
corretor existente do tenant); `aceitar_convite` propaga `assistente_de_id` pro `User` criado;
`GET /users` novo (dono/gerente).

**P5 — Frontend**
`auth.js`: `isDono`/`isGerente`/`isAssistente`/`temGestao`/`podeAvaliar`. Telas: seletor de papel
+ corretor (se assistente) em `InviteTeamView`; esconder ações de avaliar/excluir para
assistente onde fizer sentido na UI.

## Riscos

| Risco | Mitigação |
|---|---|
| Esquecer algum lugar que ainda checa `Papel.ADMIN` direto | Mapeado via grep antes de começar (9 arquivos) — lista conferida no fechamento (grep de novo, zero ocorrências de `Papel.ADMIN`) |
| Assistente sem `assistente_de_id` (dado inconsistente, ex. criado manualmente no banco) enxergar tudo por engano | RN3 + sentinela (P2) — testado explicitamente |
| Convite de assistente sem validar que o corretor referenciado existe/é do tenant certo | Validação explícita em `create_convite` antes de gravar |
| `Enum(Papel, native_enum=False)` vira `VARCHAR(N)` dimensionado pelo valor mais longo do enum **no momento em que a coluna foi criada** (migração `4ad4b94bd77c`: `VARCHAR(8)`, de "corretor"). "assistente" tem 10 chars — sem `ALTER COLUMN` alargando a coluna, Postgres rejeita o insert (`value too long`); SQLite (testes) não aplica o limite, então isso só aparece testando contra Postgres real. Descoberto rodando a migração num Postgres real via Docker antes do push, não pelos testes automatizados. Mitigado: `op.alter_column(..., type_=sa.String(10))` em `53f31a2b4f63` antes do `UPDATE`. **Lição para futuras features:** sempre que um `Enum(native_enum=False)` ganhar um valor mais longo que os existentes, a migração precisa alargar a coluna — testes com SQLite não pegam isso. |

## Critério de conclusão

ACs de US1-US7 verdes · `grep -rn "Papel.ADMIN"` no código não retorna nada · nenhum teste dos
módulos 001-009 quebra com a renomeação · cobertura ≥80% no que foi adicionado · fluxo manual:
signup (vira dono) → convidar um corretor → convidar um assistente vinculado a esse corretor →
logar como assistente → cadastrar imóvel (fica atribuído ao corretor) → tentar excluir (bloqueado)
→ tentar avaliar (bloqueado) → tag **v0.10.0**.
