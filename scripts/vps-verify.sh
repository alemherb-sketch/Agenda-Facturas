#!/usr/bin/env bash
set -euo pipefail
systemctl restart agenda-facturas
sleep 5
systemctl is-active agenda-facturas
journalctl -u agenda-facturas -n 20 --no-pager
curl -fsS http://127.0.0.1:8002/api/meta
echo
sudo -u postgres psql -d agenda_facturas -c "SELECT count(*) AS usuarios FROM usuarios;"
sudo -u postgres psql -d agenda_facturas -c "SELECT count(*) AS comprobantes FROM comprobantes;"
sudo -u postgres psql -d agenda_facturas -c "SELECT count(*) AS notificaciones FROM notificaciones;"
