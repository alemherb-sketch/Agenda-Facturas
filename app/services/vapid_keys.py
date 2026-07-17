"""Genera y carga claves VAPID para notificaciones push.

En Railway el disco es efímero: las claves se persisten en Postgres
para que las suscripciones del celular sigan válidas tras cada deploy.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
VAPID_FILE = DATA_DIR / "vapid.json"
VAPID_PRIVATE_PEM = DATA_DIR / "vapid_private.pem"

KEY_PRIVATE = "vapid_private_pem"
KEY_PUBLIC = "vapid_public_key"


def _public_key_to_urlsafe(public_key) -> str:
    """Convierte EC public key a formato applicationServerKey (base64url)."""
    numbers = public_key.public_numbers()
    x = numbers.x.to_bytes(32, "big")
    y = numbers.y.to_bytes(32, "big")
    raw = b"\x04" + x + y
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _materialize_pem(private_pem: str) -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VAPID_PRIVATE_PEM.write_text(private_pem, encoding="utf-8")
    return str(VAPID_PRIVATE_PEM)


def _db_get(clave: str) -> str | None:
    try:
        from app.database import SessionLocal
        from app.models import SistemaConfig

        db = SessionLocal()
        try:
            row = db.query(SistemaConfig).filter(SistemaConfig.clave == clave).first()
            return row.valor if row else None
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo leer %s desde DB", clave)
        return None


def _db_set(clave: str, valor: str) -> None:
    try:
        from app.database import SessionLocal
        from app.models import SistemaConfig

        db = SessionLocal()
        try:
            row = db.query(SistemaConfig).filter(SistemaConfig.clave == clave).first()
            if row:
                row.valor = valor
            else:
                db.add(SistemaConfig(clave=clave, valor=valor))
            db.commit()
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo guardar %s en DB", clave)


def _generate_pair() -> tuple[str, str]:
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
    return private_pem, public_key


def _load_or_create_keys(settings) -> tuple[str, str]:
    """Devuelve (ruta_pem_privada, public_urlsafe)."""
    env_private = (settings.vapid_private_key or "").strip()
    env_public = (settings.vapid_public_key or "").strip()
    if env_private and env_public:
        if env_private.startswith("-----BEGIN"):
            return _materialize_pem(env_private), env_public
        return env_private, env_public

    db_private = _db_get(KEY_PRIVATE)
    db_public = _db_get(KEY_PUBLIC)
    if db_private and db_public and db_private.startswith("-----BEGIN"):
        logger.info("VAPID cargadas desde base de datos")
        return _materialize_pem(db_private), db_public

    if VAPID_PRIVATE_PEM.exists() and VAPID_FILE.exists():
        data = json.loads(VAPID_FILE.read_text(encoding="utf-8"))
        public = data.get("public_key", "")
        private = VAPID_PRIVATE_PEM.read_text(encoding="utf-8")
        if public and private.startswith("-----BEGIN"):
            _db_set(KEY_PRIVATE, private)
            _db_set(KEY_PUBLIC, public)
            return str(VAPID_PRIVATE_PEM), public

    if VAPID_FILE.exists():
        data = json.loads(VAPID_FILE.read_text(encoding="utf-8"))
        private = data.get("private_key", "")
        public = data.get("public_key", "")
        if private.startswith("-----BEGIN") and public:
            path = _materialize_pem(private)
            _db_set(KEY_PRIVATE, private)
            _db_set(KEY_PUBLIC, public)
            return path, public

    private_pem, public_key = _generate_pair()
    path = _materialize_pem(private_pem)
    VAPID_FILE.write_text(json.dumps({"public_key": public_key}, indent=2), encoding="utf-8")
    _db_set(KEY_PRIVATE, private_pem)
    _db_set(KEY_PUBLIC, public_key)
    logger.info("Claves VAPID generadas y persistidas en base de datos")
    return path, public_key


_cached: tuple[str, str] | None = None


def ensure_vapid_keys(settings) -> tuple[str, str]:
    global _cached
    if _cached is None:
        _cached = _load_or_create_keys(settings)
    return _cached


def reset_vapid_cache() -> None:
    global _cached
    _cached = None
