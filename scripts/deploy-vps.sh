#!/usr/bin/env bash
# Despliega o actualiza Agenda-Facturas en el VPS.
# Uso: bash scripts/deploy-vps.sh
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "Falta .env — copia .env.vps.example y rellena secretos."
  exit 1
fi

HAS_CERT=0
if docker compose --profile tools run --rm --entrypoint sh certbot -c \
  'test -f /etc/letsencrypt/live/agenda.erpgestapp.com/fullchain.pem' >/dev/null 2>&1; then
  HAS_CERT=1
fi

if [[ "$HAS_CERT" -eq 0 ]]; then
  echo "==> Sin certificado SSL aún: usando nginx bootstrap (solo HTTP)."
  cp deploy/nginx/bootstrap.conf deploy/nginx/default.conf
else
  echo "==> Certificado SSL detectado: config HTTPS."
  # Asegurar default HTTPS versionado
  if ! grep -q "listen 443" deploy/nginx/default.conf 2>/dev/null; then
    cp deploy/nginx/bootstrap.conf deploy/nginx/default.conf
  fi
fi

echo "==> Build + up..."
docker compose pull || true
docker compose build --pull
docker compose up -d db web nginx

echo "==> Estado:"
docker compose ps
echo ""
echo "Health interno:"
docker compose exec -T web python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/meta').read().decode())" || true
echo ""
if [[ "$HAS_CERT" -eq 0 ]]; then
  echo "Primer despliegue: configura DNS (A agenda → IP VPS) y luego:"
  echo "  bash scripts/init-ssl.sh tu-email@dominio.com"
else
  echo "App: https://agenda.erpgestapp.com"
fi
