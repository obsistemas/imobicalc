# Plano de Implementação — Feature 002: Motor de Avaliação + Base de Preços

**Spec:** ./spec.md | **Constitution Check:** ✅ — nenhuma dependência nova (mesma stack de 001: FastAPI, SQLAlchemy, Pydantic, pytest).

## Contexto técnico

Dois módulos novos: `backend/app/modules/precos_mercado` (M8 — `preco_mercado`, `custo_construcao_padrao`, CRUD restrito a `admin`) e `backend/app/modules/avaliacoes` (M4 — três funções puras de cálculo + persistência + endpoints). `avaliacoes` depende de `imoveis` (001) para os dados físicos do imóvel e de `precos_mercado` para preço base/custo. Reuso: `TenantScopedMixin`, `tenant_scope`/`system_scope`, `require_admin`, `get_current_user`, padrão de router/service/schemas já estabelecido em 001.

## Pontos de design

1. **Funções de cálculo puras, sem I/O:** cada método (`calcular_comparativo`, `calcular_reproducao`, `calcular_renda`) recebe todos os inputs já resolvidos (área, preço de m², idade, conservação etc.) e retorna `(valor_estimado, valor_min, valor_max, fatores)` sem tocar banco. *Por quê:* Artigo III exige TDD rigoroso no motor de cálculo — funções puras são triviais de testar exaustivamente (tabela de casos) sem fixture de banco. A camada de serviço busca os dados (imóvel, preço de mercado) e só então chama a função pura. *Alternativa rejeitada:* calcular direto na service com queries misturadas — dificulta testar todas as combinações de fatores isoladamente.

2. **`preco_mercado` central com fallback por tipo, nunca calcula com zero:** busca específica (bairro+cidade+tipo) com fallback para genérico (tipo apenas); ausência de qualquer um dos dois levanta erro explícito. *Por quê:* Artigo II — uma avaliação sem base de preço real não é reproduzível nem confiável; melhor falhar alto (erro acionável: "cadastre o preço de mercado desta região/tipo") do que silenciosamente estimar com valor arbitrário. *Alternativa rejeitada:* fallback para valor fixo (ex.: R$ 3.000/m²) — mascara ausência de dado real, viola a invariante central do produto.

3. **`avaliacoes` append-only, `fatores` como JSON livre por método:** cada método persiste um payload de fatores com formato próprio (chaves diferentes por `metodo`), sem uma tabela normalizada por fator. *Por quê:* Artigo VIII (YAGNI) — três métodos com fatores bem diferentes normalizados forçariam uma tabela genérica `fator_key/fator_value` prematura; JSON é suficiente para reproduzir o cálculo e é o padrão já usado em `payment_events.payload` e `audit_logs.antes/depois` (001). *Alternativa rejeitada:* schema relacional por fator — over-engineering para 3 métodos fixos e conhecidos.

4. **Corretor escolhe o método, não há "avaliação automática" combinando os três:** o endpoint recebe `metodo` explícito; nenhuma lógica decide sozinha qual método é "melhor" para o imóvel. *Por quê:* mantém "sistema sugere, humano decide" (padrão de interface do produto) — o corretor tem contexto (tem comparáveis? tem renda?) que o sistema não tem nesta fase. *Alternativa rejeitada:* seleção automática de método — exigiria heurística de qualidade de dado fora de escopo do MVP.

## Fases

**P1 — Base de Preços de Mercado (M8)**
Models `preco_mercado`/`custo_construcao_padrao`, seed mínimo de exemplo, service de busca com fallback (RN3), CRUD restrito a `admin` (RF: `admin` cadastra/atualiza; `corretor` só lê via uso indireto no cálculo). Contrato OpenAPI primeiro.

**P2 — Motor de Cálculo (funções puras)**
`calcular_comparativo`, `calcular_reproducao`, `calcular_renda` — TDD exaustivo por tabela de casos (idade/conservação/fallback/taxa) antes de qualquer persistência. Cobertura ≥80% do módulo (Artigo III — motor de cálculo é domínio crítico).

**P3 — Persistência e Endpoints (avaliacoes)**
Model `avaliacoes`, service que busca imóvel + preço de mercado, chama a função pura correspondente e persiste `fatores` completos (RN1), endpoints `POST /imoveis/{id}/avaliacoes` (roteado por `metodo`) e `GET /imoveis/{id}/avaliacoes` (histórico, US6).

**P4 — UI**
Tela de avaliação (seleção de método, inputs específicos por método, resultado com faixa de confiança + observações sempre visíveis — nunca só o número) e listagem de histórico de avaliações do imóvel.

## Riscos

| Risco | Mitigação |
|---|---|
| Base de preços de mercado vazia trava todo cálculo comparativo/custo | Seed inicial com poucas linhas de exemplo + fallback genérico por tipo obrigatório na curadoria inicial |
| Fatores de depreciação/homogeneização simplificados demais para uso profissional real | Documentados explicitamente como decisão de MVP em data-model.md; revisão com corretor real prevista no UAT da feature |
| `area_total` usada como área de terreno é ambígua para apartamento (método de custo) | Observação técnica automática no resultado quando `tipo=apartamento` alertando a limitação (não bloqueia o cálculo) |

## Critério de conclusão

ACs de US1-US6 verdes · cobertura ≥80% no módulo `avaliacoes` (Artigo III, motor de cálculo crítico) · nenhuma avaliação exibida sem método + faixa de confiança/observações (Artigo II, teste automatizado) · teste de isolamento de tenant em `avaliacoes` (Artigo I) · fluxo manual completo testado: cadastrar preço de mercado → avaliar imóvel pelos 3 métodos → conferir histórico → tag **v0.2.0**.
