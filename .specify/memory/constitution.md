# Constituição — Proptech Avaliador

Princípios inegociáveis e verificáveis. Cada artigo deve ser testável em revisão de código ou gate de CI. Esta constituição é o contrato entre o dono do produto e os agentes de implementação.

## Artigo I — Isolamento Multi-tenant

Toda tabela operacional carrega `tenant_id`. Nenhum código de aplicação lê ou escreve dado de um tenant sem passar pelo filtro de tenant (`TenantScopedMixin` + contextvar de request/job). Toda feature que introduz um recurso novo (tabela/endpoint) inclui um teste de isolamento (`assert_tenant_isolated`) antes de ser considerada concluída. **Gate de CI**: PR que adiciona tabela operacional sem teste de isolamento é bloqueado.

## Artigo II — Reprodutibilidade da Avaliação

Toda avaliação registra os fatores, comparáveis e valores intermediários usados no cálculo (não só o resultado final), de forma que o mesmo cálculo seja sempre reproduzível a partir dos dados salvos. É a invariante central do produto: um corretor precisa conseguir explicar, meses depois, por que o sistema chegou naquele número. Nenhuma avaliação é exibida sem método usado + faixa de confiança/observações.

## Artigo III — Domínios Críticos e TDD

Dinheiro (licenciamento, cobrança, faturas) e o motor de cálculo de avaliação são domínios críticos: teste antes do código, cobertura ≥80% no módulo, **100% nos caminhos de dinheiro** (cálculo de fatura, aplicação de plano, webhooks de pagamento). Nenhuma PR nesses módulos é aceita sem os testes correspondentes.

## Artigo IV — Contrato Antes do Código

Todo endpoint novo nasce como schema Pydantic (request/response) antes da implementação da rota; o OpenAPI gerado é revisado como parte da spec da feature. Frontend nunca contém regra de negócio — cálculos e validações de domínio vivem no backend.

## Artigo V — Dinheiro Nunca é Float

Valores monetários e quantidades usam `NUMERIC(12,4)` no Postgres e `Decimal` em Python, ponta a ponta (banco → schema → frontend). Uso de `float` para dinheiro é rejeitado em revisão de código.

## Artigo VI — Migrations Expand/Contract

Toda migration Alembic é compatível com a release anterior (expand primeiro, contract só depois que o código antigo não depende mais da coluna/tabela removida). Nenhum deploy quebra a versão anterior em produção durante o rollout.

## Artigo VII — Segurança e LGPD Baseline

RBAC por tenant (`admin`/`corretor`) em todo endpoint sensível · 2FA obrigatório para papel `admin` · toda escrita sensível (avaliação, fatura, mudança de plano) é auditada (quem/quê/quando/antes/depois) · dados de lead tratados sob legítimo interesse, com aviso de privacidade e opt-out/remoção mediante solicitação · segredos (credenciais de gateway) sempre criptografados, nunca em texto plano ou log.

## Artigo VIII — YAGNI

Máximo de 3 níveis de indireção (ex.: router → service → repository). Nenhuma abstração para caso hipotético futuro — resolver o problema atual da feature em questão. Módulos preparados mas não implementados (ex.: geração de conteúdo por IA) ficam como stub explícito, não como camada de abstração especulativa.

## Artigo IX — Idioma

Código, nomes de variáveis/funções/tabelas e mensagens de commit em inglês. Especificações (spec.md, plan.md etc.), textos de interface e comunicação com o usuário final em português do Brasil.

## Artigo X — Qualidade e Gates de CI

Lint (Ruff/Black) · estática (mypy) · testes (pytest) com cobertura mínima conforme Artigo III · build do frontend · teste de isolamento de tenant (Artigo I) · `/speckit.analyze` antes de `/speckit.implement`. `/speckit.implement` executa em blocos revisados por humano — nunca ponta a ponta sem revisão.

## Artigo XI — Observabilidade

Toda exceção não tratada vai para o Sentry; healthcheck `/health` reporta status de banco e fila; logs estruturados (structlog), nunca com dado sensível (senha, token, PII de lead) em texto plano.
