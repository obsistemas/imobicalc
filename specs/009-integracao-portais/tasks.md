# Tasks — Feature 009: Integração com Portais

Formato: `T8## [P?] [US?] descrição` — [P] = paralelizável. Cada task termina com testes verdes +
commit convencional. Numeração: feature 009 usa T8xx.

## Bloco A — Schema
- T800 Migration + model: `imoveis.finalidade` (`ENUM('venda','aluguel')`, nullable).

## Bloco B — Feed XML VRSync
*Depende do Bloco A.*
- T810 Contrato OpenAPI de `GET /imoveis/publico/feed.xml`.
- T811 `imoveis/service.py`: `gerar_feed_vrsync` (função pura, recebe `list[Imovel]` +
  metadados do tenant, devolve XML string). TDD: XML bem formado, namespace correto; mapeamento
  `ImovelTipo`→`UsageType`/`PropertyType` conforme tabela; `finalidade`→`TransactionType`;
  `ListingID`=`Imovel.uuid`.
- T812 `imoveis/service.py`: `listar_imoveis_para_feed` (tenant-scoped, filtra
  `status=disponivel`+`ativo=True`+`finalidade IS NOT NULL`). TDD: imóvel vendido/sem finalidade
  não entra.
- T813 Endpoint `GET /imoveis/publico/feed.xml` (Host-resolved, sem auth,
  `Content-Type: application/xml`). TDD: tenant não resolvido = feed vazio válido (não 404 —
  um feed é sempre um XML válido, mesmo sem listings); imóvel de outro tenant nunca aparece.

## Bloco C — Webhook de leads dos portais
*Independente do Bloco B, mas precisa de um `Imovel` com `uuid` conhecido para os testes.*
- T820 Setting `canal_pro_webhook_secret` (padrão vazio) em `app/config.py`.
- T821 Contrato OpenAPI de `POST /webhooks/leads/portais`.
- T822 `leads/service.py`: `criar_lead_portal` — resolve tenant via `clientListingId` →
  `Imovel.uuid` (`system_scope()`); cria Lead (`corretor_id=None`, `origem=PORTAL`); incrementa
  `Imovel.contatos`; emite `lead_criado`. TDD: `clientListingId` válido cria no tenant certo;
  desconhecido não cria lead nem levanta erro (retorna sinalização de "ignorado", não exceção).
- T823 Endpoint `POST /webhooks/leads/portais` (Basic Auth contra
  `settings.canal_pro_webhook_secret`). TDD: secret correta + payload válido = 200/201; secret
  ausente/errada = 401; `clientListingId` desconhecido = 200 (não 404); campo desconhecido no
  payload não quebra o parsing.

## Bloco D — UI
- T830 [P] `IntegracaoApiKeyView.vue`: seção nova mostrando a URL do feed do tenant
  (`/imoveis/publico/feed.xml` resolvida com o domínio configurado) + nota sobre validar no
  Validador XML oficial antes de cadastrar no Canal Pro.

## Bloco E — Upload de fotos (US3, descoberto durante o Bloco B)
*Sem essa capacidade, a exigência de foto do RN2 deixaria o feed sempre vazio.*
- T850 `settings.uploads_dir` + mount de `StaticFiles` em `/uploads` (fora do `/api/v1`) +
  `mkdir` no Dockerfile antes do `chown` (volume herda permissão na primeira criação) + volume
  `uploads_data` no `docker-compose.prod.yml` + `location /uploads/` no nginx + proxy no
  `vite.config.js` (dev).
- T851 `imoveis/service.py`: `adicionar_foto`/`remover_foto` — valida tipo (JPEG/PNG/WEBP) e
  tamanho (7MB, mesmo limite do VRSync `Media`), grava em disco, atualiza `Imovel.fotos` (RN6:
  caminho relativo). TDD: tipo inválido, arquivo grande demais, imóvel de outro
  corretor/tenant, remoção por índice inválido.
- T852 `ImovelOut`/`ImovelPublico.from_imovel` ganham `base_url` — todo endpoint que devolve
  `fotos` prefixa com o host da própria requisição (RN6). `gerar_feed_vrsync` idem.
- T853 Endpoints `POST`/`DELETE /imoveis/{id}/fotos[/{indice}]`.
- T854 [P] `ImovelFormView.vue`: campo de finalidade + seção de upload/remoção de fotos
  (visível só ao editar, já que precisa do id do imóvel). `PublicoImovelView.vue`: galeria de
  fotos na página pública.

## Fechamento
- T840 Rodar suíte completa dos módulos 001-008 para confirmar que `finalidade` nullable não
  quebra nenhum teste existente.
- T841 Cobertura ≥80% no que foi adicionado.
- T842 Fluxo manual completo (ver "Critério de conclusão" do plan.md) → tag **v0.9.0**.

**Dependências entre blocos:** A é pré-requisito de B. C é independente de B (não depende do
feed em si, só de um `Imovel` existir). D depende de B e E. E é pré-requisito de facto do RN2 do
Bloco B (sem ele o feed nunca teria conteúdo). Fechamento depende de todos.
