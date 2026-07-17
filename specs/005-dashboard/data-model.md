# Modelo de Dados — Feature 005: Dashboard Analítico

Sem tabela nova de domínio — dashboard é uma camada de leitura/agregação sobre `imoveis` e
`leads` (RN4/Artigo VIII: sem tabela de cache/pré-agregação nesta fase). Única mudança de schema:
um campo novo em `leads`.

## Alteração em `leads` (feature 004)

**leads** — adiciona `fechado_em` (datetime, nullable). Preenchido em `mover_estagio` no momento
exato em que `novo_estagio == EstagioLead.FECHADO` (nunca retroativo, nunca recalculado depois —
mesmo princípio de RN2 de 004-leads: histórico não é reescrito). Índice não é necessário (volume
de leads por tenant no MVP não justifica — Artigo VIII); agregação varre por `tenant_id` (já
indexado) + filtro de data em memória/SQL simples.

## Métricas (todas calculadas sob demanda, escopadas por `tenant_id` e, se `corretor`, por
`corretor_id` — RN1)

### Resumo (cartões)
- `imoveis_por_status`: `COUNT(imoveis WHERE tenant_id=X [AND corretor_id=Y] AND ativo=true) GROUP BY status`.
- `leads_ativos`: `COUNT(leads WHERE tenant_id=X [AND corretor_id=Y] AND estagio NOT IN (fechado, perdido))`.
- `leads_sem_contato`: `COUNT(leads WHERE tenant_id=X [AND corretor_id=Y] AND estagio='novo' AND created_at <= now() - N dias)` — N configurável via query param `dias_sem_contato`, padrão 3.
- `taxa_conversao`: `COUNT(leads WHERE estagio='fechado' AND created_at NO PERÍODO) / COUNT(leads WHERE created_at NO PERÍODO)` — 0 (não erro/NaN) quando não há leads no período.
- `ticket_medio`: `AVG(imoveis.valor_anunciado WHERE status='vendido' AND data_venda NO PERÍODO)` — nulo quando não há venda no período (não zero, para não confundir com "ticket zero").
- `tempo_medio_venda_imovel_dias`: `AVG(data_venda - created_at) WHERE status='vendido' AND data_venda NO PERÍODO`, em dias.
- `tempo_medio_fechamento_lead_dias`: `AVG(fechado_em - created_at) WHERE estagio='fechado' AND fechado_em NO PERÍODO`, em dias.

### Vendas por mês (gráfico, US2)
- Série de N meses (padrão 12, query param `meses`) terminando no mês corrente.
- Por mês: `quantidade` (`COUNT(imoveis WHERE status='vendido' AND data_venda no mês)`) e
  `valor_total` (`SUM(valor_anunciado)` dos mesmos).
- **Invariante (RN2):** mês sem venda entra na série com `quantidade=0, valor_total=0` — a série
  sempre tem exatamente N pontos, gerados no código (não apenas os meses que retornaram linha no
  `GROUP BY`).

### Leads por origem (gráfico, US3)
- `COUNT(leads WHERE tenant_id=X [AND corretor_id=Y] AND created_at NO PERÍODO) GROUP BY origem`.
- Origem sem lead no período não aparece (diferente da série temporal — não há eixo fixo a
  preencher aqui, só as origens que de fato ocorreram).

## Invariantes

- **Invariante (Artigo I/RN1):** toda query de dashboard filtra por `tenant_id` do contexto da
  requisição; se `user.papel == corretor`, filtra adicionalmente por `corretor_id == user.uuid`
  (mesmo padrão de `imoveis`/`leads` já estabelecido).
- **Invariante (RN3):** `leads.fechado_em` só é setado uma vez, no momento da transição para
  `fechado`; se o lead nunca chegou a `fechado`, permanece `NULL` para sempre (não é retropreenchido
  se a régua de negócio mudar no futuro).
