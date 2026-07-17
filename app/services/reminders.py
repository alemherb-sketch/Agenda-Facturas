from datetime import date, datetime, timedelta
import logging
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Agenda, Comprobante, EstadoComprobante, Notificacion
from app.services.push_service import notificar_usuario

logger = logging.getLogger(__name__)
TZ_LIMA = ZoneInfo("America/Lima")


def ahora_lima() -> datetime:
    """Hora actual en Perú (naive), alineada con datetime-local del navegador."""
    return datetime.now(TZ_LIMA).replace(tzinfo=None)


def procesar_recordatorios() -> None:
    db = SessionLocal()
    try:
        _agendas_pendientes(db)
        _documentos_pendientes(db)
    except Exception:  # noqa: BLE001
        logger.exception("Error procesando recordatorios")
    finally:
        db.close()


def _agendas_pendientes(db: Session) -> None:
    ahora = ahora_lima()
    agendas = (
        db.query(Agenda)
        .filter(Agenda.completado.is_(False), Agenda.notificado.is_(False))
        .all()
    )
    for agenda in agendas:
        minutos = agenda.recordatorio_minutos if agenda.recordatorio_minutos is not None else 30
        momento = agenda.fecha_inicio - timedelta(minutes=minutos)
        # Ventana: desde el recordatorio hasta 2 h después del inicio
        fin_ventana = agenda.fecha_inicio + timedelta(hours=2)
        if momento <= ahora <= fin_ventana:
            hora = agenda.fecha_inicio.strftime("%d/%m/%Y %H:%M")
            notificar_usuario(
                db,
                agenda.usuario_id,
                f"Agenda: {agenda.titulo}",
                f"Tienes una {agenda.tipo.value} programada para {hora}.",
                tipo="agenda",
                enlace="/#/agenda",
            )
            agenda.notificado = True
            db.commit()
            logger.info("Recordatorio agenda id=%s enviado", agenda.id)


def _ya_notificado_hoy(db: Session, usuario_id: int, tipo: str) -> bool:
    inicio = datetime.combine(ahora_lima().date(), datetime.min.time())
    existe = (
        db.query(Notificacion)
        .filter(
            Notificacion.usuario_id == usuario_id,
            Notificacion.tipo == tipo,
            Notificacion.creado_en >= inicio,
        )
        .first()
    )
    return existe is not None


def _documentos_pendientes(db: Session) -> None:
    hoy = ahora_lima().date()
    docs = (
        db.query(Comprobante)
        .filter(
            Comprobante.estado == EstadoComprobante.NO_PAGADO,
            Comprobante.fecha_vencimiento.is_not(None),
            Comprobante.fecha_vencimiento <= hoy,
        )
        .all()
    )
    por_usuario: dict[int, list[Comprobante]] = {}
    for doc in docs:
        por_usuario.setdefault(doc.usuario_id, []).append(doc)

    for usuario_id, lista in por_usuario.items():
        if _ya_notificado_hoy(db, usuario_id, "pago"):
            continue
        total = sum(float(d.total) for d in lista)
        notificar_usuario(
            db,
            usuario_id,
            "Documentos pendientes de pago",
            f"Tienes {len(lista)} comprobante(s) no pagados por S/ {total:,.2f}.",
            tipo="pago",
            enlace="/#/comprobantes?estado=no_pagado",
        )
