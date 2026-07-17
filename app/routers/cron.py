"""Endpoint para despertar el servicio y procesar recordatorios (cron externo)."""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from app.config import get_settings
from app.services.reminders import procesar_recordatorios

router = APIRouter(prefix="/api/cron", tags=["cron"])
settings = get_settings()


@router.post("/recordatorios")
@router.get("/recordatorios")
def tick_recordatorios(
    x_cron_secret: Annotated[str | None, Header()] = None,
    secret: str | None = None,
):
    """
    Llamar cada minuto desde un cron externo (p. ej. cron-job.org) para:
    - despertar Railway si estaba dormido
    - disparar recordatorios y push aunque nadie tenga la app abierta
    """
    expected = (settings.cron_secret or "").strip()
    provided = (x_cron_secret or secret or "").strip()
    if expected and provided != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cron no autorizado")

    procesar_recordatorios()
    return {"ok": True, "mensaje": "Recordatorios procesados"}
