from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import Base, engine, ensure_schema
from app.routers import agenda, auth_router, clientes, comprobantes, consulta, dashboard, notificaciones, productos
from app.services.reminders import procesar_recordatorios

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

Base.metadata.create_all(bind=engine)
ensure_schema()

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not scheduler.running:
        scheduler.add_job(procesar_recordatorios, "interval", seconds=30, id="recordatorios")
        scheduler.start()
        # Revisa al arrancar por si hay avisos pendientes
        procesar_recordatorios()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.include_router(auth_router.router)
app.include_router(comprobantes.router)
app.include_router(agenda.router)
app.include_router(dashboard.router)
app.include_router(notificaciones.router)
app.include_router(consulta.router)
app.include_router(clientes.router)
app.include_router(productos.router)


@app.get("/api/meta")
def meta():
    return {
        "nombre": settings.app_name,
        "tipos_documento": [
            {"value": "factura", "label": "Factura Electrónica", "serie": "F001"},
            {"value": "boleta", "label": "Boleta de Venta", "serie": "B001"},
            {"value": "nota_venta", "label": "Nota de Venta", "serie": "NV01"},
            {"value": "nota_credito", "label": "Nota de Crédito", "serie": "FC01"},
            {"value": "nota_debito", "label": "Nota de Débito", "serie": "FD01"},
            {"value": "recibo_honorarios", "label": "Recibo por Honorarios", "serie": "E001"},
            {"value": "guia_remision", "label": "Guía de Remisión", "serie": "T001"},
            {"value": "ticket", "label": "Ticket / Comprobante", "serie": "T001"},
        ],
        "estados": [
            {"value": "emitido", "label": "Emitido"},
            {"value": "pagado", "label": "Pagado"},
            {"value": "no_pagado", "label": "No pagado"},
            {"value": "anulado", "label": "Anulado"},
        ],
        "tipos_agenda": [
            {"value": "reunion", "label": "Reunión"},
            {"value": "cita", "label": "Cita"},
            {"value": "nota", "label": "Nota"},
        ],
    }


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Service-Worker-Allowed": "/",
        },
    )
