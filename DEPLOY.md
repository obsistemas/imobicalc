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
  Os padrões sugeridos (8001 e 8080) evitam os mais comuns (80, 443, 8000, 5432, 6379, 3000),
  mas confirme contra o que já está rodando no servidor antes de seguir.

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
- Mercado Pago/Sentry — opcional, deixe em branco se ainda não for usar.

## 4. Subir

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

O backend roda `alembic upgrade head` automaticamente antes de subir a cada start (idempotente —
seguro rodar de novo em toda atualização).

## 5. Verificar

```bash
curl -s http://localhost:${BACKEND_PORT:-8001}/health
# {"status":"ok","database":true,"redis":true}

curl -s -o /dev/null -w "%{http_code}\n" http://localhost:${FRONTEND_PORT:-8080}/
# 200
```

Acesse `http://SEU_IP:8080` (ou a porta que você configurou) no navegador.

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
