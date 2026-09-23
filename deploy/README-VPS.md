# Despliegue VPS — agenda.erpgestapp.com

Migración de Railway → VPS con Docker + Postgres + Nginx + Let's Encrypt.

## 1. DNS

En el proveedor de `erpgestapp.com`, crea:

| Tipo | Nombre  | Valor        |
|------|---------|--------------|
| A    | agenda  | **IP del VPS** |

Espera propagación (`dig agenda.erpgestapp.com` o `nslookup`).

## 2. Requisitos en el VPS

- Ubuntu 22.04/24.04 (o similar)
- Docker Engine + Docker Compose plugin
- Puertos **80** y **443** abiertos
- Git

```bash
# Ejemplo rápido Ubuntu
sudo apt update && sudo apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# cierra sesión y vuelve a entrar
```

## 3. Clonar y configurar

```bash
sudo mkdir -p /opt/apps && sudo chown $USER:$USER /opt/apps
cd /opt/apps
git clone https://github.com/alemherb-sketch/Agenda-Facturas.git
cd Agenda-Facturas

cp .env.vps.example .env
nano .env   # SECRET_KEY, POSTGRES_PASSWORD, CRON_SECRET, SMTP, VAPID…
```

Copia desde Railway (si puedes): `SECRET_KEY`, `VAPID_*`, `SMTP_*`, `CRON_SECRET`.

## 4. Subir y arrancar

```bash
bash scripts/deploy-vps.sh
bash scripts/init-ssl.sh tu-email@dominio.com
```

App: **https://agenda.erpgestapp.com**

## 5. Migrar datos desde Railway

### En local o con Railway CLI

```bash
# Opción A: Railway CLI
railway login
railway link   # proyecto Agenda-Facturas
railway variables  # anota DATABASE_URL si sale

# Opción B: copia DATABASE_URL del dashboard Railway (Postgres → Connect)
export RAILWAY_DATABASE_URL='postgresql://...'

pg_dump "$RAILWAY_DATABASE_URL" -F c -f railway.dump
# o:
# pg_dump "$RAILWAY_DATABASE_URL" --no-owner --no-acl > railway.sql
```

### Al VPS

```bash
scp railway.dump user@VPS_IP:/opt/apps/Agenda-Facturas/
ssh user@VPS_IP
cd /opt/apps/Agenda-Facturas
bash scripts/migrate-from-railway.sh railway.dump
```

## 6. Renovación SSL

Cron semanal en el VPS:

```bash
docker compose run --rm --entrypoint certbot certbot renew --webroot -w /var/www/certbot
docker compose exec nginx nginx -s reload
```

## 7. Cron de recordatorios (opcional)

El scheduler APScheduler ya corre dentro del contenedor. Si quieres un ping externo:

```
GET https://agenda.erpgestapp.com/api/cron/recordatorios?secret=TU_CRON_SECRET
```

## 8. Apagar Railway

Cuando valides en el VPS:

1. Comprueba login, datos, PDF, push, adjuntos.
2. Actualiza cualquier URL pública guardada.
3. Elimina o pausa el servicio en Railway.
