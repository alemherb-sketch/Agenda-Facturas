#!/usr/bin/env bash
set -euo pipefail

echo "=== Postgres DBs ==="
sudo -u postgres psql -Atc "SELECT datname FROM pg_database WHERE datistemplate = false;"
echo "=== Hosts ==="
getent hosts erpgestapp.com || true
getent hosts medglobal.erpgestapp.com || true
getent hosts agenda.erpgestapp.com || true
echo "=== certbot ==="
which certbot
certbot certificates 2>/dev/null | head -50 || true
echo "=== ports ==="
ss -tlnp | grep -E ':80|:443|:800'
