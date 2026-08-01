# Deploy — VPS + Docker Compose

Segue a decisão de arquitetura já registrada em `ARQUITETURA-REFERENCIA.md` (VPS + Docker
Compose: nginx, backend, postgres, redis). Este guia é para deploy manual num servidor
compartilhado com outro sistema — por isso Postgres/Redis **nunca** expõem porta ao host (só
rede interna do compose) e as portas de backend/frontend são configuráveis.

## 1. Pré-requisitos no servidor

- Docker + Docker Compose v2 instalados (`docker compose version`).
- Confira portas já em uso antes de definir `BACKEND_PORT`/`FRONTEND_PORT`:
  ```bash
  ss -tlnp
  ```
  Os padrões sugeridos (8001 e 8090) evitam os mais comuns (80, 443, 8000, 8080, 5432, 6379,
  3000), mas confirme contra o que já está rodando no servidor antes de seguir.

## 2. Levar o código para o servidor

Opção simples (clone direto no servidor, sem precisar copiar arquivo por arquivo):

```bash
ssh root@SEU_IP
mkdir -p /opt/imobicalc
cd /opt/imobicalc
git clone https://github.com/obsistemas/imobicalc.git .
# em atualizações futuras: git pull
```

## 3. Configurar segredos

```bash
cd /opt/imobicalc
cp .env.prod.example .env.prod
```

Edite `.env.prod` e preencha (nunca reutilize os valores de exemplo):

- `POSTGRES_PASSWORD` — senha forte qualquer.
- `JWT_SECRET` — gerar com `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `ENCRYPTION_KEY` — gerar com `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` (precisa ter `cryptography` instalado; se não tiver Python à mão localmente, rode dentro do container depois do primeiro build: `docker compose -f docker-compose.prod.yml run --rm backend python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
- `BACKEND_PORT`/`FRONTEND_PORT` — ajuste se colidir com o que já roda no servidor (passo 1).
- `POSTGRES_INTERNAL_PORT` (padrão `55432`) — porta do Postgres. O backend usa pela rede interna
  do compose; também fica publicada em `127.0.0.1:<esta porta>` no próprio servidor (só
  loopback, nunca acessível de fora) — útil para conectar com `psql`/DBeaver via túnel SSH. Para
  conferir de fora do container que está respondendo:
  ```bash
  docker exec imobicalc-postgres-1 pg_isready -p 55432
  ```
  Se já tiver um deploy rodando e mudar este valor, o container do Postgres reinicia com a nova
  porta (dado no volume não é afetado) e o backend reconecta automaticamente no próximo restart.
- `SUPERADMIN_EMAIL`/`SUPERADMIN_PASSWORD` — credenciais do painel da plataforma
  (`/admin/login`, 007-superadmin), fora do modelo de tenant. Provisionado automaticamente no
  primeiro start (idempotente — reiniciar depois não reseta a senha). Deixe em branco para não
  criar a conta (painel fica inacessível até preencher e reiniciar).
- `CANAL_PRO_FEED_EMAIL`/`CANAL_PRO_WEBHOOK_SECRET` (009-integracao-portais) — integração com
  ZAP/Viva Real via Canal Pro (Grupo OLX). O feed de anúncios (`/imoveis/publico/feed.xml`)
  funciona mesmo com `CANAL_PRO_FEED_EMAIL` em branco (só fica sem e-mail de contato no XML).
  `CANAL_PRO_WEBHOOK_SECRET` é a chave única do sistema (não por tenant) obtida no processo de
  homologação do CRM junto ao Grupo OLX — sem ela, `POST /webhooks/leads/portais` rejeita tudo
  com 401. Antes de cadastrar a URL do feed de verdade no Canal Pro, valide o XML no
  [Validador oficial do Grupo OLX](https://developers.grupozap.com/feeds/xml_validator/).
- Mercado Pago/Sentry — opcional, deixe em branco se ainda não for usar.

## 4. Subir

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

**Sempre com `-f docker-compose.prod.yml` explícito.** O repositório também tem um
`docker-compose.yml` (sem sufixo) que é só para desenvolvimento local — sobe Postgres/Redis com
porta exposta direto no host (5432/6379) para rodar a suíte de testes numa máquina de
desenvolvedor. Se você clonar o repo direto no servidor (passo 2, opção alternativa) e rodar
`docker compose up` **sem** o `-f`, o Compose lê esse arquivo por padrão e expõe 5432/6379 no
host — é exatamente esse tipo de colisão de porta com outro sistema já rodando no VPS que este
guia existe para evitar. O zip de deploy (`gerar-deploy-zip.sh`) já exclui esse arquivo por
segurança (`.gitattributes`), mas um clone direto do repositório não.

O backend roda `alembic upgrade head` automaticamente antes de subir a cada start (idempotente —
seguro rodar de novo em toda atualização).

## 5. Verificar

```bash
curl -s http://localhost:${BACKEND_PORT:-8001}/health
# {"status":"ok","database":true,"redis":true}

curl -s -o /dev/null -w "%{http_code}\n" http://localhost:${FRONTEND_PORT:-8090}/
# 200
```

Acesse `http://SEU_IP:8090` (ou a porta que você configurou) no navegador.

## 6. Atualizar uma versão nova

```bash
cd /opt/imobicalc
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

## Limitações desta primeira versão do deploy

- **Sem domínio/TLS ainda** — acesso é por IP:porta puro. Quando houver domínio, trocar o
  serviço `frontend` por Caddy (reserva já feita em `ARQUITETURA-REFERENCIA.md`) para TLS
  automático, ou colocar um reverse proxy na frente com certificado.
- **Sem worker/scheduler** — a régua de dunning (`app/modules/licenciamento/dunning.py`) e o RQ
  ainda não têm um entrypoint de worker/cron configurado; hoje só a API roda. Ficará como
  próximo passo quando esse job for de fato agendado.
- **Backup** — `postgres_data` é um volume Docker nomeado; configurar `pg_dump` diário
  (RNF008) fica para uma iteração seguinte deste guia, ainda não automatizado aqui.
- **CI/CD automático** — este guia é deploy manual via SSH; o pipeline de build+deploy
  automático por tag SemVer (mencionado em `ARQUITETURA-REFERENCIA.md`) ainda não foi montado.
