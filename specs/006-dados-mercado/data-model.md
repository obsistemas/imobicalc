# Modelo de Dados — Feature 006: Dados de Mercado

Sem tabela nova. Uma alteração de schema (`preco_mercado`) e um evento de domínio novo (sem
persistência — RN de 004-leads de reaproveitar o barramento de eventos in-process).

## Alteração em `preco_mercado` (002-avaliacao)

**preco_mercado** — adiciona `latitude`, `longitude` (`NUMERIC(9,6)`, nullable). Preenchidos via
geocodificação best-effort (bairro+cidade+estado) no momento da criação (`POST` individual) ou
importação (US1); `NULL` quando a geocodificação falha ou não encontra resultado — a linha
continua válida para avaliação/alerta, só não aparece no mapa de calor (US3/AC2).

## Evento de domínio: `imovel_subprecificado`

Não é uma tabela — é um evento in-process (`app/core/events.py`, mesmo barramento de
`lead_criado` em 004-leads), emitido por `imoveis/service.py` ao criar/atualizar um imóvel com
`valor_anunciado` abaixo do esperado (RN2). Consumido por um listener em
`precos_mercado/listeners.py` que publica no canal Redis `tenant.{tenant_id}.notificacoes` (o
mesmo canal WebSocket já usado por 004-leads), com payload:

```json
{
  "tipo": "imovel_subprecificado",
  "imovel": {
    "id": "<uuid>",
    "titulo": "...",
    "valor_anunciado": "...",
    "valor_esperado": "...",
    "percentual_abaixo": 0.18
  }
}
```

## Invariantes

- **Invariante (RN1/Artigo VIII):** nenhuma tabela nova de histórico de alerta — o evento é
  efêmero (tempo real), reaproveitando a infraestrutura já validada de 004-leads.
- **Invariante (RN3):** `preco_mercado.latitude`/`longitude` nulos são um estado válido e
  esperado (não um erro) — geocodificação é best-effort, nunca obrigatória.
- **Invariante (RN4/Artigo I):** o cálculo do alerta de subprecificação sempre parte de um
  `Imovel` já resolvido no contexto do tenant da requisição (via `tenant_scope`); o preço de
  mercado consultado é central (sem tenant_id, igual 002-avaliacao) mas a notificação emitida é
  sempre publicada no canal do tenant do imóvel — nunca em um canal genérico/global.
