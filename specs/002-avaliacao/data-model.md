# Modelo de Dados — Feature 002: Motor de Avaliação + Base de Preços

Convenções herdadas de 001-fundacao: PK `id` (bigint), `uuid` público, dinheiro/preço `NUMERIC(12,4)`, tabelas centrais sem `tenant_id`.

## Base de Preços de Mercado (M8)

**preco_mercado** — uuid, bairro (nullable — nulo representa fallback genérico), cidade (nullable), estado (nullable), tipo (`apartamento`|`casa`|`terreno`|`comercial`|`galpao`), preco_m2 NUMERIC(12,4), fonte (string — origem/curadoria do dado), atualizado_em, created_at. *(central, sem tenant_id — catálogo compartilhado; unique em bairro+cidade+tipo, permitindo NULL+NULL+tipo como linha genérica de fallback)*

**custo_construcao_padrao** — uuid, padrao (`baixo`|`normal`|`alto`), custo_m2 NUMERIC(12,4), atualizado_em. *(central, sem tenant_id — referência tipo CUB/SINDUSCON, seed manual no MVP; usado só pelo método de reprodução/reposição)*

## Avaliações (M4)

**avaliacoes** — tenant_id, uuid, imovel_id (FK imoveis), corretor_id (uuid do User que executou — mesmo padrão de `imoveis.corretor_id`), metodo (`comparativo`|`reproducao`|`renda`), valor_estimado NUMERIC(12,4), valor_min NUMERIC(12,4), valor_max NUMERIC(12,4), fatores (json — todos os inputs e valores intermediários do cálculo, ver "Fórmulas" abaixo), observacoes (text, nullable), created_at. *(append-only — RN2: nunca editada, uma nova avaliação é uma nova linha)*

## Relações-chave e invariantes

- 1 `imovel` → N `avaliacoes` (histórico, nunca sobrescrito).
- `preco_mercado` e `custo_construcao_padrao` são centrais (sem `tenant_id`), lidas por todos os tenants; somente `admin` escreve (RN4).
- **Invariante (Artigo II/RN1):** `avaliacoes.fatores` sempre contém os valores intermediários suficientes para reconstruir o `valor_estimado` sem consultar o estado atual de `imoveis`/`preco_mercado` (que pode ter mudado desde então).
- **Invariante (RN3):** toda leitura de `preco_mercado` primeiro tenta `bairro+cidade+tipo` exato; se não encontrar, tenta `bairro=NULL AND cidade=NULL AND tipo=X`; se nem isso existir, levanta erro (`PrecoMercadoNaoEncontradoError`) — nunca calcula com preço zero/assumido.
- **Invariante (Artigo I):** toda query a `avaliacoes` é automaticamente filtrada por `tenant_id` do contexto da requisição.

## Fórmulas (decisões tomadas — NBR 14653, simplificadas para o MVP)

### Método Comparativo Direto
1. `area = imovel.area_util ou imovel.area_total se area_util for nulo`.
2. `preco_m2_base` = `preco_mercado` por bairro+cidade+tipo do imóvel (fallback genérico por tipo — RN3).
3. **Fator idade**: depreciação linear simples, 1%/ano até no máximo 30% (`fator_idade = max(0.7, 1 - 0.01 * idade_anos)`); imóvel sem `idade_anos` informada usa fator 1.0 (decisão: não penalizar dado ausente).
4. **Fator conservação**: tabela fixa — `otima=1.05`, `boa=1.0`, `regular=0.9`, `ruim=0.75`; nulo usa `1.0`.
5. `valor_estimado = preco_m2_base * area * fator_idade * fator_conservacao`.
6. **Faixa de confiança**: ±10% se o preço veio de dado específico do bairro; ±20% se veio do fallback genérico por tipo (menos precisão, documentado em `fatores.fonte_preco`).

### Método de Reprodução/Reposição (Custo)
1. `valor_terreno = area_total(do imóvel) * preco_m2` de `preco_mercado` com `tipo="terreno"` (mesma busca com fallback do comparativo). *Limitação documentada (Artigo VIII/YAGNI): o modelo `imoveis` não distingue área de terreno de área construída para `casa`; assume-se `area_total` como área do terreno e `area_util` (ou `area_total` se nula) como área construída — método mais adequado a `casa`/`terreno`, uso em `apartamento` é uma aproximação grosseira, sinalizada em `observacoes`.*
2. `area_construida = imovel.area_util ou area_total se nula`.
3. `custo_m2` = `custo_construcao_padrao` pelo padrão construtivo informado pelo corretor no momento do cálculo (`baixo`|`normal`|`alto`).
4. `valor_construcao = area_construida * custo_m2`.
5. **Depreciação física** (Ross-Heidecke simplificada): mesmos fatores de idade/conservação do método comparativo (passo 3-4 acima) aplicados sobre `valor_construcao`.
6. `valor_estimado = valor_terreno + (valor_construcao * fator_idade * fator_conservacao)`.
7. **Faixa de confiança**: ±15% fixo (menor precisão que comparativo com dado específico, por somar duas fontes de incerteza — terreno e custo de construção).

### Método de Renda/Capitalização
1. Inputs do corretor no momento do cálculo: `renda_mensal_bruta`, `despesas_operacionais_mensais`, `taxa_capitalizacao_anual` (sugestão padrão de `0.08` — 8% a.a. — editável).
2. `renda_liquida_mensal = renda_mensal_bruta - despesas_operacionais_mensais` (validação: resultado deve ser > 0).
3. `valor_estimado = (renda_liquida_mensal * 12) / taxa_capitalizacao_anual`.
4. **Faixa de confiança**: ±(variação de 1 ponto percentual na taxa de capitalização para cima/para baixo) — `valor_min` usa `taxa + 0.01`, `valor_max` usa `taxa - 0.01` (taxa maior → valor menor, e vice-versa; taxa mínima de 0.01 para evitar divisão por zero/negativo).
