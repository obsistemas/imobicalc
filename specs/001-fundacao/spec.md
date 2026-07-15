# Feature 001 — Fundação (Tenancy + Licenciamento + Cadastro de Imóveis)

**Status:** Pronta para /speckit.clarify | **Fase do roadmap:** 1 | **Release alvo:** v0.1.0
**Fonte:** docs/ESPECIFICACAO-MASTER.md §4 (M1, M2, M3) | **Depende de:** nenhuma (feature fundacional)

## Resumo

Estabelece a base sobre a qual todas as demais features são construídas: cada imobiliária/corretor autônomo vira um **tenant** isolado, com autenticação e papéis (`admin`/`corretor`), assinatura de um plano com trial de 7 dias e cobrança via Mercado Pago, e o primeiro cadastro de domínio (imóveis). Sem esta feature, nenhuma outra faz sentido — é o que torna o sistema multi-tenant e monetizável.

## Histórias de usuário (priorizadas)

**US1 (P0) — Criar conta e tenant.** Como visitante, quero criar minha conta e o tenant da minha imobiliária/carteira autônoma, para começar a usar a plataforma.
- AC1: ao completar o cadastro (nome, e-mail, senha, nome do tenant), um tenant é criado com status `trial` e o usuário criado como `admin` desse tenant.
- AC2: o trial dura exatamente 7 dias corridos a partir da criação, sem exigir dados de cartão de crédito.
- AC3: e-mail duplicado (já usado por outro `admin`) é rejeitado com mensagem acionável.

**US2 (P0) — Login e sessão.** Como usuário cadastrado, quero fazer login com e-mail/senha, para acessar meu tenant.
- AC1: login inválido (senha errada) não revela se o e-mail existe ou não.
- AC2: sessão expira após período configurável de inatividade; token JWT carrega `tenant_id` e `papel`.
- AC3: usuário de um tenant nunca consegue autenticar-se "dentro" de outro tenant via manipulação de token.

**US3 (P0) — 2FA para admin.** Como `admin`, quero (ou sou obrigado a) ativar autenticação de dois fatores, para proteger ações administrativas.
- AC1: papel `admin` não consegue executar ações administrativas sensíveis (convidar usuário, mudar plano, ver faturamento) sem 2FA ativo.
- AC2: 2FA usa TOTP (app autenticador) — sem dependência de SMS pago.

**US4 (P0) — Convidar corretor.** Como `admin`, quero convidar um corretor da minha equipe por e-mail, para que ele tenha acesso ao tenant com papel `corretor`.
- AC1: convite expira em 7 dias; corretor define a própria senha ao aceitar.
- AC2: número de usuários ativos nunca excede `max_users` do plano vigente — convite além do limite é bloqueado com mensagem acionável ("Limite do plano atingido — fazer upgrade").

**US5 (P0) — Isolamento entre tenants.** Como plataforma, preciso garantir que nenhum tenant acesse dado de outro, em nenhuma circunstância.
- AC1: toda tabela operacional desta feature (`users`, `imoveis`) tem teste de isolamento (`assert_tenant_isolated`) passando no CI.
- AC2: requisição autenticada de um tenant que tenta acessar recurso de `imovel_id` de outro tenant retorna 404 (não 403 — não revela existência).

**US6 (P0) — Cadastro de imóvel.** Como `corretor`, quero cadastrar um imóvel com dados completos, para começar a gerenciar minha carteira.
- AC1: CEP preenchido aciona auto-complete via ViaCEP (logradouro, bairro, cidade, estado); falha do ViaCEP não bloqueia o salvamento, apenas deixa os campos manuais.
- AC2: campos obrigatórios (título, CEP, bairro, cidade, estado, tipo, área total) são validados antes de salvar; demais campos do modelo de dados são opcionais.
- AC3: imóvel criado além de `max_imoveis` do plano vigente é bloqueado com mensagem acionável.
- AC4: `corretor` só vê/edita os imóveis que ele mesmo cadastrou; `admin` vê todos os imóveis do tenant.

**US7 (P0) — Listagem e filtros de imóveis.** Como usuário do tenant, quero listar e filtrar meus imóveis, para encontrar rapidamente o que preciso.
- AC1: filtros por status, tipo, bairro, cidade e faixa de valor combinam entre si (AND).
- AC2: paginação via `skip`/`limit`, com total de registros retornado no envelope da resposta.

**US8 (P1) — Fatura e cobrança recorrente.** Como `admin`, quero que minha assinatura seja cobrada automaticamente ao final do trial, para continuar usando o sistema sem ação manual.
- AC1: ao final dos 7 dias de trial, se não houver forma de pagamento configurada, o tenant entra em bloqueio suave (RN2).
- AC2: webhook de pagamento do Mercado Pago é processado de forma idempotente pela chave natural do evento (nunca gera fatura duplicada em reprocessamento).
- AC3: fatura paga com sucesso reativa o tenant automaticamente, sem intervenção manual.

**US9 (P1) — Régua de dunning.** Como plataforma, preciso reduzir a inadimplência sem interromper abruptamente o trabalho do corretor.
- AC1: sequência é lembrete (D-3, D0 da cobrança) → bloqueio suave (leitura liberada, escrita bloqueada com HTTP 402) → suspensão (após N dias configuráveis, só regularização e exportação de dados) → cancelamento com retenção de dados por 30 dias.
- AC2: toda transição de estado de licença ocorre à meia-noite (00h America/Sao_Paulo), nunca no meio do expediente.
- AC3: tenant suspenso ainda consegue exportar os próprios dados (imóveis, leads) a qualquer momento.

**US10 (P2) — Acesso por subdomínio.** Como usuário, quero acessar meu tenant por um subdomínio próprio, para ter uma URL previsível.
- AC1: `{slug}.proptechavaliador.com.br` resolve para o tenant correto via middleware, com cache do mapeamento host→tenant.
- AC2: slug é gerado a partir do nome do tenant no cadastro, único, editável pelo `admin`.

## Fora de escopo

Domínio customizado/white-label (feature futura, pós-MVP) · emissão de NFS-e (sistema externo à parte, integração detalhada quando essa necessidade for priorizada) · permissões granulares além de `admin`/`corretor` (feature futura, se necessário) · recuperação de senha via SMS (usar e-mail) · múltiplos gateways de pagamento simultâneos (só Mercado Pago nesta feature) · portal de convite self-service sem e-mail (ex.: link público de auto-cadastro de corretor).

## Regras de negócio críticas

- RN1: nenhuma query de aplicação retorna dado de um `tenant_id` diferente do tenant autenticado na requisição/job — sem exceção, mesmo para debug.
- RN2: trial de 7 dias corridos, sem cartão obrigatório; ao expirar sem forma de pagamento ativa, o tenant entra automaticamente em bloqueio suave (não é excluído nem perde dados).
- RN3: `max_users` e `max_imoveis` do plano vigente são validados de forma síncrona no momento da criação do recurso — nunca permitem ultrapassar o limite, mesmo sob concorrência (constraint/lock no banco).
- RN4: 2FA é obrigatório para o papel `admin` executar ações administrativas sensíveis; `corretor` não precisa de 2FA no MVP.
- RN5: todo webhook de pagamento é idempotente pela chave natural do evento do Mercado Pago — reprocessamento nunca duplica efeito (fatura paga duas vezes, reativação duplicada etc.).
- RN6: transições de estado de licença (trial→active→past_due→suspended→cancelled) ocorrem exclusivamente no job agendado de meia-noite, nunca de forma síncrona numa requisição de usuário.
- RN7: exportação de dados do próprio tenant está disponível em qualquer estado de licença, inclusive suspenso.

## Requisitos não funcionais aplicáveis

Artigo I (isolamento multi-tenant, com teste obrigatório por recurso) · Artigo III (TDD com 100% de cobertura nos caminhos de dinheiro: cálculo de fatura, aplicação de plano, webhook) · Artigo V (dinheiro em `NUMERIC(12,4)`/`Decimal`) · Artigo VII (RBAC, 2FA admin, auditoria de escrita sensível) · RNF001 (API <500ms) · RNF008 (backup diário do Postgres antes de qualquer alteração destrutiva de schema).
