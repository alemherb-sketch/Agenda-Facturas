"""Genera y carga claves VAPID para notificaciones push.

Siempre deriva la clave pública desde la privada (PEM) para evitar el 403:
"VAPID credentials do not correspond to the credentials used to create the subscriptions".
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
VAPID_PRIVATE_PEM = DATA_DIR / "vapid_private.pem"

KEY_PRIVATE = "vapid_private_pem"


def _public_key_to_urlsafe(public_key) -> str:
    numbers = public_key.public_numbers()
    x = numbers.x.to_bytes(32, "big")
    y = numbers.y.to_bytes(32, "big")
    raw = b"\x04" + x + y
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _public_from_pem(private_pem: str) -> str:
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    key = load_pem_private_key(private_pem.encode("utf-8"), password=None)
    return _public_key_to_urlsafe(key.public_key())


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


def _db_delete(clave: str) -> None:
    try:
        from app.database import SessionLocal
        from app.models import SistemaConfig

        db = SessionLocal()
        try:
            db.query(SistemaConfig).filter(SistemaConfig.clave == clave).delete()
            db.commit()
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo borrar %s de DB", clave)


def _generate_private_pem() -> str:
    try:
        from py_vapid import Vapid
    except ImportError:
        from py_vapid import Vapid01 as Vapid

    vapid = Vapid()
    vapid.generate_keys()
    private_pem = vapid.private_pem()
    if isinstance(private_pem, bytes):
        private_pem = private_pem.decode("utf-8")
    return private_pem


def _wipe_all_subscriptions() -> int:
    """Tras rotar VAPID, las suscripciones viejas quedan inválidas."""
    try:
        from app.database import SessionLocal
        from app.models import PushSubscription

        db = SessionLocal()
        try:
            n = db.query(PushSubscription).delete()
            db.commit()
            return n or 0
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        logger.exception("No se pudieron limpiar suscripciones push")
        return 0


def _load_or_create_keys(settings) -> tuple[str, str]:
    """Devuelve (ruta_pem_privada, public_urlsafe derivada)."""
    env_private = (settings.vapid_private_key or "").strip()
    if env_private:
        if env_private.startswith("-----BEGIN"):
            path = _materialize_pem(env_private)
            public = _public_from_pem(env_private)
            return path, public
        pem_text = Path(env_private).read_text(encoding="utf-8")
        public = _public_from_pem(pem_text)
        return env_private, public

    db_private = _db_get(KEY_PRIVATE)
    if db_private and db_private.startswith("-----BEGIN"):
        path = _materialize_pem(db_private)
        public = _public_from_pem(db_private)
        # La pública guardada aparte causaba 403; limpiamos suscripciones una vez
        if _db_get("vapid_public_key") is not None or _db_get("vapid_fix_v2") != "1":
            wiped = _wipe_all_subscriptions()
            _db_delete("vapid_public_key")
            _db_set("vapid_fix_v2", "1")
            logger.warning("Suscripciones push limpiadas por corrección VAPID (%s)", wiped)
        logger.info("VAPID cargada desde Postgres (pública derivada del PEM)")
        return path, public

    if VAPID_PRIVATE_PEM.exists():
        private = VAPID_PRIVATE_PEM.read_text(encoding="utf-8")
        if private.startswith("-----BEGIN"):
            _db_set(KEY_PRIVATE, private)
            public = _public_from_pem(private)
            _db_delete("vapid_public_key")
            return str(VAPID_PRIVATE_PEM), public

    private_pem = _generate_private_pem()
    path = _materialize_pem(private_pem)
    _db_set(KEY_PRIVATE, private_pem)
    _db_delete("vapid_public_key")
    wiped = _wipe_all_subscriptions()
    public = _public_from_pem(private_pem)
    logger.info("VAPID nueva generada; suscripciones antiguas borradas=%s", wiped)
    return path, public


_cached: tuple[str, str] | None = None


def ensure_vapid_keys(settings) -> tuple[str, str]:
    global _cached
    if _cached is None:
        _cached = _load_or_create_keys(settings)
    return _cached


def force_rotate_vapid(settings) -> tuple[str, str]:
    """Fuerza nuevas claves y limpia suscripciones (uso administrativo)."""
    global _cached
    private_pem = _generate_private_pem()
    path = _materialize_pem(private_pem)
    _db_set(KEY_PRIVATE, private_pem)
    _db_delete("vapid_public_key")
    wiped = _wipe_all_subscriptions()
    public = _public_from_pem(private_pem)
    _cached = (path, public)
    logger.info("VAPID rotada manualmente; suscripciones borradas=%s", wiped)
    return _cached


def reset_vapid_cache() -> None:
    global _cached
    _cached = None
