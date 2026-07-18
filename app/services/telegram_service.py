import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def enviar_telegram(chat_id: str, titulo: str, mensaje: str) -> bool:
    token = settings.telegram_bot_token
    if not token or not chat_id:
        return False

    texto = f"🔔 {titulo}\n{mensaje}"
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": texto, "disable_web_page_preview": True},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("Telegram fallido chat_id=%s status=%s body=%s", chat_id, resp.status_code, resp.text[:300])
            return False
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Error inesperado enviando Telegram a chat_id=%s", chat_id)
        return False
