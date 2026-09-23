#!/usr/bin/env bash
# Importa un dump SQL de Railway hacia el Postgres del VPS (docker compose).
# Uso:
#   1) En tu PC/Railway: pg_dump "$DATABASE_URL" -F c -f railway.dump
#      (o formato plain: pg_dump "$DATABASE_URL" > railway.sql)
#   2) Copia el archivo al VPS, en la raíz del proyecto
#   3) bash scripts/migrate-from-railway.sh railway.dump
set -euo pipefail

DUMP="${1:-railway.dump}"
COMPOSE="docker compose"

cd "$(dirname "$0")/.."

if [[ ! -f "$DUMP" ]]; then
  echo "No existe el archivo: $DUMP"
  echo "Obtén el dump desde Railway:"
  echo "  railway connect Postgres   # o exporta DATABASE_URL"
  echo "  pg_dump \"\$DATABASE_URL\" -F c -f railway.dump"
  exit 1
fi

echo "==> Asegurando stack db arriba..."
$COMPOSE up -d db
for i in $(seq 1 30); do
  if $COMPOSE exec -T db pg_isready -U "${POSTGRES_USER:-agenda}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

DB_USER="${POSTGRES_USER:-agenda}"
DB_NAME="${POSTGRES_DB:-agenda_facturas}"

# Detectar formato: custom (.dump /.backup) vs SQL
if file "$DUMP" | grep -qi "PostgreSQL custom\|PostgreSQL database dump" 2>/dev/null \
   || [[ "$DUMP" == *.dump || "$DUMP" == *.backup ]]; then
  echo "==> Restaurando dump custom con pg_restore..."
  $COMPOSE exec -T db dropdb -U "$DB_USER" --if-exists "$DB_NAME" || true
  $COMPOSE exec -T db createdb -U "$DB_USER" "$DB_NAME"
  cat "$DUMP" | $COMPOSE exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl --clean --if-exists || true
else
  echo "==> Restaurando SQL plano..."
  $COMPOSE exec -T db dropdb -U "$DB_USER" --if-exists "$DB_NAME" || true
  $COMPOSE exec -T db createdb -U "$DB_USER" "$DB_NAME"
  cat "$DUMP" | $COMPOSE exec -T db psql -U "$DB_USER" -d "$DB_NAME"
fi

echo "==> Reiniciando app web para aplicar schema / seed seguro..."
$COMPOSE up -d web
echo "==> Migración completada."
