# Feature 008 — Captação Automática de Leads (Página Pública + Webhook)

**Status:** Em implementação | **Fase do roadmap:** 3 (Fase 3 do documento
`Proptech_Avaliador_Especificacao_v1.2.0.pdf` — "Expansão e Integração com Portais",
reordenada da antiga Fase 6 na v1.2.0) | **Release alvo:** v0.8.0
**Fonte:** `Proptech_Avaliador_Especificacao_v1.2.0.pdf` §10 (Fase 3) + RF006 atualizado |
**Depende de:** 001-fundacao (subdomínio por tenant), 004-leads (pipeline, canal WS)

## Resumo

A Fase 3 do documento lista 6 itens. Esta feature implementa **2 dos 6** — página pública do
imóvel com formulário de interesse, e webhook/API pública para leads de outros canais — que são
exatamente os dois mecanismos de captação automática que **não dependem de acesso oficial aos
portais (ZAP, Viva Real)**. Os demais 4 itens ficam fora de escopo (ver "Fora de escopo").

**Mesma decisão de risco jurídico da 006-dados-mercado:** publicar anúncios automaticamente nos
portais ou importar os contatos recebidos lá dentro exige integração oficial (API paga) ou
scraping — a mesma dependência/risco que já nos fez excluir o scraper de preços em 006. Sem uma
parceria formal com ZAP/Viva Real, essa parte da Fase 3 fica fora até isso mudar.

De quebra, esta feature fecha uma lacuna que já existia desde a especificação original (RF001/
RF006): os contadores `views`/`contatos` são citados na especificação desde a v1.0.0 ("Marketing:
fotos, destaque em portais, contadores de views e contatos") mas **nunca foram implementados no
schema** — não existem como coluna em `imoveis` hoje. Esta feature os adiciona, porque a página
pública e o formulário de interesse são exatamente os eventos que deveriam incrementá-los.

## Histórias de usuário (priorizadas)

**US1 (P0) — Página pública do imóvel com formulário de interesse.** Como corretor, quero um
link público que eu possa compartilhar (WhatsApp, redes sociais, portal) que mostre os dados do
imóvel e permita a um interessado deixar contato, para captar leads sem que ninguém precise
digitar nada manualmente no sistema.
- AC1: `GET /imoveis/publico/{id}` não exige autenticação; resolve o tenant pelo subdomínio
  (Host header, mesmo mecanismo já usado por rotas públicas em 001-fundacao); retorna um
  subconjunto público dos dados (título, descrição, bairro/cidade/estado, tipo, área, quartos,
  banheiros, vagas, valor anunciado, fotos) — nunca campos internos (matrícula, IPTU, valor
  avaliado internamente, valor de mercado).
- AC2: só imóveis com `status=disponivel` e `ativo=True` respondem; imóvel vendido/alugado/
  reservado, inativo, ou de tenant não resolvido pelo Host retornam 404 — nunca revela existência
  cross-tenant.
- AC3: cada carregamento bem-sucedido incrementa `Imovel.views` (RF001/RF006 — lacuna antiga
  fechada).
- AC4: `POST /leads/publico` (mesmo Host/tenant), sem autenticação, cria um `Lead` com
  `origem=site`, vinculado obrigatoriamente ao `imovel_id` da página; exige ao menos telefone OU
  email preenchido (diferente do cadastro manual — aqui não há corretor validando ao vivo).
- AC5: lead criado via AC4 incrementa `Imovel.contatos` e emite `lead_criado` no canal WS do
  tenant, exatamente como o cadastro manual (004-leads) — o corretor recebe o toast em tempo
  real independente de como o lead entrou.

**US2 (P0) — Webhook/API pública para leads de outros canais.** Como admin, quero uma URL e uma
chave de API para conectar landing pages e ferramentas de campanha ao meu funil de leads, sem
precisar de login de usuário.
- AC1: `POST /leads/integracao/api-key` (admin, autenticado) gera uma chave nova; a chave em
  texto plano só aparece nessa resposta — a partir daí só o hash fica salvo. Gerar de novo
  invalida a anterior imediatamente (no máximo uma chave ativa por tenant).
- AC2: `GET /leads/integracao/api-key` (admin, autenticado) informa se existe chave e quando foi
  gerada/usada pela última vez — nunca devolve a chave em si.
- AC3: `POST /webhooks/leads` autentica via header `X-API-Key` (não é JWT/Bearer — é uma
  integração servidor-a-servidor de longa duração, diferente de uma sessão de usuário); chave
  ausente/inválida retorna 401 genérico.
- AC4: payload aceita `nome`, `telefone`/`email` (ao menos um obrigatório), `origem` (opcional,
  um dos valores já existentes — zap, vivareal, site, indicacao, outro — default `outro`) e
  `imovel_id` (opcional); cria `Lead` com `corretor_id=None`, incrementa `Imovel.contatos` se
  `imovel_id` informado, emite `lead_criado` no canal WS do tenant da chave.

## Fora de escopo

**Publicação automática de anúncios nos portais (ZAP, Viva Real)** — exige parceria oficial/API
paga com os portais que não temos hoje; mesma decisão de risco jurídico já registrada em
006-dados-mercado. · **Captação automática de leads DOS portais** (importar contatos recebidos
em anúncios já publicados no ZAP/Viva Real) — mesma dependência de acesso oficial. · **Módulo de
locação** (contratos, boletos) — feature própria e grande, sem relação com o argumento comercial
de leads automáticos que motivou a reordenação desta fase. · **Integração cartorária (SERPRO)**
— depende de acesso pago/governamental, feature própria. · **Suporte a outros países** — i18n,
feature própria. · **Marketplace entre corretores** — conceito de produto diferente
(multi-sided marketplace), feature própria. · **Tela de "assumir/atribuir lead" a um corretor
específico** — um lead sem dono (`corretor_id=None`) fica visível a todos os corretores do
tenant; quem quiser que trabalhe nele primeiro. Atribuição explícita fica para quando isso virar
um problema real de equipe maior. · **Rate limiting / CAPTCHA no formulário público e no
webhook** — mesma lacuna já assumida no `DEPLOY.md`; sem isso, ambos endpoints são um alvo de
spam. Documentado como risco conhecido, não esquecido.

## Regras de negócio

- **RN1 (Artigo I mantido):** tanto a página pública quanto o webhook resolvem o tenant *antes*
  de qualquer leitura/escrita (Host header para a página pública, hash da API key para o
  webhook) e sempre operam dentro de `tenant_scope(tenant_id)` — nunca aceitam um `tenant_id`
  explícito vindo do chamador.
- **RN2 (visibilidade pública):** só `Imovel` com `status=disponivel` e `ativo=True` aparece na
  página pública ou aceita interesse — outro status vira 404, sem distinguir "não existe" de
  "não está mais disponível" (mesma prática de não vazar informação por status de resposta já
  usada em 004-leads/`_garante_visivel`).
- **RN3 (contato mínimo):** `POST /leads/publico` e `POST /webhooks/leads` exigem ao menos
  telefone OU email — diferente do `POST /leads` autenticado (004-leads), que continua sem essa
  exigência (um corretor pode ter motivo para cadastrar um contato incompleto manualmente).
- **RN4 (uma chave por tenant):** gerar uma nova API key substitui a anterior — não há
  acumulação de chaves esquecidas nem lista de chaves ativas.
- **RN5 (chave nunca reexibida):** o texto plano da API key só existe na resposta do momento em
  que foi gerada; o que fica persistido é só o hash — não existe endpoint para recuperar uma
  chave já gerada, só para gerar uma nova.
- **RN6 (contadores):** `Imovel.views` incrementa a cada `GET /imoveis/publico/{id}` bem
  sucedido; `Imovel.contatos` incrementa toda vez que um `Lead` é criado com `imovel_id`
  preenchido — inclusive pelo `POST /leads` manual já existente (004-leads), fechando a lacuna
  original do RF006 (o contador nunca era incrementado em nenhum caminho até esta feature).
- **RN7 (lead sem dono):** `Lead.corretor_id` passa a ser opcional; um `CORRETOR` continua sem
  ver leads de outro corretor específico, mas passa a ver os leads sem dono (`corretor_id=None`)
  do próprio tenant; `ADMIN` sempre viu tudo e continua vendo.
