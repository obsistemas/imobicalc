# Tasks — Feature 002: Motor de Avaliação + Base de Preços de Mercado

Formato: `T1## [P?] [US?] descrição` — [P] = paralelizável. TDD obrigatório (Artigo III: motor de cálculo é domínio crítico, cobertura ≥80% no módulo). Cada task termina com testes verdes + commit convencional. Numeração: feature 002 usa T1xx.

## Bloco A — Base de Preços de Mercado (M8, US5)
- T100 Revisar contrato OpenAPI dos endpoints de `preco_mercado`/`custo_construcao_padrao` (`contracts/openapi.yaml`).
- T101 Migration + Models: `preco_mercado`, `custo_construcao_padrao` (centrais, sem `tenant_id`) + seed mínimo de exemplo (poucas linhas reais + fallback genérico por tipo).
- T102 TDD: busca de preço com fallback (RN3). Casos: bairro+cidade+tipo exato encontrado; fallback para genérico por tipo quando específico não existe; erro explícito quando nem o genérico existe.
- T103 [P] `POST/PUT /admin/precos-mercado` restrito a `admin` (RN4); `corretor` não escreve (403).

## Bloco B — Motor de Cálculo (M4, funções puras, US1-US3)
*Sem I/O — TDD exaustivo antes de qualquer persistência (Artigo III).*
- T110 TDD: `calcular_comparativo`. Casos: fator idade dentro/no limite dos 30% de depreciação; idade ausente usa fator 1.0; fator conservação para os 4 níveis + nulo; faixa de confiança ±10% (dado específico) vs ±20% (fallback genérico).
- T111 TDD: `calcular_reproducao`. Casos: soma terreno + construção depreciada; depreciação aplicada só sobre construção (não sobre terreno); observação automática de limitação quando `tipo=apartamento`; faixa de confiança fixa ±15%.
- T112 TDD: `calcular_renda`. Casos: renda líquida negativa/zero rejeitada com erro; taxa padrão sugerida 8% a.a.; faixa de confiança por variação de 1pp na taxa; taxa mínima 0.01 evita divisão por zero.

## Bloco C — Persistência e Endpoints (avaliacoes, US1-US4, US6)
*Depende do Bloco A (preço de mercado) e Bloco B (funções puras).*
- T120 Migration + Model: `avaliacoes` (tenant-scoped, `TenantScopedMixin`, append-only).
- T121 TDD: `POST /imoveis/{id}/avaliacoes` roteado por `metodo`. Casos: cada método persiste `fatores` completos reproduzíveis (RN1); imóvel de outro tenant retorna 404; preço de mercado ausente (sem fallback) retorna 422 com mensagem acionável, não calcula com zero.
- T122 TDD: `GET /imoveis/{id}/avaliacoes` (histórico). Casos: ordenado por `created_at` desc; nunca retorna avaliação de outro tenant (reforça Artigo I); resposta sempre inclui `valor_min`/`valor_max`/`observacoes` (Artigo II — nunca só o valor final).
- T123 Teste de isolamento de tenant obrigatório (`assert_tenant_isolated`) para `avaliacoes` (Artigo I, gate de CI).

## Bloco D — UI
- T130 [P] Tela de avaliação: seleção de método, formulário de inputs específico por método (idade/conservação já vêm do imóvel; renda/despesas/taxa são inputs livres para o método de renda; padrão construtivo para o método de custo).
- T131 [P] Exibição do resultado: valor estimado + faixa de confiança + observações sempre visíveis (nunca só o número — Artigo II).
- T132 [P] Listagem de histórico de avaliações do imóvel (US6).

## Fechamento
- T140 Cobertura ≥80% no módulo `avaliacoes` e nas funções de cálculo (Artigo III).
- T141 Fluxo manual completo: cadastrar preço de mercado → avaliar imóvel pelos 3 métodos → conferir histórico → tag **v0.2.0**.

**Dependências entre blocos:** A e B paralelizam entre si (sem dependência mútua). C depende de A+B. D (UI) depende de C. Fechamento depende de A+B+C+D completos.
