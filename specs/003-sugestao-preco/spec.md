# Feature 003 — Sugestão de Preço de Anúncio

**Status:** Em implementação | **Fase do roadmap:** 3 | **Release alvo:** v0.3.0
**Fonte:** docs/ESPECIFICACAO-MASTER.md §4 (M5, RF005) | **Depende de:** 002-avaliacao (motor de avaliação)

## Resumo

Tradução do valor técnico calculado pelo motor de avaliação (feature 002) em uma sugestão
prática de "por quanto anunciar": três perfis de urgência do vendedor (Rápido/Normal/Máximo),
cada um com um preço de anúncio sugerido, uma margem de negociação e um valor mínimo aceitável.
O sistema sempre sugere — o corretor decide o valor final (mesmo princípio de "sistema sugere,
humano decide" já aplicado ao motor de avaliação, Artigo II por analogia). Nunca recalcula o
valor de mercado: reaproveita `valor_estimado`/`valor_min` de uma avaliação já persistida.

## Histórias de usuário (priorizadas)

**US1 (P0) — Sugerir preço de anúncio por urgência.** Como corretor, quero receber uma sugestão
de preço de anúncio conforme a urgência do vendedor, para negociar com dados objetivos.
- AC1: o corretor escolhe um perfil de urgência (Rápido/Normal/Máximo) para uma avaliação já calculada.
- AC2: o sistema retorna preço de anúncio sugerido, margem de negociação e valor mínimo aceitável — nunca só um número.
- AC3: o valor mínimo aceitável nunca fica abaixo do `valor_min` (piso da faixa de confiança) da avaliação de origem.

**US2 (P0) — Sugestão sempre ligada a uma avaliação existente.** Como corretor, quero que a
sugestão de preço reaproveite uma avaliação já feita, para manter a mesma rastreabilidade e
reprodutibilidade do motor de avaliação (Artigo II).
- AC1: a sugestão referencia `avaliacao_id` e nunca recalcula `valor_estimado`.
- AC2: uma avaliação de outro tenant ou de um imóvel diferente do informado retorna 404.

**US3 (P1) — Histórico de sugestões.** Como corretor, quero ver as sugestões de preço já geradas
para uma avaliação, para comparar cenários de urgência ao decidir o anúncio.
- AC1: lista ordenada por data, mostrando urgência, preço sugerido e valor mínimo aceitável de cada uma.

## Fora de escopo

Ajuste automático dos fatores de urgência por segmento de mercado ou histórico de vendas (usa
tabela fixa única nesta fase, Artigo VIII/YAGNI) · publicação automática do anúncio em portais
externos (fase futura) · edição/exclusão de sugestões geradas (append-only, mesmo padrão de
`avaliacoes`) · sugestão sem avaliação de origem (não há "avaliação rápida" implícita nesta feature).

## Regras de negócio críticas

- RN1: toda sugestão referencia uma avaliação existente (`avaliacao_id`) do mesmo imóvel/tenant — nunca recalcula `valor_estimado`/`valor_min`/`valor_max`, apenas os lê.
- RN2: três perfis fixos de urgência, com fator sobre `valor_estimado` e margem de negociação documentados em `data-model.md` — valores de decisão de produto no MVP, sem heurística de mercado (Artigo VIII).
- RN3: `valor_minimo_aceitavel` nunca fica abaixo de `avaliacao.valor_min`; se o cálculo bruto cair abaixo, é ajustado (clamp) e o fato é registrado em `fatores.clamp_aplicado`.
- RN4: sugestão é imutável após criada (histórico append-only) — trocar a urgência gera uma nova sugestão, nunca edita uma existente.
- RN5: toda sugestão é escopada ao tenant (Artigo I); a mesma regra de visibilidade por corretor/admin de `imoveis`/`avaliacoes` se aplica (um corretor só sugere/consulta preço de imóveis da própria carteira, exceto `admin`).

## Requisitos não funcionais aplicáveis

Artigo I (isolamento multi-tenant) · Artigo II (por analogia — nunca exibir sugestão sem
margem/valor mínimo, só o preço sugerido) · Artigo IV (contrato OpenAPI antes da rota) · Artigo V
(dinheiro em `NUMERIC(12,4)`/`Decimal`) · Artigo VIII (YAGNI — três perfis fixos, sem motor de
regras genérico de precificação).
