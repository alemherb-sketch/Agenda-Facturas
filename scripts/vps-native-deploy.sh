#!/usr/bin/env bash
# Despliegue nativo en VPS (mismo patrón que medglobal/erp)
# Puerto app: 8002 | dominio: agenda.erpgestapp.com | path: /srv/agenda-facturas
set -euo pipefail

APP_NAME="agenda-facturas"
APP_USER="agendafact"
APP_DIR="/srv/agenda-facturas"
APP_PORT="8002"
DOMAIN="agenda.erpgestapp.com"
REPO="https://github.com/alemherb-sketch/Agenda-Facturas.git"
DB_NAME="agenda_facturas"
DB_USER="agenda_facturas"

echo "==> [1/8] Usuario del sistema"
if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "/home/$APP_USER" --shell /usr/sbin/nologin "$APP_USER"
  usermod -aG www-data "$APP_USER" || true
fi

echo "==> [2/8] Código en $APP_DIR"
mkdir -p /srv
if [[ -d "$APP_DIR/.git" ]]; then
  cd "$APP_DIR"
  git fetch origin
  git reset --hard origin/master
else
  rm -rf "$APP_DIR"
  git clone "$REPO" "$APP_DIR"
  cd "$APP_DIR"
fi
chown -R "$APP_USER:www-data" "$APP_DIR"

echo "==> [3/8] Postgres: rol y base"
# password aleatorio
DB_PASS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
  echo "    Rol ${DB_USER} ya existe — se regenera password y se actualiza .env"
  sudo -u postgres psql -c "ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASS}';" >/dev/null
else
  sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';" >/dev/null
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" >/dev/null
else
  sudo -u postgres psql -c "ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USER};" >/dev/null || true
fi
sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO ${DB_USER};" >/dev/null || true

echo "==> [4/8] Python venv + deps"
apt-get update -qq
apt-get install -y -qq python3-venv python3-dev libpq-dev build-essential git >/dev/null
cd "$APP_DIR"
if [[ ! -d .venv ]]; then
  sudo -u "$APP_USER" python3 -m venv .venv
fi
sudo -u "$APP_USER" .venv/bin/pip install -U pip wheel -q
sudo -u "$APP_USER" .venv/bin/pip install -r requirements.txt -q

echo "==> [5/8] .env"
SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
CRON_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
ENV_FILE="${APP_DIR}/.env"
if [[ -f "$ENV_FILE" ]] && grep -q "DATABASE_URL=" "$ENV_FILE"; then
  # conservar SECRET_KEY/VAPID/SMTP previos si existen
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  SECRET_KEY="${SECRET_KEY:-$SECRET_KEY}"
  # re-leer sin pisar variables recien generadas mal
fi

# Si ya hay .env, solo actualizar DATABASE_URL; si no, crear completo
if [[ ! -f "$ENV_FILE" ]]; then
  cat > "$ENV_FILE" <<EOF
SECRET_KEY=${SECRET_KEY}
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}
APP_NAME=Agenda Facturas Perú
APP_URL=https://${DOMAIN}
CRON_SECRET=${CRON_SECRET}
VAPID_CLAIM_EMAIL=mailto:avisos@erpgestapp.com
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=Agenda Facturas <avisos@erpgestapp.com>
VAPID_PRIVATE_KEY=
VAPID_PUBLIC_KEY=
EOF
else
  # actualizar password de DB en DATABASE_URL
  python3 - <<PY
from pathlib import Path
p = Path("${ENV_FILE}")
text = p.read_text(encoding="utf-8")
lines = []
found = False
for line in text.splitlines():
    if line.startswith("DATABASE_URL="):
        lines.append("DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}")
        found = True
    elif line.startswith("APP_URL="):
        lines.append("APP_URL=https://${DOMAIN}")
        found = found
    else:
        lines.append(line)
if not found:
    lines.append("DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}")
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
fi
chown "$APP_USER:www-data" "$ENV_FILE"
chmod 640 "$ENV_FILE"
mkdir -p "${APP_DIR}/app/uploads"
chown -R "$APP_USER:www-data" "${APP_DIR}/app/uploads"

echo "==> [6/8] systemd service (puerto ${APP_PORT})"
cat > /etc/systemd/system/agenda-facturas.service <<EOF
[Unit]
Description=Agenda Facturas (FastAPI/uvicorn)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=${APP_USER}
Group=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${APP_PORT} --workers 2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable agenda-facturas.service
systemctl restart agenda-facturas.service
sleep 3
systemctl --no-pager --full status agenda-facturas.service | head -20

echo "==> [7/8] Nginx site ${DOMAIN}"
# bootstrap solo HTTP (certbot luego)
cat > /etc/nginx/sites-available/agenda-facturas <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
        client_max_body_size 25m;
    }
}
EOF

ln -sfn /etc/nginx/sites-available/agenda-facturas /etc/nginx/sites-enabled/agenda-facturas
nginx -t
systemctl reload nginx

echo "==> [8/8] Health local"
curl -fsS "http://127.0.0.1:${APP_PORT}/api/meta" || true
echo
echo "OK deploy base."
echo "SIGUIENTE: apunta DNS A ${DOMAIN} -> $(curl -fsS ifconfig.me 2>/dev/null || hostname -I | awk '{print \$1}')"
echo "Luego: certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos -m admin@erpgestapp.com --redirect"
echo
echo "Migrar Railway (opcional):"
echo "  pg_dump \"\\\$RAILWAY_DATABASE_URL\" --no-owner --no-acl > /tmp/railway.sql"
echo "  sudo -u postgres psql -d ${DB_NAME} < /tmp/railway.sql"
echo "  systemctl restart agenda-facturas"
