# Plano de Implementação — Feature 003: Sugestão de Preço de Anúncio

**Spec:** ./spec.md | **Constitution Check:** ✅ — nenhuma dependência nova (mesma stack de 001/002: FastAPI, SQLAlchemy, Pydantic, pytest).

## Contexto técnico

Um módulo novo: `backend/app/modules/sugestoes_preco` (M5 — função pura de cálculo + persistência
+ endpoints). Depende de `avaliacoes` (002) para `valor_estimado`/`valor_min` já calculados — nunca
recalcula. Reuso: `TenantScopedMixin`, `tenant_scope`, `get_current_user`, padrão de
router/service/schemas/calculos já estabelecido em `avaliacoes`, e a visibilidade por
corretor/admin já implementada em `imoveis.service.obter_imovel`.

## Pontos de design

1. **Função de cálculo pura, sem I/O:** `calcular_sugestao_preco(valor_estimado, valor_min, urgencia)` recebe os valores já resolvidos da avaliação e retorna `(preco_anuncio_sugerido, valor_minimo_aceitavel, fatores)` sem tocar banco. *Por quê:* mesmo racional de `avaliacoes/calculos.py` — trivial de testar exaustivamente por tabela de casos. *Alternativa rejeitada:* calcular direto na service — dificulta testar os 3 perfis e o clamp isoladamente.

2. **Sugestão sempre referencia uma avaliação, nunca recalcula o valor de mercado:** o endpoint recebe `avaliacao_id` (não os inputs da avaliação); a service busca a avaliação via novo helper `obter_avaliacao` (mesmo padrão 404 de `obter_imovel`). *Por quê:* Artigo II por analogia — a sugestão herda a rastreabilidade da avaliação de origem; duplicar os inputs de avaliação na sugestão criaria uma segunda fonte de verdade para o valor de mercado. *Alternativa rejeitada:* sugestão calcular seu próprio valor de mercado — quebraria a reprodutibilidade e duplicaria lógica já existente em `avaliacoes`.

3. **3 perfis fixos de urgência, tabela única e nomeada, fácil de ajustar:** `_FATOR_URGENCIA` em `calculos.py` é a única fonte dos percentuais (ver data-model.md) — trocar um valor é uma linha, sem migração. *Por quê:* Artigo VIII (YAGNI) — não há dado histórico de vendas para justificar um motor de regras mais sofisticado no MVP. *Alternativa rejeitada:* configuração por tenant/admin dos percentuais — prematuro sem demanda validada.

4. **Clamp do valor mínimo aceitável no piso da faixa de confiança da avaliação:** nunca sugere aceitar menos que `avaliacao.valor_min`. *Por quê:* consistência com a garantia de que a avaliação nunca é exibida sem faixa de confiança (Artigo II) — a sugestão não pode contradizer o piso técnico já calculado. *Alternativa rejeitada:* deixar o valor mínimo aceitável cair livremente com a margem de negociação — poderia sugerir aceitar um valor tecnicamente injustificável.

## Fases

**P1 — Migration + Model**
Model `SugestaoPreco` (`TenantScopedMixin`, append-only) + migration Alembic encadeada no head atual.

**P2 — Motor de Cálculo (função pura)**
`calcular_sugestao_preco` — TDD exaustivo por tabela de casos (3 urgências, clamp ativado/não ativado) antes de qualquer persistência.

**P3 — Persistência e Endpoints**
Helper `obter_avaliacao` em `avaliacoes/service.py` (reuso). Service `sugerir_preco` (busca imóvel + avaliação, chama função pura, persiste). Endpoints `POST /imoveis/{imovel_id}/avaliacoes/{avaliacao_id}/sugestoes-preco` e `GET` (histórico, US3).

**P4 — UI**
Bloco de sugestão de preço em `AvaliacaoView.vue`, ativo após uma avaliação ser calculada: seletor de urgência + resultado (preço sugerido + valor mínimo aceitável + margem) sempre exibidos juntos.

## Riscos

| Risco | Mitigação |
|---|---|
| Percentuais fixos de urgência não refletirem a realidade de um mercado específico | Documentados como decisão de MVP em `data-model.md`, em constante única e nomeada — fácil revisar após uso real |
| Confundir "avaliação" com "sugestão" na UI (usuário não entender que a sugestão depende de uma avaliação prévia) | Bloco de sugestão só aparece após `resultado` de uma avaliação existir na mesma tela, nunca como fluxo independente |

## Critério de conclusão

ACs de US1-US3 verdes · cobertura ≥80% no módulo `sugestoes_preco` · nenhuma sugestão exibida sem
urgência + margem + valor mínimo aceitável (Artigo II por analogia, teste automatizado) · teste de
isolamento de tenant em `sugestoes_preco` (Artigo I) · fluxo manual completo testado: calcular uma
avaliação → gerar sugestão nas 3 urgências → conferir histórico → tag **v0.3.0**.
