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

## Cuenta demo local

- Email: `demo@agenda.pe`
- Clave: `demo1234`
