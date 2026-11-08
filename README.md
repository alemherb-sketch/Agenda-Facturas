# Agenda Facturas Perú

Aplicación unificada **PWA + Web** para comprobantes peruanos, agenda y recordatorios.

## Stack

- FastAPI + SQLAlchemy (SQLite local / PostgreSQL en Railway)
- Frontend responsive PWA
- Web Push para avisos en segundo plano

## Local

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/generate_icons.py
python run.py
```

Abre http://localhost:8000

## Despliegue en Railway

1. Sube el código a GitHub.
2. En [Railway](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
3. Agrega un plugin **PostgreSQL** al mismo proyecto.
4. Variables de entorno recomendadas:

| Variable | Valor |
|---|---|
| `SECRET_KEY` | cadena larga aleatoria |
| `DATABASE_URL` | (se enlaza sola desde Postgres) |
| `APP_URL` | `https://tu-app.up.railway.app` |
| `VAPID_PRIVATE_KEY` | PEM de `app/data/vapid_private.pem` (opcional) |
| `VAPID_PUBLIC_KEY` | clave pública VAPID (opcional) |
| `VAPID_CLAIM_EMAIL` | `mailto:tu@correo.com` |

5. Railway usará el `Procfile` / `railway.toml` con:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Avisos con la app cerrada (Web Push)

1. En el celular abre la URL HTTPS de Railway e **instala la PWA**.
2. Entra a **Más → Avisos** (o el botón de notificaciones) y pulsa **Activar avisos en segundo plano**.
3. Acepta el permiso. Debe llegar una **prueba** aunque cierres la app.
4. Las claves VAPID se guardan en Postgres (no se pierden al redesplegar).

Para que los recordatorios se disparen aunque Railway esté dormido, configura un cron externo cada 1–5 min:

```
GET https://tu-app.up.railway.app/api/cron/recordatorios?secret=TU_CRON_SECRET
```

Variable de entorno opcional: `CRON_SECRET`.

## Conector del panel de ERPGEST (el proveedor)

`app/panel_erpgest.py` recibe en `/erpgest-conector/v1/` las órdenes firmadas (Ed25519) del panel de ERPGEST
(Panel › Subdominios): ver las cuentas y su actividad, suspender el servicio (la página y el API responden 503
con el aviso), fijar cuántas cuentas activas se admiten (el registro público lo respeta) y restablecer el acceso
de una cuenta (contraseña nueva y cierre de todas las sesiones). Se activa con dos variables de entorno, que el
panel muestra en la pestaña *Conector*; la llave es pública, no secreta:

```
ERPGEST_CONECTOR_SISTEMA=agenda
ERPGEST_CONECTOR_LLAVE=<la llave pública que muestra el panel>
```

Sin ellas el conector no existe (404). Pruebas: `python -m pytest tests -q` (base SQLite temporal).

## Despliegue en VPS (Docker)

Producción objetivo: **https://agenda.erpgestapp.com**

Guía completa: [deploy/README-VPS.md](deploy/README-VPS.md)

Resumen:

```bash
# En el VPS
git clone https://github.com/alemherb-sketch/Agenda-Facturas.git
cd Agenda-Facturas
cp .env.vps.example .env   # editar secretos
bash scripts/deploy-vps.sh
bash scripts/init-ssl.sh tu-email@dominio.com
# (opcional) restaurar dump de Railway
bash scripts/migrate-from-railway.sh railway.dump
```
