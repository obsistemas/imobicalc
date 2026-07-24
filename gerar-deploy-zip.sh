#!/usr/bin/env bash
# Gera o zip de deploy na raiz do projeto: imobicalc-deploy-<data>-<hash-curto>.zip
#
# Contém todos os arquivos versionados no commit atual (via `git archive`) mais o
# `.env.prod` local, se existir (ele é ignorado pelo git de propósito — nunca deve ser
# commitado — mas precisa ir dentro do zip para o servidor não precisar recriá-lo na mão).
#
# Uso: ./gerar-deploy-zip.sh

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

rm -f imobicalc-deploy-*.zip

HASH_CURTO=$(git rev-parse --short HEAD)
DESTINO="imobicalc-deploy-$(date +%F)-${HASH_CURTO}.zip"

git archive --format=zip -o "$DESTINO" HEAD

if [ -f .env.prod ]; then
  zip -j "$DESTINO" .env.prod > /dev/null
  echo "Incluído .env.prod (local, fora do git) no zip."
else
  echo "Aviso: .env.prod não encontrado na raiz do projeto — o zip não terá segredos prontos;" >&2
  echo "será preciso criar .env.prod manualmente no servidor a partir do .env.prod.example." >&2
fi

echo "Gerado: $DESTINO"
