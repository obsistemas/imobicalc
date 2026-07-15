# Arquitetura de Referência — Proptech Avaliador (SaaS Multi-tenant)

Adaptada do blueprint genérico de SaaS multi-tenant para este projeto. Principais desvios do blueprint padrão, com racional: **backend em FastAPI/Python** (mantendo a base já especificada no documento de origem do produto, em vez do Laravel/PHP do blueprint) e **Postgres** como banco único (em vez de MySQL do blueprint / SQLite do documento de origem).

## 1. Estilo arquitetural

**Monólito modular + frontend multi-app (PWA)** — um único deploy de backend organizado em módulos de domínio (bounded contexts), e um frontend com um bundle por perfil de usuário. Microsserviços só quando um módulo comprovadamente exigir escala/equipe independente.

```
backend/app/modules/{imoveis, avaliacao, leads, dashboard, mercado, tenancy, licenciamento, ...}
  └── router.py · models.py · schemas.py · service.py · events.py · tests/
frontend/apps/{corretor}                 → 1 bundle = 1 perfil de usuário (MVP: só "corretor/gestor")
  └── packages/ui                        → design system compartilhado
```

Comunicação **entre módulos por eventos de domínio** (nunca import direto de service alheio): um módulo publica um evento (`LeadFechado`, `ImovelCadastrado`) num barramento assíncrono interno (ex.: `blinker`/event bus próprio ou fila Redis), outros módulos assinam via listeners. Mantém acoplamento baixo e dá pontos naturais de extensão.

## 2. Stack de referência (decidida para este projeto)

| Camada | Escolha | Papel |
|---|---|---|
| Backend | **FastAPI (Python 3.12+)** | API REST versionada, domínio, filas, agendamento |
| Frontend | Vue 3 + Vite + Pinia + Tailwind | SPA/PWA multi-entry por perfil |
| Banco | **PostgreSQL 16** (base única) | isolamento lógico por tenant via `tenant_id` |
| ORM/Migrations | SQLAlchemy 2.0 + Alembic | mapeamento objeto-relacional + migrations expand/contract |
| Cache/Filas | Redis + RQ (Redis Queue) | filas nomeadas por domínio/prioridade — RQ escolhido por simplicidade (equipe pequena); reavaliar para Celery se surgir necessidade de workflows complexos |
| Tempo real | WebSockets nativos do FastAPI + Redis pub/sub | canais com namespace por tenant, habilitado desde o MVP |
| Testes | Pytest + pytest-cov + mypy + Ruff/Black | TDD nos domínios críticos |
| E2E | Playwright | fluxos de negócio ponta a ponta |
| Observabilidade | Sentry + healthcheck `/health` + logs estruturados (structlog) | erros, filas, uptime |
| Infra | VPS + Docker Compose (nginx, backend, postgres, redis, worker, scheduler) | simples e suficiente até escala média |
| Edge | Caddy (ACME automático) | HTTPS de domínios customizados de tenants (pós-MVP) |
| Pagamento | Mercado Pago ou Asaas (driver pattern) | cobrança recorrente, PIX/boleto/cartão |

## 3. Multi-tenancy (padrão canônico, adaptado a SQLAlchemy)

1. **Base única, `tenant_id` em toda tabela operacional**; tabelas *centrais* (tenants, plans, licenses, invoices, `preco_mercado`) sem tenant_id — `preco_mercado` é intencionalmente central/compartilhada entre todos os tenants (decisão do produto: efeito de rede na base de preços).
2. **Mixin `TenantScopedMixin`**: classe base SQLAlchemy que injeta `tenant_id` + um `event.listens_for` em `before_flush`/query que aplica filtro automático via `contextvars` (equivalente ao global scope do Eloquent). Impossível "esquecer" o filtro.
3. **Resolução por host**: subdomínio (`{slug}.proptechavaliador.com.br`) no MVP; domínio customizado (tabela `domains`) fica para fase de white-label. Middleware FastAPI `IdentifyTenantMiddleware` com cache Redis por host → `TenantContext` (contextvar por request).
4. **Propagação de contexto**: jobs RQ recebem `tenant_id` explícito nos argumentos e restauram o contextvar no worker; canais WebSocket prefixados `tenant.{id}.*`; uploads (fotos de imóveis) segregados em `storage/tenants/{id}/`.
5. **Teste de isolamento obrigatório por recurso**: helper `assert_tenant_isolated(Model)` — tenant A jamais lê/escreve dado do tenant B (gate de CI).
6. **Segredos por tenant** (credenciais de gateway de pagamento quando aplicável): colunas criptografadas (Fernet/`cryptography`), nunca em texto plano.

## 4. Motor de licenciamento e cobrança

- `plans` (features json + limites default: `max_users`, `max_imoveis`) → `licenses` (1 por tenant: preço congelado, limites, overrides de módulos, status trial→active→past_due→suspended→cancelled, ativação).
- `invoices` + `invoice_events`: faturas por ciclo mensal, gateway **Mercado Pago/Asaas** (webhooks idempotentes, chave natural do evento), trilha completa.
- **Trial de 7 dias** a partir da criação do tenant; sem cartão obrigatório na entrada (a definir na especificação da feature de licenciamento).
- **Régua de dunning** configurável: lembretes → bloqueio suave (escrita 402, leitura ok) → suspensão (só regularização + exportação de dados) → cancelamento com retenção. Transições **sempre à meia-noite** — nunca interromper operação no meio do expediente; tenant sempre exporta os próprios dados.
- Enforcement: dependency FastAPI `requires_feature("flag")` + validadores de limite nos pontos de criação (ex.: bloquear novo imóvel se `max_imoveis` atingido).

## 5. Padrões de integração externa

1. **Driver Pattern para todo serviço externo crítico**: interface Python (Protocol/ABC) `PagamentoGatewayDriver`, `GeolocalizacaoDriver` (ViaCEP) + implementações intercambiáveis por config. Permite trocar fornecedor, ter contingência e testar com fakes.
2. **Integração nunca bloqueia o fluxo principal**: chamadas críticas (webhooks de pagamento) em fila RQ dedicada com retry exponencial. Exceção pragmática: consulta de CEP (ViaCEP) é síncrona no cadastro por ser rápida e não crítica — falha vira preenchimento manual, nunca bloqueia o salvamento do imóvel.
3. **Circuito de contingência**: N falhas consecutivas → modo contingência + sonda de saúde → reprocessamento automático do represado (aplica-se a gateway de pagamento e, futuramente, scraper de portais).
4. **Webhooks de entrada**: sempre idempotentes (chave natural do evento), assinados/verificados, processados em fila.
5. **Sem agente local/hardware**: este domínio não tem hardware no cliente (impressoras, balanças, sensores) — padrão do blueprint não se aplica aqui.

## 6. Offline-first

**Não aplicável no MVP.** O perfil único (corretor/gestor) opera híbrido desktop+mobile responsivo, mas com conectividade assumida (uso urbano). PWA com cache básico de assets é suficiente; fila de operações offline (IndexedDB/Dexie) fica para fase futura caso surja demanda real de uso em áreas sem cobertura.

## 7. API e contratos

- REST versionada `/api/v1/...`; contrato **OpenAPI gerado pelo FastAPI a partir dos schemas Pydantic**, revisado antes do código de cada feature (mantendo o espírito "contrato antes do código" — aqui o contrato nasce junto com os schemas Pydantic da spec).
- Respostas via Pydantic response models; erros RFC 9457 (`fastapi-problem` ou handler próprio); paginação/filtro/ordenação padronizados (`skip`/`limit`).
- Frontend não contém regra de negócio.
- Dinheiro e quantidades: `NUMERIC(12,4)` no Postgres, `Decimal` em Python; nunca float.
- Avaliações são **estimativas internas de apoio à decisão** (não laudo legal com validade de ART/RRT) — não exigem snapshot imutável/versionamento pesado no MVP, mas o histórico (`created_at`, valores calculados) é sempre preservado (append-only na tabela `avaliacoes`).

## 8. Segurança e conformidade (baseline)

RBAC simples por tenant (papéis `admin` e `corretor`, sem granularidade de permissões no MVP) · 2FA para papel `admin` · auditoria de toda escrita sensível (quem/quê/quando/antes/depois) · rate limiting · consentimento LGPD com trilha para dados de leads (texto exibido, data, canal) e opt-out imediato · retenção documental configurável · backups diários testados (`pg_dump` agendado).

## 9. CI/CD por tags

```
feature/* → PR → develop  → deploy automático STAGING
develop → PR → main → tag vX.Y.Z → CI completa → aprovação manual → deploy PRODUÇÃO (zero-downtime) → smoke tests
```
- SemVer estrito; Conventional Commits; changelog automático; GitHub Environments com aprovação para produção.
- Deploy por releases+symlink (ou imagem Docker versionada): rollback = symlink/imagem anterior.
- **Migrations expand/contract** via Alembic: sempre compatíveis com a release anterior.
- Gates de CI: lint (Ruff/Black), estática (mypy), testes com cobertura mínima (80% nos módulos críticos: avaliação, licenciamento), build do front, testes de isolamento de tenant.

## 10. Decisões com racional (para reavaliar se necessário)

| Decisão | Racional | Quando mudar |
|---|---|---|
| FastAPI/Python em vez de Laravel/PHP | continuidade com a base já especificada no documento de origem do produto; equipe/ferramentas já pensadas em Python | se a equipe migrar para PHP ou precisar do ecossistema Laravel |
| Postgres em vez de MySQL/SQLite | melhor suporte a JSON/NUMERIC, padrão de mercado com SQLAlchemy, decisão explícita do dono do produto | dificilmente — Postgres escala bem até tenants grandes |
| RQ em vez de Celery | fila simples o suficiente para o volume esperado (webhooks de pagamento, jobs de e-mail); menos operação | se workflows de fila ficarem complexos (retries encadeados, orquestração) |
| `preco_mercado` central (sem tenant_id) | efeito de rede: todos os tenants se beneficiam da mesma base agregada | se corretores exigirem bases privadas/proprietárias de preço |
| Sem offline-first no MVP | perfil de uso é urbano/conectado; complexidade não se paga ainda | se expansão para áreas rurais/baixa conectividade virar prioridade |
| Base única + tenant_id | operação simples, 1 migration p/ todos | tenants gigantes/regulados → schema/db por tenant |
| Monólito modular | equipe pequena, velocidade | módulo com escala própria → extrair serviço |
| VPS + Docker Compose | custo/controle | tráfego alto → k8s/managed |
