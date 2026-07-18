import asyncio
import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Notificacion, PushSubscription, Usuario
from app.services.email_service import enviar_correo
from app.services.telegram_service import enviar_telegram
from app.services.vapid_keys import ensure_vapid_keys

logger = logging.getLogger(__name__)
settings = get_settings()


def _keys() -> tuple[str, str]:
    return ensure_vapid_keys(settings)


def get_vapid_public_key() -> str:
    _, public = _keys()
    return public or ""


def borrar_suscripciones_usuario(db: Session, usuario_id: int) -> int:
    n = (
        db.query(PushSubscription)
        .filter(PushSubscription.usuario_id == usuario_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return n or 0


def guardar_suscripcion(
    db: Session,
    usuario_id: int,
    endpoint: str,
    p256dh: str,
    auth: str,
    *,
    reemplazar_todas: bool = False,
) -> PushSubscription:
    if reemplazar_todas:
        borrar_suscripciones_usuario(db, usuario_id)

    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).first()
    if existing:
        existing.usuario_id = usuario_id
        existing.p256dh = p256dh
        existing.auth = auth
        db.commit()
        db.refresh(existing)
        return existing

    # Mantener solo las 2 suscripciones más recientes por usuario
    viejas = (
        db.query(PushSubscription)
        .filter(PushSubscription.usuario_id == usuario_id)
        .order_by(PushSubscription.id.desc())
        .offset(1)
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
        },
        ensure_ascii=False,
    )
    claims = {"sub": settings.vapid_claim_email or "mailto:avisos@agenda-facturas.pe"}

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
            logger.info("Push OK usuario=%s endpoint=%s...", usuario_id, sub.endpoint[:48])
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            body = ""
            try:
                body = exc.response.text[:300] if exc.response is not None else ""
            except Exception:  # noqa: BLE001
                body = str(exc)
            logger.warning(
                "Push fallido usuario=%s status=%s body=%s",
                usuario_id,
                status,
                body,
            )
            # 403 = VAPID distinta a la de la suscripción; 404/410 = expirada
            if status in {403, 404, 410}:
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

    usuario = db.get(Usuario, usuario_id)
    if usuario:
        if usuario.telegram_chat_id:
            enviar_telegram(usuario.telegram_chat_id, titulo, mensaje)
        if usuario.notificar_email and usuario.email:
            asyncio.run(enviar_correo(usuario.email, titulo, mensaje))

    return nota
