from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Notificacion, Usuario
from app.schemas import NotificacionOut, PreferenciasAvisoIn, PreferenciasAvisoOut, PushSubscriptionIn
from app.services.push_service import get_vapid_public_key, guardar_suscripcion
from app.services.reminders import procesar_recordatorios
from app.services.telegram_service import enviar_telegram

router = APIRouter(prefix="/api/notificaciones", tags=["notificaciones"])


@router.get("", response_model=list[NotificacionOut])
def listar(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return (
        db.query(Notificacion)
        .filter(Notificacion.usuario_id == user.id)
        .order_by(Notificacion.creado_en.desc())
        .limit(50)
        .all()
    )


@router.post("/{notificacion_id}/leer")
def marcar_leida(
    notificacion_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    nota = (
        db.query(Notificacion)
        .filter(Notificacion.id == notificacion_id, Notificacion.usuario_id == user.id)
        .first()
    )
    if nota:
        nota.leida = True
        db.commit()
    return {"ok": True}


@router.post("/leer-todas")
def marcar_todas(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    db.query(Notificacion).filter(
        Notificacion.usuario_id == user.id, Notificacion.leida.is_(False)
    ).update({"leida": True})
    db.commit()
    return {"ok": True}


@router.get("/vapid-public-key")
def vapid_key():
    return {"publicKey": get_vapid_public_key()}


@router.post("/push-subscribe")
def push_subscribe(
    payload: PushSubscriptionIn,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    guardar_suscripcion(
        db,
        user.id,
        payload.endpoint,
        payload.keys.get("p256dh", ""),
        payload.keys.get("auth", ""),
        reemplazar_todas=payload.reemplazar_todas,
    )
    return {"ok": True, "mensaje": "Dispositivo registrado para avisos en segundo plano"}


@router.post("/probar-push")
def probar_push(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    from app.models import PushSubscription
    from app.services.push_service import enviar_push, crear_notificacion

    subs = db.query(PushSubscription).filter(PushSubscription.usuario_id == user.id).count()
    if subs == 0:
        return {
            "ok": False,
            "enviados": 0,
            "suscripciones": 0,
            "mensaje": "No hay dispositivo registrado. Pulsa primero «Activar avisos en segundo plano».",
        }

    nota = crear_notificacion(
        db,
        user.id,
        "Prueba de aviso",
        "Si ves esto con la página cerrada, los recordatorios en segundo plano ya funcionan.",
        tipo="prueba",
        enlace="/#/recordatorios",
    )
    enviados = enviar_push(
        db,
        user.id,
        nota.titulo,
        nota.mensaje,
        "/#/recordatorios",
    )
    return {
        "ok": enviados > 0,
        "id": nota.id,
        "enviados": enviados,
        "suscripciones": subs,
        "mensaje": (
            f"Push enviado a {enviados} dispositivo(s). Cierra la pestaña y espera unos segundos."
            if enviados > 0
            else "No se pudo enviar el push. Vuelve a activar los avisos en segundo plano."
        ),
    }


@router.post("/procesar-ahora")
def procesar_ahora(user: Annotated[Usuario, Depends(get_current_user)]):
    _ = user
    procesar_recordatorios()
    return {"ok": True, "mensaje": "Recordatorios revisados"}


@router.get("/preferencias", response_model=PreferenciasAvisoOut)
def obtener_preferencias(user: Annotated[Usuario, Depends(get_current_user)]):
    return user


@router.post("/preferencias", response_model=PreferenciasAvisoOut)
def guardar_preferencias(
    payload: PreferenciasAvisoIn,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    user.telegram_chat_id = (payload.telegram_chat_id or "").strip() or None
    user.notificar_email = payload.notificar_email
    db.commit()
    db.refresh(user)
    return user


@router.post("/telegram-probar")
def telegram_probar(user: Annotated[Usuario, Depends(get_current_user)]):
    if not user.telegram_chat_id:
        return {"ok": False, "mensaje": "Primero guarda tu chat_id de Telegram."}
    enviado = enviar_telegram(
        user.telegram_chat_id,
        "Prueba de aviso",
        "Si ves este mensaje, tus recordatorios llegarán por Telegram con sonido.",
    )
    return {
        "ok": enviado,
        "mensaje": (
            "Mensaje de prueba enviado. Revisa Telegram."
            if enviado
            else "No se pudo enviar. Verifica el chat_id y que TELEGRAM_BOT_TOKEN esté configurado."
        ),
    }
