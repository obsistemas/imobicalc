# Feature 009 — Integração com Portais (Feed XML VRSync + Webhook de Leads)

**Status:** Em implementação | **Fase do roadmap:** 3 (Fase 3 do documento
`Proptech_Avaliador_Especificacao_v1.2.0.pdf`, seção "Requisitos da integração com portais
(ZAP/Viva Real) [NOVO v1.2.0]") | **Release alvo:** v0.9.0
**Fonte:** especificação + documentação real consultada em `developers.grupozap.com`
(Portal de Integração do Grupo OLX) | **Depende de:** 004-leads, 008-captacao-leads

## Resumo

A especificação v1.2.0 acrescentou uma seção afirmando que a integração com ZAP/Viva Real (via
Canal Pro, modo "Desenvolvedor Próprio") não exige parceria formal. Consultei a documentação
técnica real do Grupo OLX para confirmar isso e levantar os schemas exatos antes de escrever
qualquer código — dois achados mudam o desenho desta feature em relação ao que a spec
descrevia:

1. **Publicar anúncios é mesmo self-service.** O cliente só cadastra a URL do meu feed XML
   (formato **VRSync**) no Canal Pro; o schema real foi obtido em
   `developers.grupozap.com/feeds/vrsync/*` (ver data-model.md).
2. **Receber leads não é totalmente self-service.** A autenticação do webhook é Basic Auth com
   uma `SECRET_KEY` **por CRM** (não por tenant/imobiliária), obtida através de um processo de
   homologação do software junto ao Grupo OLX — isso contradiz o "sem credenciamento formal" da
   especificação. Esta feature constrói o adaptador pronto para usar essa chave assim que ela
   existir (mesmo padrão de "deixar o env var em branco até você obter o valor real" já usado em
   `SUPERADMIN_EMAIL`/`SUPERADMIN_PASSWORD` na 007-superadmin).

Uma lacuna adicional descoberta durante o levantamento: o schema VRSync exige saber se um
anúncio é venda ou aluguel (`TransactionType`), mas `Imovel` nunca teve esse campo — a
especificação original (v1.0.0) já citava `finalidade: venda | aluguel` na tabela de dados, mas
nunca foi implementado (mesmo padrão do gap de `views`/`contatos` fechado na 008). Esta feature
adiciona esse campo porque o feed não existe sem ele.

## Histórias de usuário (priorizadas)

**US1 (P0) — Feed XML de anúncios (VRSync) por tenant.** Como corretor/admin, quero uma URL de
feed que eu possa cadastrar no meu Canal Pro, para que meus imóveis disponíveis sejam
publicados e atualizados automaticamente no ZAP/Viva Real sem trabalho manual.
- AC1: `GET /imoveis/publico/feed.xml` não exige autenticação; resolve o tenant pelo subdomínio
  (Host header, mesmo mecanismo da página pública de imóvel em 008-captacao-leads).
- AC2: retorna XML válido no formato VRSync (`namespace
  http://www.vivareal.com/schemas/1.0/VRSync`) com um `Listing` por imóvel `status=disponivel`
  e `ativo=True` do tenant — imóvel vendido/alugado/reservado/inativo nunca aparece no feed.
- AC3: `ListingID` de cada `Listing` é o `Imovel.uuid` — permite rastrear de volta o imóvel (e o
  tenant) quando um lead chegar pelo webhook (US2).
- AC4: `TransactionType` reflete `Imovel.finalidade` (venda → `For Sale`, aluguel → `For Rent`);
  imóvel sem finalidade definida não entra no feed (não dá pra publicar sem saber o tipo de
  transação).
- AC5: campos de `Details` (`PropertyType`, `UsageType`, `LivingArea`, `ListPrice`/
  `RentalPrice`, `Bedrooms`, `Bathrooms`, `Garage`, `Suites`, `Description`) preenchidos a partir
  dos campos já existentes de `Imovel` (ver mapeamento em data-model.md).
- AC6 (limitação assumida): a saída não foi validada contra o **Validador XML oficial**
  (`developers.grupozap.com/feeds/xml_validator/`) — isso é um passo manual que você precisa
  rodar antes de cadastrar a URL de verdade num Canal Pro, porque nem toda regra de negócio do
  validador está documentada publicamente.

**US2 (P0) — Webhook de recebimento de leads dos portais.** Como corretor, quero que contatos
recebidos nos meus anúncios do ZAP/Viva Real caiam automaticamente no meu funil de leads.
- AC1: `POST /webhooks/leads/portais` autentica via HTTP Basic Auth contra uma
  `SECRET_KEY` **única para todo o sistema** (não por tenant — assim que a documentação real do
  Grupo OLX descreve: chave por CRM). Requisição sem essa chave, ou com chave errada, retorna
  401.
- AC2: payload aceito é o formato real do Grupo OLX (`leadOrigin`, `clientListingId`, `name`,
  `email`, `ddd`+`phone`, `message`, `timestamp`, `originLeadId`, `extraData.leadType` etc. — ver
  data-model.md) — não o formato do webhook genérico já existente (`POST /webhooks/leads`,
  008-captacao-leads, que usa `X-API-Key` por tenant e um payload próprio).
- AC3: tenant é resolvido cruzando `clientListingId` com `Imovel.uuid` (`system_scope()`, mesmo
  padrão já documentado para "consulta cross-tenant legítima" — igual ao webhook de API key da
  008); lead criado nesse tenant, `corretor_id=None`, `origem=OrigemLead.PORTAL` (o payload real
  nunca diz se é ZAP ou Viva Real especificamente — só "Grupo OLX" — então não dá pra separar em
  `zap`/`vivareal` como o RF006 sugere; ver Fora de escopo).
- AC4: `clientListingId` que não corresponde a nenhum `Imovel` conhecido retorna 200 (não 404) —
  reenviar (retry automático deles) não resolveria um imóvel que não existe mais; só logamos e
  ignoramos, para não entrar num loop de retry inútil.
- AC5: lead criado incrementa `Imovel.contatos` e emite `lead_criado` no canal WS do tenant,
  igual aos outros caminhos de captação automática.

**US3 (P0) — Upload de fotos do imóvel.** Como corretor, quero subir fotos de um imóvel, para
que ele possa entrar no feed de portais (RN2 exige ao menos 1 foto) e ter uma página pública
apresentável.
- AC1: `POST /imoveis/{id}/fotos` (multipart, autenticado) aceita JPEG/PNG/WEBP até 7MB (mesmo
  limite documentado pelo schema VRSync para `Media`); grava em disco (volume Docker, sem
  storage externo — RNF009) e acrescenta a URL à lista `fotos` do imóvel.
- AC2: `DELETE /imoveis/{id}/fotos/{indice}` remove uma foto pelo índice na lista.
- AC3: reaproveita a mesma checagem de visibilidade do resto do módulo (corretor só mexe nos
  próprios imóveis; admin mexe em qualquer um do tenant) — imóvel de outro corretor/tenant
  retorna 404, nunca 403 (mesmo racional de não revelar existência).
- AC4: toda URL de foto retornada pela API (`ImovelOut`, `ImovelPublico`, feed VRSync) é
  absoluta — construída a partir do host da própria requisição, nunca hardcoded, já que corretor
  logado, visitante da página pública e o crawler do Grupo OLX acessam por hosts diferentes.

*Descoberta durante a implementação da US1:* o sistema não tinha (e nunca teve) nenhum
mecanismo de upload de imagem — `ImovelCreate`/`ImovelUpdate` nunca aceitaram um campo de foto,
apesar de `Imovel.fotos` existir no schema desde a v1.0.0. Sem esta US, a exigência de "ao menos
1 foto" do RN2 tornaria o feed permanentemente vazio.

## Fora de escopo

**Leads do tipo MCMV** (simulação de financiamento "Minha Casa Minha Vida") — o payload real
não inclui `originListingId`/`clientListingId` nesse caso, então não há como resolver a qual
tenant o lead pertence; sem uma forma de rotear, esse tipo de lead é descartado (200, sem
processar) até existir um mecanismo de matching diferente. · **Distinguir ZAP de Viva Real na
origem do lead** — o payload real do Grupo OLX não informa o portal de origem especificamente,
só "Grupo OLX" genérico; usar `origem=portal` (já existente no enum) em vez de criar valores
`zap`/`vivareal` que a API não permite preencher com precisão. · **`TransactionType` combinado
("Sale/Rent")** — só suporta venda OU aluguel por imóvel nesta v1 (`Imovel.finalidade` é um
campo único, não uma lista); imóvel que aceita os dois publicará só como venda (ver RN3). ·
**Homologação do software junto ao Grupo OLX** — conseguir a `SECRET_KEY` de verdade é um passo
que só você pode fazer (contato comercial/técnico com o Grupo OLX); esta feature deixa o
adaptador pronto, mas ele fica inerte até a chave real ser configurada (mesmo padrão do
`SUPERADMIN_EMAIL` em 007). · **Validação formal do XML contra o validador oficial** — recomendo
rodar antes de ir para produção; não é algo que eu consiga verificar por aqui.

## Regras de negócio

- **RN1 (Artigo I mantido):** tanto o feed quanto o webhook resolvem o tenant *antes* de
  qualquer leitura/escrita (Host header para o feed, `clientListingId → Imovel.uuid` para o
  webhook) — nunca aceitam um identificador de tenant explícito vindo do chamador.
- **RN2 (feed só de imóveis publicáveis):** só `status=disponivel`, `ativo=True`,
  `finalidade` preenchida **e** ao menos 1 foto cadastrada entram no feed — os quatro critérios,
  não três. A exigência de foto existe porque o schema VRSync exige mínimo 1 imagem por
  `Listing`; publicar um imóvel sem foto resultaria nesse anúncio específico sendo rejeitado do
  lado do Grupo OLX — melhor nunca publicar algo que já sabemos inválido do que descobrir isso
  só no relatório de importação deles.
- **RN3 (uma finalidade por imóvel):** `Imovel.finalidade` é um enum simples (`venda`/`aluguel`),
  não uma lista — decisão consciente de simplicidade sobre o "Sale/Rent" combinado do VRSync.
- **RN4 (SECRET_KEY única, não por tenant):** ao contrário do webhook de API key da
  008-captacao-leads (uma chave por tenant), o webhook de portais usa uma única chave para todo
  o sistema — reflete como o Grupo OLX de fato modela essa integração (por CRM, não por cliente
  final).
- **RN5 (falha de lookup não é erro HTTP):** `clientListingId` desconhecido retorna 200 —
  evita retry automático infinito por algo que reprocessar não resolve.
- **RN6 (fotos armazenadas como caminho relativo):** `Imovel.fotos` guarda caminhos relativos
  (`/uploads/imoveis/...`), nunca URL absoluta — a URL completa é montada em cada leitura, a
  partir do host de quem está pedindo naquele momento (corretor logado, visitante público, feed).
  Gravar a URL absoluta no momento do upload prenderia a foto ao host usado naquela hora
  específica, que pode não ser o mesmo host de quem for visualizar depois.
