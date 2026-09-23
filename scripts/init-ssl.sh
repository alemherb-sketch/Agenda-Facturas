#!/usr/bin/env bash
# Emite el certificado Let's Encrypt para agenda.erpgestapp.com
# Uso (en el VPS, dentro del directorio del proyecto):
#   bash scripts/init-ssl.sh tu-email@dominio.com
set -euo pipefail

EMAIL="${1:-}"
DOMAIN="agenda.erpgestapp.com"
COMPOSE="docker compose"

if [[ -z "$EMAIL" ]]; then
  echo "Uso: bash scripts/init-ssl.sh tu-email@dominio.com"
  exit 1
fi

cd "$(dirname "$0")/.."

echo "==> Arranque HTTP bootstrap (sin HTTPS)..."
cp deploy/nginx/bootstrap.conf deploy/nginx/default.conf
$COMPOSE up -d db web nginx

echo "==> Esperando health de web..."
for i in $(seq 1 30); do
  if $COMPOSE exec -T web python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/meta')" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "==> Solicitando certificado para ${DOMAIN}..."
$COMPOSE --profile tools run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$DOMAIN" \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  --non-interactive

echo "==> Activando config HTTPS..."
git checkout -- deploy/nginx/default.conf 2>/dev/null || true
# Restaurar default HTTPS si no hay git en el servidor
if [[ ! -f deploy/nginx/default.conf ]] || ! grep -q "listen 443" deploy/nginx/default.conf; then
  cat > deploy/nginx/default.conf <<'NGINX'
# HTTP: ACME challenge + redirect a HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name agenda.erpgestapp.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name agenda.erpgestapp.com;

    ssl_certificate     /etc/letsencrypt/live/agenda.erpgestapp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/agenda.erpgestapp.com/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

    client_max_body_size 25m;

    location = /static/sw.js {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        add_header Cache-Control "no-cache";
    }

    location / {
        proxy_pass http://web:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
    }
}
NGINX
fi

# Reponer archivo HTTPS versionado
cat > deploy/nginx/default.conf <<'NGINX'
# HTTP: ACME challenge + redirect a HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name agenda.erpgestapp.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name agenda.erpgestapp.com;

    ssl_certificate     /etc/letsencrypt/live/agenda.erpgestapp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/agenda.erpgestapp.com/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

    client_max_body_size 25m;

    location = /static/sw.js {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        add_header Cache-Control "no-cache";
    }

    location / {
        proxy_pass http://web:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
    }
}
NGINX

$COMPOSE exec nginx nginx -s reload || $COMPOSE up -d nginx
echo "==> SSL listo: https://${DOMAIN}"
