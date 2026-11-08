"""Conector de ERPGEST para los sistemas en subdominios: comprobación de las órdenes del panel (protocolo v1).

Este archivo se copia tal cual en cada sistema (MET SALUD, MEDGLOBAL, Agenda, PORKYS SELECT…). El panel de ERPGEST
lo usa también, para firmar con el mismo mensaje que el sistema comprueba. Solo necesita la biblioteca estándar y
``cryptography``. El protocolo completo está en ``PROTOCOLO.md``, junto a este archivo.

El sistema se configura con dos variables de entorno, que muestra el panel en la pestaña «Conector»:

    ERPGEST_CONECTOR_SISTEMA   código del sistema en el panel, p. ej. ``metsalud``
    ERPGEST_CONECTOR_LLAVE     llave pública Ed25519 en base64 (no es secreta)

Sin las dos, el conector no existe y sus rutas responden 404. Cada orden del panel trae dos cabeceras:

    X-Erpgest-Fecha   segundos desde 1970 (UTC) en que se firmó
    X-Erpgest-Firma   firma Ed25519, en base64, de ``mensaje(fecha, método, sistema, operación, cuerpo)``

La firma cubre el método, el sistema, la operación y el cuerpo exacto: no sirve para otra orden ni para otro sistema,
y caduca a los cinco minutos. En el servidor del sistema no se guarda nada que permita hacerse pasar por el panel.
"""
import base64
import binascii
import hashlib
import os
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PROTOCOLO = "ERPGEST-CONECTOR-V1"
PREFIJO = "/erpgest-conector/v1/"
VENTANA_SEGUNDOS = 300
CABECERA_FECHA = "X-Erpgest-Fecha"
CABECERA_FIRMA = "X-Erpgest-Firma"
OPERACIONES = {
    "estado": "GET",
    "usuarios": "GET",
    "suspension": "POST",
    "limite-usuarios": "POST",
    "restablecer-acceso": "POST",
    "usuario-activo": "POST",
}


class FirmaInvalida(Exception):
    """La orden no viene del panel, es para otro sistema u otra operación, o ya caducó."""


def mensaje(fecha, metodo, sistema, operacion, cuerpo):
    """Lo que firma el panel: seis líneas con el protocolo, la fecha, el método, el sistema, la operación y el
    SHA-256 del cuerpo tal como viaja (vacío en las consultas GET)."""
    return "\n".join([PROTOCOLO, str(int(fecha)), metodo.upper(), sistema, operacion,
                      hashlib.sha256(cuerpo or b"").hexdigest()]).encode("utf-8")


def configuracion():
    """``(sistema, llave pública)`` según el entorno, o ``None`` si el conector no está configurado."""
    sistema = os.environ.get("ERPGEST_CONECTOR_SISTEMA", "").strip()
    llave = os.environ.get("ERPGEST_CONECTOR_LLAVE", "").strip()
    return (sistema, llave) if sistema and llave else None


def verificar(metodo, operacion, cuerpo, fecha, firma, sistema, llave, ahora=None):
    """Comprueba una orden recibida; si no es válida lanza ``FirmaInvalida``.

    ``cuerpo`` son los bytes recibidos sin tocar; ``fecha`` y ``firma``, el texto de las dos cabeceras."""
    try:
        fecha = int(str(fecha).strip())
    except (TypeError, ValueError):
        raise FirmaInvalida("sin fecha") from None
    if abs((time.time() if ahora is None else ahora) - fecha) > VENTANA_SEGUNDOS:
        raise FirmaInvalida("caducada")
    try:
        publica = Ed25519PublicKey.from_public_bytes(base64.b64decode(llave, validate=True))
        publica.verify(base64.b64decode(firma or "", validate=True),
                       mensaje(fecha, metodo, sistema, operacion, cuerpo))
    except (InvalidSignature, ValueError, binascii.Error):
        raise FirmaInvalida("firma") from None
