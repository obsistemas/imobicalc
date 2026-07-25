#!/usr/bin/env bash
# Sobe (ou atualiza) a stack de produção. Roda no servidor, dentro da pasta do projeto
# (ex.: /opt/imobicalc), depois de extrair o zip de deploy.
#
# Existe só para não esquecer o --env-file .env.prod — sem essa flag o Docker Compose
# ignora o .env.prod silenciosamente (ele só lê um arquivo chamado ".env" sozinho) e todas
# as variáveis obrigatórias (POSTGRES_PASSWORD, JWT_SECRET, ENCRYPTION_KEY) ficam faltando.
#
# Uso: ./deploy.sh

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -f .env.prod ]; then
  echo "Erro: .env.prod não encontrado nesta pasta." >&2
  echo "Copie .env.prod.example para .env.prod e preencha os segredos antes de rodar este script." >&2
  exit 1
fi

docker compose -f docker-compose.prod.yml --env-file .env.prod up --build -d

echo
echo "Subiu. Conferindo:"
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
