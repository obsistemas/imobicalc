# Plano de Implementação — Feature 008: Captação Automática de Leads

**Spec:** ./spec.md | **Constitution Check:** ✅ — sem dependência nova de backend/frontend
(`secrets`/`hashlib` da stdlib para a API key). Primeira feature com rotas verdadeiramente
públicas (sem JWT) que escrevem em tabela tenant-scoped — mitigado reaproveitando 100% do
mecanismo de resolução de tenant por Host já validado em 001-fundacao, sem inventar um segundo
caminho.

## Contexto técnico

Estende `backend/app/modules/leads/` (models: `corretor_id` nullable + `TenantApiKey`; service:
`criar_lead_publico`, `criar_lead_webhook`, `gerar_api_key`, `obter_status_api_key`; router: 3
rotas novas) e `backend/app/modules/imoveis/` (service: `obter_imovel_publico` + increment de
`views`/`contatos`). Frontend: nova view pública `PublicoImovelView.vue` (fora do guard de
autenticação) e uma tela de gestão da API key na área do admin.

## Pontos de design

1. **Reaproveitar o Host-header fallback já existente em vez de inventar uma segunda forma de
   resolver tenant para rota pública.** *Por quê:* `IdentifyTenantMiddleware`/
   `resolve_tenant_uuid_by_host` foram construídos em 001-fundacao especificamente para "rotas
   públicas por tenant" (ver docstring do middleware) — esta é a primeira feature que de fato
   usa esse caminho para além de testes unitários; usá-lo aqui é validar uma peça da arquitetura
   que já existia dormente. *Alternativa rejeitada:* aceitar um `tenant_id`/`slug` explícito no
   path ou body do request público — abriria a porta para um visitante forjar o tenant de
   qualquer imobiliária só sabendo o UUID, o oposto do que Host-header-only garante.

2. **API key com hash SHA-256 (lookup direto), não bcrypt (verificação lenta por design).**
   *Por quê:* bcrypt é lento de propósito para dificultar força bruta de senha humana de baixa
   entropia — mas aqui a chave já nasce com 256 bits de entropia (`secrets.token_urlsafe(32)`),
   então o problema que bcrypt resolve não existe; em compensação, o webhook precisa localizar
   o tenant *pelo hash* (`WHERE key_hash = :hash`), o que bcrypt não permite fazer diretamente
   (cada verificação bcrypt é contra um hash específico, não pesquisável por igualdade).
   *Alternativa rejeitada:* bcrypt como senha — exigiria iterar todas as chaves da plataforma
   tentando cada uma (O(tenants) por webhook, cresce mal) só para manter uma "boa prática" que
   não se aplica a segredos de alta entropia.

3. **`corretor_id` nullable em vez de um usuário "sistema" fictício.** *Por quê:* um usuário
   fictício (`corretor_id` apontando para uma conta "robô") mentiria sobre quem é o dono do
   lead e exigiria criar essa conta em todo tenant (mais um caso especial em `signup`/seed);
   `NULL` é honesto — "ninguém pegou este lead ainda" — e já é um valor totalmente suportado
   pelo tipo da coluna (era `NOT NULL` só por nunca ter existido um caminho sem corretor
   logado). *Alternativa rejeitada:* atribuir automaticamente ao primeiro admin do tenant —
   viraria gargalo em qualquer tenant com mais de um corretor.

4. **Sem tela de "assumir lead" nesta versão.** *Por quê:* o pipeline existente já permite mover
   estágio e adicionar nota em qualquer lead visível — para tenants pequenos (RNF: 1-10
   corretores) um lead sem dono visível a todos é suficiente para alguém agir; formalizar
   "assumir" (travar para um corretor só) é otimização prematura sem sinal de que vira
   problema real. *Alternativa rejeitada:* endpoint de atribuição agora — YAGNI até aparecer
   fricção de equipe de verdade.

## Fases

**P1 — Schema**
Migration: `leads.corretor_id` nullable + tabela `tenant_api_keys`. TDD: nenhuma migração de
dado necessária (coluna já aceita NULL a partir de agora, linhas existentes mantêm seus valores).

**P2 — Página pública do imóvel**
`GET /imoveis/publico/{id}` (Host-resolved, sem auth). TDD: só `disponivel`+`ativo` responde;
outro tenant/host não resolvido = 404; campos internos nunca aparecem no DTO; `views` incrementa
a cada chamada bem-sucedida.

**P3 — Formulário público de interesse**
`POST /leads/publico`. TDD: cria lead com origem=site, corretor_id=None; exige telefone OU
email (RN3); imovel de outro tenant/indisponível = 404; incrementa `Imovel.contatos`; emite
`lead_criado` no canal WS certo (reaproveita padrão de teste de `test_notificacoes_ws.py`).

**P4 — Gestão de API key**
`POST`/`GET /leads/integracao/api-key` (admin-only). TDD: gerar retorna texto plano uma vez;
gerar de novo invalida a chave anterior; GET nunca retorna a chave; não-admin recebe 403.

**P5 — Webhook de leads**
`POST /webhooks/leads` (X-API-Key). TDD: chave válida cria lead no tenant certo; chave ausente/
inválida = 401; `origem` default outro; `imovel_id` opcional, valida pertencer ao tenant da
chave; `last_used_at` atualiza.

**P6 — Ajuste de visibilidade (RN7)**
`leads/service.py`: `_garante_visivel`/`listar_leads` passam a tratar `corretor_id=None` como
visível para qualquer corretor do tenant. TDD: corretor A vê lead sem dono; corretor A não vê
lead do corretor B; admin vê tudo (comportamento já existente, só confirma que não regrediu).

**P7 — UI**
`PublicoImovelView.vue` (rota pública, sem guard de autenticação) com dados do imóvel +
formulário de interesse. Tela de gestão da API key na área de admin (gerar/copiar/ver status).

## Riscos

| Risco | Mitigação |
|---|---|
| Spam no formulário público / webhook (sem CAPTCHA/rate limit) | Aceito nesta v1, documentado como limitação conhecida (mesmo racional já usado no `DEPLOY.md`) |
| API key vazada dá acesso de escrita de leads no tenant inteiro, sem expiração | Rotação é imediata e de um clique (RN4); orientar o usuário a regenerar se suspeitar de vazamento — mesma lógica de "revogar e recriar" já usada em outras integrações de mercado |
| Lead sem dono nunca é notado por ninguém em um tenant com só 1 corretor ausente | Aceitável — mesmo risco de um lead manual esquecido; fora do escopo desta feature resolver gestão de ausência de equipe |

## Critério de conclusão

ACs de US1-US2 verdes · nenhum teste dos módulos 001-007 quebra com `corretor_id` nullable ·
cobertura ≥80% no que foi adicionado · fluxo manual: abrir a página pública de um imóvel
disponível → confirmar `views` incrementou → enviar o formulário de interesse → ver o toast em
tempo real na conta do corretor → gerar uma API key como admin → simular um `POST
/webhooks/leads` via curl → ver o lead aparecer na listagem sem dono → tag **v0.8.0**.
