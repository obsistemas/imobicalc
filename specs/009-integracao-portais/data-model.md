# Modelo de Dados — Feature 009: Integração com Portais

Uma alteração de schema (`imoveis.finalidade`), nenhuma tabela nova — o feed é gerado sob
demanda a partir de `Imovel` já existente, e o webhook só cria `Lead` (004-leads).

## Alteração em `imoveis`: `finalidade`

`ENUM('venda', 'aluguel') NULL`. Citado na especificação desde a v1.0.0, nunca implementado —
mesmo padrão do gap de `views`/`contatos` fechado em 008-captacao-leads. `NULL` é um estado
válido (imóvel cadastrado antes desta feature, ou o corretor ainda não definiu) — nesse caso o
imóvel simplesmente não entra no feed (RN2), sem quebrar nada que já funcionava.

## Mapeamento `Imovel` → `Listing` (VRSync)

Schema real obtido em `developers.grupozap.com/feeds/vrsync/*` (namespace
`http://www.vivareal.com/schemas/1.0/VRSync`).

**Header** (dados do feed, não do imóvel — um por arquivo):

| Campo VRSync | Valor |
|---|---|
| `Provider` | nome fixo da aplicação (ex.: "Proptech Avaliador") |
| `Email` | e-mail de contato configurável (`settings`) |
| `ContactName` | nome do tenant (`Tenant.nome`) |
| `PublishDate` | timestamp de geração do feed |
| `Telephone` | fixo/configurável — RNF: sem telefone de contato hoje no cadastro do tenant, usa um valor institucional |

**Listing** (por imóvel):

| Campo VRSync | Origem em `Imovel` | Observação |
|---|---|---|
| `ListingID` | `uuid` | permite rastrear de volta no webhook (US2/AC3) |
| `Title` | `titulo` | truncado/preenchido para respeitar 10-100 chars exigidos |
| `TransactionType` | `finalidade` | `venda`→`For Sale`, `aluguel`→`For Rent` (RN3: nunca `Sale/Rent`) |
| `Location.Country/State/City/Neighborhood` | `estado`/`cidade`/`bairro` | `Country` fixo `Brazil` |
| `PostalCode` | `cep` | |
| `Media` | `fotos` (JSON) | mínimo 1 imagem exigido pelo schema — imóvel sem foto não deveria ir ao feed em produção (ver Riscos no plan.md) |
| `ContactInfo` | dados do tenant/corretor | nome+email mínimo |

**Details** (características):

| Campo VRSync | Origem em `Imovel` |
|---|---|
| `Description` | `descricao` (50-3000 chars exigidos pelo schema — descrição menor é preenchida/ajustada) |
| `PropertyType`/`UsageType` | `tipo` — ver tabela de mapeamento abaixo |
| `LivingArea` | `area_total` |
| `ListPrice` (venda) / `RentalPrice` (aluguel) | `valor_anunciado` |
| `Bedrooms` | `quartos` |
| `Bathrooms` | `banheiros` |
| `Suites` | `suites` |
| `Garage` | `vagas` |
| `Iptu` | não existe hoje em `Imovel` (só `iptu_quitado`, um boolean) — omitido |

**Mapeamento `ImovelTipo` → `UsageType`/`PropertyType`** (valores exatos confirmados na
documentação; decisão de simplificação onde `ImovelTipo` não tem granularidade suficiente):

| `ImovelTipo` | `UsageType` | `PropertyType` |
|---|---|---|
| `apartamento` | `Residential` | `Residential / Apartment` |
| `casa` | `Residential` | `Residential / Home` |
| `terreno` | `Residential` | `Residential / Land Lot` (simplificação — VRSync também tem `Commercial / Land Lot`, mas `ImovelTipo` não distingue) |
| `comercial` | `Commercial` | `Commercial / Business` (genérico — sem granularidade fina no `ImovelTipo`) |
| `galpao` | `Commercial` | `Commercial / Industrial` |

## Payload real do webhook de leads (Grupo OLX)

Confirmado via `developers.grupozap.com/webhooks/integration_leads.html` — **não é o mesmo
formato do webhook genérico da 008-captacao-leads**:

```json
{
  "leadOrigin": "Grupo OLX",
  "timestamp": "2017-10-23T15:50:30.619Z",
  "originLeadId": "59ee0fc6e4b043e1b2a6d863",
  "originListingId": "87027856",
  "clientListingId": "a40171",
  "name": "Nome Consumidor",
  "email": "nome.consumidor@email.com",
  "ddd": "11",
  "phone": "999999999",
  "message": "Olá, tenho interesse neste imóvel...",
  "temperature": "Alta",
  "transactionType": "SELL",
  "extraData": { "leadType": "CONTACT_CHAT" }
}
```

`clientListingId` é o `ListingID` que eu mesmo atribuí no feed — ou seja, é literalmente o
`Imovel.uuid` (ver US1/AC3). Leads do tipo MCMV (financiamento) não têm `clientListingId` nem
`originListingId` — fora de escopo (spec.md).

**Autenticação:** HTTP Basic Auth — o header `Authorization: Basic <base64>` é decodificado e
comparado contra uma `SECRET_KEY` única do sistema (`settings.canal_pro_webhook_secret`), não
uma chave por tenant (RN4) — diferente do padrão `TenantApiKey` da 008.

## Invariantes

- **Invariante (RN1/Artigo I):** nenhuma leitura/escrita tenant-scoped acontece antes do tenant
  ser resolvido — Host header no feed, lookup de `clientListingId` no webhook.
- **Invariante (RN2):** o feed nunca inclui um imóvel com `finalidade IS NULL` — imóvel
  cadastrado antes desta feature simplesmente não aparece até o corretor definir a finalidade.
