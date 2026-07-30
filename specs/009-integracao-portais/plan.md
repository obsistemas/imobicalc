# Plano de Implementação — Feature 009: Integração com Portais

**Spec:** ./spec.md | **Constitution Check:** ✅ — sem dependência nova (geração de XML via
`xml.etree.ElementTree` da stdlib, sem biblioteca externa). Segunda feature com rota
verdadeiramente pública que expõe dados em massa de um tenant (o feed lista *todos* os imóveis
disponíveis) — mitigado pelo mesmo Host-header-only já validado em 008.

## Contexto técnico

Estende `backend/app/modules/imoveis/` (migration `finalidade`, `gerar_feed_vrsync` em
`service.py`, endpoint em `router.py`) e `backend/app/modules/leads/` (novo
`criar_lead_portal` em `service.py`, endpoint `POST /webhooks/leads/portais` autenticado por
Basic Auth). Frontend: adicionar a URL do feed à tela de integração já existente
(`IntegracaoApiKeyView.vue`, 008-captacao-leads).

## Pontos de design

1. **`ListingID` = `Imovel.uuid`, não um contador sequencial próprio.** *Por quê:* já é único,
   estável e eu já uso esse valor em todo o resto do sistema — reaproveitá-lo no feed é o que
   permite ao webhook de leads (US2) resolver o tenant sem precisar de uma tabela de mapeamento
   nova. *Alternativa rejeitada:* gerar um ID sequencial só para o feed — exigiria uma tabela
   extra só para traduzir de volta, sem ganho real.

2. **SECRET_KEY do webhook de portais é uma única configuração de sistema, não uma
   `TenantApiKey` por tenant.** *Por quê:* a documentação real do Grupo OLX descreve a chave
   como "por CRM, não por cliente" — é o próprio Proptech Avaliador que se autentica como
   integração, não cada imobiliária individualmente; modelar como chave por tenant seria
   inventar uma granularidade que a API deles não usa. *Alternativa rejeitada:* reaproveitar
   `TenantApiKey`/`X-API-Key` da 008 — formato de payload e mecanismo de auth são incompatíveis
   com o que o Grupo OLX realmente envia.

3. **`clientListingId` desconhecido responde 200, não 404/422.** *Por quê:* a doc deles descreve
   retry automático em qualquer resposta fora de 2xx — um imóvel que não existe mais não passa a
   existir só porque eles tentaram de novo; responder 2xx e logar internamente evita um retry
   loop sem propósito. *Alternativa rejeitada:* 404 — tecnicamente mais "correto" no sentido REST,
   mas gera reenvio infinito sem chance de sucesso.

4. **Sem tabela de fila/histórico de leads recebidos por portal.** *Por quê:* o lead em si já
   fica registrado como `Lead` (mesma tabela de sempre); não há necessidade de um log paralelo
   só para esta origem — consistente com o resto do sistema (nenhum outro canal de captação
   tem log próprio).

## Fases

**P1 — Schema**
Migration: `imoveis.finalidade` (nullable). TDD: imóvel existente continua funcionando com
`finalidade=NULL`; não aparece no feed até ser definida.

**P2 — Feed XML VRSync**
`gerar_feed_vrsync` (função pura: recebe lista de imóveis, devolve string XML) +
`GET /imoveis/publico/feed.xml` (Host-resolved, sem auth, `Content-Type: application/xml`). TDD:
só imóveis disponível+ativo+com finalidade aparecem; `ListingID` bate com `Imovel.uuid`;
`TransactionType`/`PropertyType`/`UsageType` seguem a tabela de mapeamento; imóvel de outro
tenant nunca aparece.

**P3 — Webhook de leads dos portais**
`criar_lead_portal` (resolve tenant via `clientListingId` → `Imovel.uuid`, `system_scope()`) +
`POST /webhooks/leads/portais` (Basic Auth contra `settings.canal_pro_webhook_secret`). TDD:
secret válida cria lead no tenant certo; secret inválida/ausente = 401; `clientListingId`
desconhecido = 200 sem criar lead; incrementa `Imovel.contatos`; emite `lead_criado`.

**P4 — UI**
Mostrar a URL do feed (`https://{slug}.{platform_domain}/api/v1/imoveis/publico/feed.xml`) na
tela de integração já existente, com uma nota sobre rodar o Validador XML oficial antes de
cadastrar no Canal Pro de verdade.

## Riscos

| Risco | Mitigação |
|---|---|
| Schema XML gerado não bater 100% com o que o validador oficial do Grupo OLX exige (documentação pública é parcial) | Documentado explicitamente (spec.md, Fora de escopo) — rodar `developers.grupozap.com/feeds/xml_validator/` antes de cadastrar a URL num Canal Pro real é responsabilidade do usuário, não algo que dá pra verificar por aqui |
| Imóvel sem foto no feed (VRSync exige mínimo 1 imagem) | Aceito nesta v1 — imóvel sem foto entra no feed mesmo assim; se o Grupo OLX rejeitar essas linhas, o resto do feed continua válido (comportamento de feed em lote: uma linha ruim não devia derrubar as outras) |
| `SECRET_KEY` de homologação nunca é obtida (depende de contato comercial com o Grupo OLX) | Webhook fica inerte com `settings.canal_pro_webhook_secret` vazio — mesmo padrão do `SUPERADMIN_EMAIL`, não bloqueia o resto do sistema |
| Payload do Grupo OLX ganhar campos novos sem aviso (mencionado na doc deles) | `criar_lead_portal` ignora campos desconhecidos (parsing tolerante, não `extra="forbid"` no schema Pydantic) |

## Critério de conclusão

ACs de US1-US2 verdes · nenhum teste dos módulos 001-008 quebra com `finalidade` nullable ·
cobertura ≥80% no que foi adicionado · fluxo manual: cadastrar um imóvel com finalidade
definida → conferir `GET /imoveis/publico/feed.xml` → simular um `POST
/webhooks/leads/portais` via curl com o `clientListingId` do imóvel → ver o lead aparecer sem
dono → tag **v0.9.0**.
