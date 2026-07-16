# Tasks — Feature 003: Sugestão de Preço de Anúncio

Formato: `T2## [P?] [US?] descrição` — [P] = paralelizável. TDD obrigatório onde há função de cálculo (mesmo racional do Artigo III aplicado por analogia ao motor de avaliação). Cada task termina com testes verdes + commit convencional. Numeração: feature 003 usa T2xx.

## Bloco A — Migration + Model
- T200 Migration + Model: `sugestoes_preco` (tenant-scoped, `TenantScopedMixin`, append-only), encadeada no head atual (`1ee518ccc841`).

## Bloco B — Motor de Cálculo (função pura)
*Sem I/O — TDD exaustivo antes de qualquer persistência.*
- T210 TDD: `calcular_sugestao_preco`. Casos: 3 perfis de urgência (rápido/normal/máximo) com fator e margem corretos; clamp ativado quando `valor_minimo_aceitavel` bruto cai abaixo de `valor_min`; clamp não ativado no caso normal; urgência inválida levanta erro.

## Bloco C — Persistência e Endpoints
*Depende do Bloco A e Bloco B.*
- T220 `obter_avaliacao` em `avaliacoes/service.py` (mesmo padrão 404 de `obter_imovel` — avaliação de outro tenant/imóvel não existe para quem pergunta).
- T221 TDD: `POST /imoveis/{imovel_id}/avaliacoes/{avaliacao_id}/sugestoes-preco`. Casos: cada urgência persiste `fatores` completos; avaliação de outro tenant ou de outro imóvel retorna 404; resposta sempre inclui `valor_minimo_aceitavel` (nunca só o preço sugerido).
- T222 TDD: `GET /imoveis/{imovel_id}/avaliacoes/{avaliacao_id}/sugestoes-preco` (histórico, US3). Casos: ordenado por `created_at` desc; nunca retorna sugestão de outro tenant.
- T223 Teste de isolamento de tenant obrigatório (`assert_tenant_isolated`) para `sugestoes_preco` (Artigo I, gate de CI).

## Bloco D — UI
- T230 Bloco de sugestão de preço em `AvaliacaoView.vue`: seletor de urgência, ativo somente após uma avaliação ser calculada na mesma tela.
- T231 Exibição do resultado: preço de anúncio sugerido + margem de negociação + valor mínimo aceitável sempre visíveis juntos (nunca só o preço).

## Fechamento
- T240 Cobertura ≥80% no módulo `sugestoes_preco`.
- T241 Fluxo manual completo: calcular avaliação → gerar sugestão nas 3 urgências → conferir histórico → tag **v0.3.0**.

**Dependências entre blocos:** A e B paralelizam entre si (sem dependência mútua). C depende de A+B. D (UI) depende de C. Fechamento depende de A+B+C+D completos.
