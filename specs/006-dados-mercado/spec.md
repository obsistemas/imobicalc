# Feature 006 — Dados de Mercado (Importação, Alerta de Subprecificação, Mapa de Calor)

**Status:** Em implementação | **Fase do roadmap:** 6 (Fase 2 do documento
`Proptech_Avaliador_Especificacao.pdf` — "Dados de Mercado") | **Release alvo:** v0.6.0
**Fonte:** `Proptech_Avaliador_Especificacao.pdf` §10 (Fase 2) | **Depende de:** 002-avaliacao
(preco_mercado), 004-leads (canal de notificação em tempo real)

## Resumo

O documento de especificação original lista 4 itens na "Fase 2 — Dados de Mercado": scraper de
preços dos portais (ZAP, Viva Real), importação automática de preços, mapa de calor por região e
alerta de imóveis subprecificados. Esta feature implementa **3 dos 4 itens** — importação em
lote, alerta de subprecificação e mapa de calor — todos construídos sobre o que já existe
(`preco_mercado` da 002, canal de notificação da 004), sem dependência de serviço externo pago.

**Scraper de portais fica fora de escopo desta feature** (ver "Fora de escopo" — decisão de
risco jurídico, não técnica).

## Histórias de usuário (priorizadas)

**US1 (P0) — Importação em lote de preços de mercado.** Como `admin`, quero importar uma
planilha CSV de preços por bairro/cidade/tipo, para atualizar a base de uma vez em vez de
cadastro manual um a um.
- AC1: linha com bairro+cidade+tipo já existente **atualiza** o preço (upsert); combinação nova
  **cria** um registro.
- AC2: linha malformada (campo obrigatório ausente, tipo inválido, preço não-numérico) é
  reportada no resultado da importação (linha + motivo) sem interromper as linhas válidas
  restantes do arquivo.
- AC3: cada linha importada tenta geocodificar bairro+cidade+estado (best-effort) para
  preencher latitude/longitude, usados no mapa de calor (US3); falha de geocodificação nunca
  impede a importação da linha (mesmo princípio de fallback do ViaCEP em 001-fundacao).

**US2 (P0) — Alerta de imóvel subprecificado.** Como corretor, quero ser avisado quando cadastro
ou atualizo um imóvel com valor abaixo do mercado, para não deixar dinheiro na mesa sem perceber.
- AC1: ao criar/atualizar um imóvel com `valor_anunciado` informado, o sistema compara contra o
  preço de mercado esperado (`preco_m2 × área`, com o mesmo fallback genérico por tipo de
  002-avaliacao); se estiver `N%` abaixo (configurável, padrão 15%), emite notificação em tempo
  real no mesmo canal WebSocket já usado para novo lead (004-leads).
- AC2: sem preço de mercado disponível (nem fallback) ou sem `valor_anunciado` informado, nenhum
  alerta é gerado — não há base de comparação, e isso nunca bloqueia o cadastro/atualização.
- AC3: alerta é puramente informativo (tempo real, sem persistência/histórico consultável nesta
  fase) — nunca alterna estado do imóvel nem impede a operação.

**US3 (P0) — Mapa de calor de preços por região.** Como `admin`, quero visualizar um mapa de
calor de preços por região, para identificar rapidamente onde o m² é mais caro/barato.
- AC1: mapa mostra um ponto de calor por combinação bairro+cidade cadastrada em
  `preco_mercado` com coordenada geocodificada, intensidade proporcional ao `preco_m2`.
- AC2: entradas sem coordenada (geocodificação falhou ou nunca rodou) não aparecem no mapa, mas
  continuam válidas para os cálculos de avaliação (002) e alerta (US2) normalmente.

## Fora de escopo

**Scraper de preços dos portais (ZAP, Viva Real ou similares)** — scraping direto de portais de
terceiros tipicamente viola os Termos de Uso deles e expõe a operação a risco de bloqueio de IP
e notificação de cessar-e-desistir; é uma decisão de risco jurídico/negócio, não uma escolha
técnica desta feature, e fica de fora até uma avaliação jurídica ou um provedor de dados
licenciado ser escolhido. · Persistência/histórico consultável de alertas de subprecificação
(só notificação em tempo real nesta fase). · Geocodificação de imóveis individuais (só
`preco_mercado`, regional, é geocodificado — não há necessidade de coordenada por imóvel para o
mapa de calor). · Mapa de calor interativo com drill-down por imóvel (mostra só a agregação
regional de `preco_mercado`).

## Regras de negócio críticas

- RN1: geocodificação usa serviço gratuito sem chave de API (Nominatim/OpenStreetMap), com
  fallback silencioso — nunca bloqueia importação ou cadastro (mesmo padrão do `ViaCepDriver`).
- RN2: threshold de subprecificação é configurável (`settings.subprecificado_threshold`),
  padrão 0.15 (15% abaixo do esperado).
- RN3: importação é resiliente por linha — uma linha malformada não invalida as demais nem o
  arquivo inteiro (nunca all-or-nothing).
- RN4: toda leitura/escrita de `preco_mercado` continua central (sem `tenant_id`) — igual
  002-avaliacao; o alerta de subprecificação, por comparar dado de um imóvel (tenant-scoped)
  contra um preço central, é calculado no contexto do tenant do imóvel, nunca vaza entre tenants.

## Requisitos não funcionais aplicáveis

Artigo I (isolamento — o alerta nunca cruza tenant, mesmo comparando contra dado central) ·
Artigo IV (contrato antes do código) · Artigo VIII (YAGNI — sem tabela de histórico de alerta,
sem geocodificação de imóvel individual, escopo estritamente os 3 itens viáveis sem risco
jurídico).
