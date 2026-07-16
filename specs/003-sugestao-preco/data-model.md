# Modelo de Dados — Feature 003: Sugestão de Preço de Anúncio

Convenções herdadas de 001/002: PK `id` (bigint), `uuid` público, dinheiro `NUMERIC(12,4)`,
tabela tenant-scoped via `TenantScopedMixin`, append-only (mesmo padrão de `avaliacoes`).

## Sugestões de Preço (M5)

**sugestoes_preco** — `tenant_id`, `uuid`, `imovel_id` (uuid do imóvel), `avaliacao_id` (uuid da
avaliação de origem), `corretor_id` (uuid do User que gerou), `urgencia`
(`rapido`|`normal`|`maximo`), `preco_anuncio_sugerido NUMERIC(12,4)`, `valor_minimo_aceitavel NUMERIC(12,4)`,
`fatores` (json — ver "Fórmula" abaixo), `observacoes` (text, nullable), `created_at`.
*(tenant-scoped, append-only — RN4: nunca editada, uma nova sugestão é uma nova linha)*

## Relações-chave e invariantes

- 1 `avaliacao` → N `sugestoes_preco` (histórico, nunca sobrescrito).
- **Invariante (RN1):** `sugestoes_preco` nunca recalcula `valor_estimado`; sempre lê de uma `avaliacao` já persistida.
- **Invariante (RN3):** `valor_minimo_aceitavel >= avaliacao.valor_min` sempre — o clamp é aplicado no cálculo e documentado em `fatores.clamp_aplicado`.
- **Invariante (Artigo I):** toda query a `sugestoes_preco` é automaticamente filtrada por `tenant_id` do contexto da requisição.

## Fórmula (decisão tomada — MVP, valores fixos e fáceis de ajustar em uma única constante)

Perfis de urgência (`app/modules/sugestoes_preco/calculos.py`, tabela `_FATOR_URGENCIA`):

| Urgência | Fator sobre `valor_estimado` | Margem de negociação |
|---|---|---|
| `rapido` | 0.95 (5% abaixo) | 5% |
| `normal` | 1.00 | 8% |
| `maximo` | 1.08 (8% acima) | 12% |

1. `preco_anuncio_sugerido = avaliacao.valor_estimado * fator_urgencia`.
2. `valor_minimo_aceitavel_bruto = preco_anuncio_sugerido * (1 - margem_negociacao)`.
3. `valor_minimo_aceitavel = max(valor_minimo_aceitavel_bruto, avaliacao.valor_min)` — RN3, nunca abaixo do piso da faixa de confiança da avaliação; `fatores.clamp_aplicado = True` quando o bruto era menor que `valor_min`.
4. `fatores` persiste: `valor_estimado_base`, `valor_min_base`, `urgencia`, `fator_urgencia`, `margem_negociacao_pct`, `valor_minimo_aceitavel_bruto`, `clamp_aplicado`.
