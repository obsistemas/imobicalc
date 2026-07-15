# Especificação Master — Proptech Avaliador

**Versão:** 2 (decisões tomadas) | **Data:** 2026-07-14 | **Autor:** Omar Alejandro Balcon Benvenuto (produto) + arquitetura assistida

---

## 1. Visão e objetivos de negócio

O **Proptech Avaliador** é uma plataforma SaaS multi-tenant para corretores autônomos e pequenas imobiliárias (1-10 corretores) que precisam de uma ferramenta acessível para:

- Calcular o valor de mercado de imóveis usando métodos técnicos reconhecidos (Comparativo, Reprodução, Renda), inspirados na NBR 14.653/IBAPE, como **estimativa de apoio à decisão** do corretor.
- Gerenciar a carteira de imóveis com cadastro completo de características e documentação.
- Acompanhar leads e oportunidades com pipeline de vendas.
- Sugerir preços de anúncio otimizados conforme o prazo de venda desejado pelo proprietário.
- Fornecer dashboards analíticos com métricas de desempenho do corretor/imobiliária.

**Diferencial competitivo:** avaliação técnica automatizada (nenhum CRM imobiliário brasileiro popular oferece isso integrado), preço acessível para corretor autônomo, operação multi-tenant em VPS próprio (custo controlado, sem dependência de cloud enterprise).

**Modelo de negócio:** SaaS multi-tenant centralizado. Cada imobiliária/corretor autônomo é um tenant isolado, com assinatura mensal recorrente, trial de 7 dias sem cartão obrigatório, 3 planos por limites de uso:

| Plano | Usuários | Imóveis | Preço |
|---|---|---|---|
| Solo | 1 | até 50 | R$ 39/mês |
| Pro | até 5 | ilimitados | R$ 79/mês |
| Enterprise | 10+ | ilimitados | sob consulta |

## 2. Não-objetivos (nesta fase)

- **Não** é ferramenta de laudo técnico com validade legal (sem ART/RRT, sem assinatura digital de engenheiro/avaliador credenciado) — é estimativa interna de apoio à precificação.
- **Não** inclui scraper automatizado de portais (ZAP, Viva Real) nem importação automática de preços de mercado — entrada de dados de mercado é manual/curada no MVP.
- **Não** inclui geração de conteúdo por IA (descrições, SEO, previsão de preço) — módulo preparado na estrutura, mas sem integração ativa.
- **Não** inclui domínio customizado por tenant (white-label) — todo tenant acessa via subdomínio da plataforma no MVP.
- **Não** inclui portal público para o proprietário/comprador do imóvel acompanhar status — acesso é restrito aos usuários do tenant (`admin`/`corretor`).
- **Não** inclui app mobile nativo — o bundle web responsivo (PWA leve) cobre o uso em campo.
- **Não** inclui integração cartorária, módulo de locação (contratos/boletos), marketplace entre corretores nem expansão para outros países — mantidos no roadmap de longo prazo, não detalhados nesta especificação.
- **Não** inclui agente local/hardware — não há dispositivos físicos no domínio deste produto.

## 3. Perfis de usuário e interfaces

Um único arquétipo de perfil no MVP: **Gestor/Corretor**, com dois papéis de RBAC dentro do tenant:

| Papel | Acesso |
|---|---|
| `admin` | Vê e gerencia todos os imóveis, leads, avaliações e dashboards do tenant; gerencia usuários (`corretor`) e configurações da assinatura. |
| `corretor` | Vê e gerencia apenas a própria carteira de imóveis e leads. |

Interface: desktop-first responsiva (menu lateral + cabeçalho fixo), totalmente utilizável em mobile para cadastro em campo (ver [PADROES-DE-INTERFACE.md](../PADROES-DE-INTERFACE.md)). Bundle único `frontend/apps/corretor`.

## 4. Módulos funcionais

**M1 — Tenancy e Autenticação** *(fundação, novo em relação ao documento de origem)*
Cadastro de tenant (imobiliária), autenticação por usuário (login/senha + 2FA para `admin`), papéis `admin`/`corretor`, resolução por subdomínio.

**M2 — Licenciamento e Cobrança** *(fundação, novo)*
Planos Solo/Pro/Enterprise por limites (nº de usuários, nº de imóveis), licença por tenant, trial de 7 dias sem cartão obrigatório, faturas e webhooks via Mercado Pago, régua de dunning (lembrete → bloqueio suave → suspensão → cancelamento). Emissão de NFS-e é feita por sistema externo à parte, fora do escopo deste módulo.

**M3 — Cadastro e Gestão de Imóveis** *(RF001, RF009 do documento de origem)*
Cadastro completo (localização com auto-complete de CEP via ViaCEP, características físicas, conservação, valores, documentação, fotos), listagem com filtros (status, tipo, bairro, cidade, faixa de valor) e paginação.

**M4 — Motor de Avaliação** *(RF002-RF004)*
Três métodos: Comparativo Direto (homogeneização por idade/conservação, faixa de confiança), Reprodução/Reposição (custo de construção + depreciação + terreno), Renda/Capitalização (renda mensal, despesas operacionais, taxa de capitalização).

**M5 — Sugestão de Preço de Anúncio** *(RF005)*
Três perfis de urgência (Rápido/Normal/Máximo), margem de negociação, preço de anúncio sugerido e valor mínimo aceitável. Sempre uma sugestão — o corretor decide o valor final.

**M6 — Gestão de Leads / Pipeline** *(RF006)*
Cadastro de lead, origem, vinculação a imóvel, pipeline (novo→contatado→visita→proposta→fechado/perdido), notas/histórico, notificação em tempo real de novo lead (WebSocket).

**M7 — Dashboard Analítico** *(RF007)*
Métricas de imóveis/leads/conversão/ticket médio/tempo médio de venda, gráficos de vendas por mês e leads por origem, atualização em tempo real.

**M8 — Base de Preços de Mercado** *(RF008)*
Referência de preço médio do m² por bairro/cidade/tipo, **central e compartilhada entre todos os tenants**, com fallback genérico por tipo quando não há dado regional. Entrada manual/curada no MVP (sem scraper).

**M9 — Geração de Conteúdo com IA** *(RF010, preparado — fora de escopo de implementação nesta fase)*
Estrutura de módulo reservada para descrições/SEO e previsão de tendência de preço, sem integração ativa.

## 5. Histórias principais

- **US-M1** Como corretor autônomo, quero criar minha conta e assinar um plano, para começar a usar a plataforma no trial de 7 dias sem compromisso.
- **US-M1** Como `admin` de uma imobiliária, quero convidar corretores da minha equipe, para que cada um gerencie sua própria carteira dentro do mesmo tenant.
- **US-M2** Como `admin`, quero ver claramente quando meu plano está perto do limite (imóveis/usuários), para decidir fazer upgrade antes de ser bloqueado.
- **US-M3** Como corretor, quero cadastrar um imóvel rapidamente com auto-complete de CEP, para não digitar endereço manualmente.
- **US-M4** Como corretor, quero calcular o valor de mercado de um imóvel pelo método comparativo, para justificar tecnicamente um preço ao proprietário.
- **US-M4** Como corretor, quero ver a faixa de confiança e os comparáveis usados, para entender a margem de segurança da estimativa.
- **US-M5** Como corretor, quero receber uma sugestão de preço de anúncio conforme a urgência do vendedor, para negociar com dados objetivos.
- **US-M6** Como corretor, quero ser notificado em tempo real quando um lead novo chega, para responder rapidamente.
- **US-M7** Como `admin`, quero ver a taxa de conversão e o tempo médio de venda da equipe, para identificar gargalos no funil.

## 6. Arquitetura resumida

Ver detalhamento em [ARQUITETURA-REFERENCIA.md](../ARQUITETURA-REFERENCIA.md) e [PADROES-DE-INTERFACE.md](../PADROES-DE-INTERFACE.md). Resumo das decisões tomadas:

- **Backend:** FastAPI (Python 3.12+), SQLAlchemy 2.0 + Alembic, Postgres 16 como base única.
- **Multi-tenancy:** `tenant_id` em toda tabela operacional, exceto tabelas centrais (`plans`, `licenses`, `preco_mercado`); resolução por subdomínio.
- **Frontend:** Vue 3 + Vite + Pinia + Tailwind, bundle único `corretor`, PWA responsivo.
- **Filas/cache:** Redis + RQ.
- **Tempo real:** WebSockets nativos do FastAPI + Redis pub/sub, habilitado desde o MVP (notificação de lead, atualização de dashboard).
- **Pagamento:** Mercado Pago (decidido — driver pattern permite troca futura). Emissão de nota fiscal (NFS-e) da assinatura fica a cargo de um sistema externo à parte, não pelo gateway de pagamento.
- **Infra:** VPS + Docker Compose (nginx, backend, worker, postgres, redis); Caddy reservado para quando houver domínio customizado.
- **CI/CD:** GitHub Actions, gates de lint/estática/teste/cobertura/isolamento de tenant, deploy por tag SemVer.

## 7. Requisitos não funcionais

- **RNF001 Performance:** API < 500ms em 95% das requisições; carregamento inicial < 2s.
- **RNF002 Disponibilidade:** uptime ≥ 99,5% em VPS; Docker Compose com restart automático.
- **RNF003 Segurança/LGPD:** CORS restrito por domínio; HTTPS obrigatório; RBAC por tenant; 2FA para `admin`; auditoria de escrita sensível; dados de lead tratados sob legítimo interesse do corretor (aviso de privacidade padrão + opt-out/remoção mediante solicitação, sem checkbox de consentimento explícito no MVP).
- **RNF004 Escalabilidade:** Postgres desde o início (sem migração futura de banco); backend stateless, escalável horizontalmente.
- **RNF005 Usabilidade:** interface responsiva mobile-first onde relevante; auto-complete de CEP; feedback visual em todas as ações; acessibilidade AA.
- **RNF006 Manutenção:** código modular por domínio; testes automatizados; logs estruturados (structlog); documentação inline mínima (só onde o "porquê" não é óbvio).
- **RNF007 Compatibilidade:** Backend Python 3.12+; Frontend Chrome 90+, Firefox 88+, Safari 14+.
- **RNF008 Backup:** `pg_dump` diário automatizado + retenção configurável; volume Docker para uploads (fotos).
- **RNF009 Custo:** operação em VPS de R$ 30-50/mês na fase inicial (poucos tenants); sem dependência de serviços cloud pagos além do gateway de pagamento e Sentry (free tier).
- **RNF010 Internacionalização:** código preparado para i18n; moeda e formatos em português do Brasil no MVP.
- **RNF011 Isolamento multi-tenant:** teste de isolamento obrigatório por recurso novo (gate de CI) — nenhum tenant acessa dado de outro.

## 8. Fases de implementação

Cada fase = 1 release SemVer, conforme metodologia Spec Kit (feature 001 sempre a fundação).

| Fase | Release | Escopo |
|---|---|---|
| **Fase 1** | v0.1.0 | M1 (Tenancy/Auth) + M2 (Licenciamento/Cobrança) + M3 (Cadastro de Imóveis) — fundação |
| **Fase 2** | v0.2.0 | M4 (Motor de Avaliação, 3 métodos) + M8 (Base de Preços de Mercado) |
| **Fase 3** | v0.3.0 | M5 (Sugestão de Preço de Anúncio) |
| **Fase 4** | v0.4.0 | M6 (Gestão de Leads) + notificação em tempo real |
| **Fase 5** | v0.5.0 | M7 (Dashboard Analítico) |
| **Fase 6+** | a definir | Domínio customizado/white-label, scraper de portais, IA (M9), integração cartorária, expansão internacional, marketplace — roadmap de longo prazo, cada item detalhado só quando priorizado |

## 9. Decisões Tomadas

1. **Planos**: Solo (1 usuário, até 50 imóveis, R$ 39/mês) · Pro (até 5 usuários, imóveis ilimitados, R$ 79/mês) · Enterprise (10+ usuários, sob consulta).

2. **Base legal LGPD para dados de lead**: legítimo interesse do corretor (relação pré-contratual de venda), com aviso de privacidade padrão e opt-out/remoção mediante solicitação — sem checkbox de consentimento explícito no MVP, já que quem insere o dado é o corretor, não o lead diretamente.

3. **Trial de 7 dias sem cartão obrigatório** — cobrança só é configurada ao final do trial, antes do bloqueio suave.

4. **Escopo do WebSocket no MVP**: apenas notificação de novo lead. Contadores de dashboard em tempo real ficam para fase futura, se houver demanda.

5. **Gateway de pagamento: Mercado Pago** (não Asaas). A **emissão de NFS-e da assinatura é feita por sistema externo à parte**, fora do escopo do motor de licenciamento — a integração com esse sistema externo será detalhada quando a feature de licenciamento for especificada.

6. **Número mínimo de comparáveis para o método Comparativo**: 3. Abaixo disso, o sistema avisa e sugere o método de Reprodução como alternativa (não troca automaticamente).

## 10. Glossário

| Termo | Definição |
|---|---|
| Tenant | Uma imobiliária ou corretor autônomo, com dados isolados na plataforma |
| Avaliação Imobiliária | Estimativa técnica do valor de um imóvel, baseada em métodos reconhecidos, sem validade de laudo legal neste produto |
| Método Comparativo | Compara o imóvel com transações/preços similares, ajustando diferenças (homogeneização) |
| Método da Reprodução | Calcula o custo para construir um imóvel equivalente hoje, menos depreciação |
| Método da Renda | Capitaliza a renda que o imóvel gera para estimar seu valor |
| Homogeneização | Processo de ajustar comparáveis para torná-los equivalentes ao imóvel avaliando |
| Trial | Período gratuito (7 dias) antes da cobrança da assinatura |
| Dunning | Régua de cobrança/bloqueio progressivo para inadimplência |
| RBAC | Controle de acesso por papel (`admin`, `corretor`) |
| CEP | Código de Endereçamento Postal, usado para geolocalização (ViaCEP) |
