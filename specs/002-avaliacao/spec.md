# Feature 002 — Motor de Avaliação + Base de Preços de Mercado

**Status:** Em implementação | **Fase do roadmap:** 2 | **Release alvo:** v0.2.0
**Fonte:** docs/ESPECIFICACAO-MASTER.md §4 (M4, M8) | **Depende de:** 001-fundacao (tenancy, licenciamento, imóveis)

## Resumo

Motor de avaliação de imóveis com três métodos técnicos consagrados (NBR 14653 — Avaliação de Bens): Comparativo Direto, Reprodução/Reposição (custo) e Renda/Capitalização. É a invariante central do produto (Artigo II da constituição): toda avaliação registra os fatores, comparáveis e valores intermediários usados no cálculo, nunca só o resultado final, para que o corretor consiga explicar o número meses depois. Depende de uma base de preços de mercado (M8) central e compartilhada entre tenants, com curadoria manual no MVP.

## Histórias de usuário (priorizadas)

**US1 (P0) — Avaliar por método comparativo.** Como corretor, quero calcular o valor de mercado de um imóvel pelo método comparativo direto, para justificar tecnicamente um preço ao proprietário.
- AC1: o cálculo usa o preço médio de m² da base de mercado (bairro+cidade+tipo do imóvel avaliado), com fallback genérico por tipo quando não há dado regional.
- AC2: o valor é homogeneizado por idade e conservação do imóvel (fatores documentados e reproduzíveis).
- AC3: o resultado sempre vem com faixa de confiança (mínimo/máximo) — nunca um número único.

**US2 (P0) — Avaliar por método de custo (reprodução/reposição).** Como corretor, quero calcular o valor de um imóvel pelo custo de reconstrução, para casos sem comparáveis de mercado suficientes (imóvel atípico, terreno com benfeitoria específica).
- AC1: o cálculo soma valor do terreno (preço de mercado do m² de terreno na região) + custo de construção depreciado pela idade/conservação.
- AC2: o custo de construção usa uma referência de custo unitário básico (CUB) por padrão construtivo (baixo/normal/alto), central e compartilhada.

**US3 (P0) — Avaliar por método de renda/capitalização.** Como corretor, quero calcular o valor de um imóvel de renda a partir do aluguel esperado, para imóveis comerciais ou de investimento.
- AC1: o corretor informa renda mensal bruta, despesas operacionais mensais e taxa de capitalização anual (com valor padrão sugerido, editável).
- AC2: o cálculo capitaliza a renda líquida anual pela taxa informada.

**US4 (P0) — Reprodutibilidade da avaliação (Artigo II).** Como corretor, quero acessar uma avaliação já feita meses depois e entender exatamente como o número foi calculado.
- AC1: toda avaliação persiste o método usado, todos os fatores e valores intermediários (não recalculados a partir do estado atual de `imoveis`/`preco_mercado`, que pode ter mudado).
- AC2: nenhuma avaliação é exibida sem método + faixa de confiança/observações técnicas.
- AC3: um imóvel pode ter múltiplas avaliações ao longo do tempo (histórico), nunca sobrescritas.

**US5 (P1) — Base de preços de mercado.** Como `admin`, quero cadastrar/atualizar preços médios de m² por bairro/cidade/tipo, para manter a base de comparação atualizada.
- AC1: entrada é manual/curada nesta fase (sem scraper).
- AC2: a base é central e compartilhada entre todos os tenants (não é dado sensível do tenant).
- AC3: quando não há preço específico do bairro, o sistema usa um valor genérico por tipo de imóvel (fallback), nunca bloqueia o cálculo.

**US6 (P2) — Listagem de avaliações do imóvel.** Como corretor, quero ver o histórico de avaliações de um imóvel, para comparar estimativas ao longo do tempo.
- AC1: lista ordenada por data, mostrando método, valor estimado e faixa de confiança de cada uma.

## Fora de escopo

Sugestão de preço de anúncio a partir da avaliação (feature 003, M5) · geração automática de laudo em PDF (fase futura) · comparáveis reais extraídos de portais externos/scraper (fase futura) · ajuste automático de taxa de capitalização por segmento de mercado (usa valor padrão único configurável nesta fase) · método evolutivo/involutivo da NBR 14653 (não previsto no MVP).

## Regras de negócio críticas

- RN1 (Artigo II): toda avaliação persiste `metodo`, `fatores` (json com todos os inputs e valores intermediários), `valor_estimado`, `valor_min`, `valor_max` e `observacoes` — nunca só o resultado final.
- RN2: avaliação é imutável após criada (histórico append-only) — recalcular gera uma nova avaliação, nunca edita uma existente.
- RN3: preço de mercado é consultado por `bairro+cidade+tipo`; se não encontrado, cai para o registro genérico do `tipo` (`bairro`/`cidade` nulos); se nem esse existir, o cálculo falha com erro acionável (não usa zero silenciosamente).
- RN4: `admin` gerencia a base de preços de mercado; `corretor` só lê (para calcular avaliações).
- RN5: toda avaliação é escopada ao tenant (Artigo I) e ao imóvel; `preco_mercado` é central, sem `tenant_id`.

## Requisitos não funcionais aplicáveis

Artigo II (reprodutibilidade — invariante central desta feature) · Artigo III (TDD obrigatório no motor de cálculo, cobertura ≥80% no módulo) · Artigo IV (contrato OpenAPI antes da rota) · Artigo V (dinheiro/preço em `NUMERIC(12,4)`/`Decimal`) · Artigo VIII (YAGNI — fatores de homogeneização e depreciação documentados como decisão simples e explícita, não um motor de regras genérico).
