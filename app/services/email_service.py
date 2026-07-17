import logging
from email.message import EmailMessage

import aiosmtplib

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def enviar_correo(
    destinatario: str,
    asunto: str,
    cuerpo_texto: str,
    adjunto_nombre: str | None = None,
    adjunto_bytes: bytes | None = None,
    adjunto_tipo: str = "application/pdf",
) -> tuple[bool, str]:
    if not settings.smtp_host or not settings.smtp_user:
        return False, (
            "SMTP no configurado. Configure SMTP_HOST, SMTP_USER y SMTP_PASSWORD en el archivo .env"
        )

    message = EmailMessage()
    message["From"] = settings.smtp_from or settings.smtp_user
    message["To"] = destinatario
    message["Subject"] = asunto
    message.set_content(cuerpo_texto)

    if adjunto_bytes and adjunto_nombre:
        message.add_attachment(
            adjunto_bytes,
            maintype=adjunto_tipo.split("/")[0],
            subtype=adjunto_tipo.split("/")[1],
            filename=adjunto_nombre,
        )

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
        )
        return True, "Correo enviado correctamente"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error enviando correo")
        return False, f"No se pudo enviar el correo: {exc}"
