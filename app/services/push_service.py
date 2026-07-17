import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Notificacion, PushSubscription
from app.services.vapid_keys import ensure_vapid_keys

logger = logging.getLogger(__name__)
settings = get_settings()


def _keys() -> tuple[str, str]:
    return ensure_vapid_keys(settings)


def get_vapid_public_key() -> str:
    _, public = _keys()
    return public or ""


def guardar_suscripcion(db: Session, usuario_id: int, endpoint: str, p256dh: str, auth: str) -> PushSubscription:
    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).first()
    if existing:
        existing.usuario_id = usuario_id
        existing.p256dh = p256dh
        existing.auth = auth
        db.commit()
        db.refresh(existing)
        return existing

    # Mantener solo las 3 suscripciones más recientes por usuario
    viejas = (
        db.query(PushSubscription)
        .filter(PushSubscription.usuario_id == usuario_id)
        .order_by(PushSubscription.id.desc())
        .offset(2)
        .all()
    )
    for antigua in viejas:
        db.delete(antigua)

    sub = PushSubscription(usuario_id=usuario_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def crear_notificacion(
    db: Session,
    usuario_id: int,
    titulo: str,
    mensaje: str,
    tipo: str = "info",
    enlace: str | None = None,
) -> Notificacion:
    nota = Notificacion(
        usuario_id=usuario_id,
        titulo=titulo,
        mensaje=mensaje,
        tipo=tipo,
        enlace=enlace,
    )
    db.add(nota)
    db.commit()
    db.refresh(nota)
    return nota


def enviar_push(db: Session, usuario_id: int, titulo: str, mensaje: str, url: str = "/") -> int:
    private_key, public_key = _keys()
    if not private_key or not public_key:
        logger.warning("VAPID no disponible; no se puede enviar push en segundo plano")
        return 0

    subs = db.query(PushSubscription).filter(PushSubscription.usuario_id == usuario_id).all()
    if not subs:
        logger.warning("Usuario %s sin suscripción push; active avisos en el navegador", usuario_id)
        return 0

    enviados = 0
    payload = json.dumps(
        {
            "title": titulo,
            "body": mensaje,
            "url": url or "/#/recordatorios",
            "tag": f"af-{usuario_id}-{titulo[:20]}",
        }
    )
    claims = {"sub": settings.vapid_claim_email or "mailto:admin@agenda-facturas.local"}

    for sub in list(subs):
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims=claims,
                ttl=86400,
                timeout=15,
            )
            enviados += 1
            logger.info("Push OK usuario=%s", usuario_id)
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            logger.warning("Push fallido usuario=%s status=%s err=%s", usuario_id, status, exc)
            if status in {404, 410}:
                db.delete(sub)
                db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error inesperado enviando push: %s", exc)

    return enviados


def notificar_usuario(
    db: Session,
    usuario_id: int,
    titulo: str,
    mensaje: str,
    tipo: str = "recordatorio",
    enlace: str | None = "/",
) -> Notificacion:
    nota = crear_notificacion(db, usuario_id, titulo, mensaje, tipo, enlace)
    enviados = enviar_push(db, usuario_id, titulo, mensaje, enlace or "/")
    logger.info("Notificación id=%s push_enviados=%s", nota.id, enviados)
    return nota
