"""Genera y carga claves VAPID para notificaciones push."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
VAPID_FILE = DATA_DIR / "vapid.json"
VAPID_PRIVATE_PEM = DATA_DIR / "vapid_private.pem"


def _public_key_to_urlsafe(public_key) -> str:
    """Convierte EC public key a formato applicationServerKey (base64url)."""
    numbers = public_key.public_numbers()
    x = numbers.x.to_bytes(32, "big")
    y = numbers.y.to_bytes(32, "big")
    raw = b"\x04" + x + y
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _load_or_create_keys(settings) -> tuple[str, str]:
    """Devuelve (ruta_pem_privada, public_urlsafe)."""
    env_private = (settings.vapid_private_key or "").strip()
    env_public = (settings.vapid_public_key or "").strip()
    if env_private and env_public:
        # Si viene PEM en env, materializar a archivo (pywebpush prefiere path)
        if env_private.startswith("-----BEGIN"):
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            VAPID_PRIVATE_PEM.write_text(env_private, encoding="utf-8")
            return str(VAPID_PRIVATE_PEM), env_public
        # Path o DER en string
        return env_private, env_public

    if VAPID_PRIVATE_PEM.exists() and VAPID_FILE.exists():
        data = json.loads(VAPID_FILE.read_text(encoding="utf-8"))
        return str(VAPID_PRIVATE_PEM), data["public_key"]

    if VAPID_FILE.exists():
        data = json.loads(VAPID_FILE.read_text(encoding="utf-8"))
        private = data.get("private_key", "")
        public = data.get("public_key", "")
        if private.startswith("-----BEGIN") and public:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            VAPID_PRIVATE_PEM.write_text(private, encoding="utf-8")
            return str(VAPID_PRIVATE_PEM), public

    try:
        from py_vapid import Vapid
    except ImportError:
        from py_vapid import Vapid01 as Vapid

    vapid = Vapid()
    vapid.generate_keys()
    private_pem = vapid.private_pem()
    if isinstance(private_pem, bytes):
        private_pem = private_pem.decode("utf-8")
    public_key = _public_key_to_urlsafe(vapid.public_key)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VAPID_PRIVATE_PEM.write_text(private_pem, encoding="utf-8")
    VAPID_FILE.write_text(
        json.dumps({"public_key": public_key}, indent=2),
        encoding="utf-8",
    )
    logger.info("Claves VAPID generadas")
    return str(VAPID_PRIVATE_PEM), public_key


def ensure_vapid_keys(settings) -> tuple[str, str]:
    return _load_or_create_keys(settings)
