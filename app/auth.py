import time
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import PanelEstado, Usuario

security = HTTPBearer(auto_error=False)
settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    # Cuando se emitio (en milisegundos) permite cerrar de una vez todas las sesiones: ver _sesion_vigente
    return jwt.encode(
        {"sub": subject, "exp": expire, "emitido_ms": int(time.time() * 1000)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def _sesion_vigente(db: Session, payload) -> bool:
    """False si el panel de ERPGEST cerro todas las sesiones (restablecer el acceso) despues de emitirse el token.

    Sin esa marca no cambia nada; con ella, un token sin fecha de emision (de antes de esta version) ya no vale."""
    estado = db.query(PanelEstado).filter(PanelEstado.id == 1).first()
    if estado is None or estado.sesiones_desde is None:
        return True
    emitido = payload.get("emitido_ms")
    if not isinstance(emitido, int) or isinstance(emitido, bool):
        return False
    return datetime.fromtimestamp(emitido / 1000, timezone.utc).replace(tzinfo=None) >= estado.sesiones_desde


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
) -> Usuario:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from exc

    user = db.query(Usuario).filter(Usuario.email == email, Usuario.activo.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    if not _sesion_vigente(db, payload):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión cerrada por el proveedor")
    return user
