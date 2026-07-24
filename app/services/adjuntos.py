"""Guardado y validación de adjuntos (PDF / imágenes) — uno o varios por entidad."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Adjunto, Comprobante, MovimientoCaja, MovimientoCombustible, Usuario

ALLOWED_MIME = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_BYTES = 8 * 1024 * 1024  # 8 MB
MAX_POR_ENTIDAD = 12

ENTIDAD_COMPROBANTE = "comprobante"
ENTIDAD_CAJA = "caja"
ENTIDAD_COMBUSTIBLE = "combustible"


def uploads_root() -> Path:
    settings = get_settings()
    raw = (getattr(settings, "upload_dir", None) or "").strip()
    root = Path(raw) if raw else Path(__file__).resolve().parent.parent / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_original_name(name: str | None) -> str:
    base = Path(name or "archivo").name
    base = re.sub(r"[^\w.\- ()áéíóúÁÉÍÓÚñÑ]+", "_", base, flags=re.UNICODE).strip("._")
    return (base or "archivo")[:200]


async def save_upload(
    file: UploadFile,
    *,
    user_id: int,
    kind: str,
    entity_id: int,
) -> tuple[str, str, str]:
    """Guarda el archivo y devuelve (path relativo, nombre original, mime)."""
    mime = (file.content_type or "").lower().split(";")[0].strip()
    if mime not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail="Solo se permiten PDF o imágenes (JPG, PNG, WEBP, GIF)",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="El archivo supera el máximo de 8 MB")

    ext = ALLOWED_MIME[mime]
    folder = uploads_root() / str(user_id) / kind
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{entity_id}_{uuid.uuid4().hex}{ext}"
    full = folder / stored
    full.write_bytes(data)

    rel = f"{user_id}/{kind}/{stored}"
    original = _safe_original_name(file.filename)
    if not original.lower().endswith(ext):
        original = f"{original}{ext}"
    return rel, original, mime


def absolute_path(rel: str | None) -> Path | None:
    if not rel:
        return None
    clean = Path(rel.replace("\\", "/"))
    if clean.is_absolute() or ".." in clean.parts:
        return None
    full = (uploads_root() / clean).resolve()
    root = uploads_root().resolve()
    if not str(full).startswith(str(root)):
        return None
    return full if full.is_file() else None


def delete_file(rel: str | None) -> None:
    path = absolute_path(rel)
    if path and path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def file_response(rel: str | None, nombre: str | None, mime: str | None) -> FileResponse:
    path = absolute_path(rel)
    if not path:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")
    filename = nombre or path.name
    media = mime or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media,
        filename=filename,
        content_disposition_type="inline",
    )


def listar_adjuntos(db: Session, entidad_tipo: str, entidad_id: int) -> list[Adjunto]:
    return (
        db.query(Adjunto)
        .filter(Adjunto.entidad_tipo == entidad_tipo, Adjunto.entidad_id == entidad_id)
        .order_by(Adjunto.id.asc())
        .all()
    )


def contar_adjuntos(db: Session, entidad_tipo: str, entidad_id: int) -> int:
    return (
        db.query(Adjunto)
        .filter(Adjunto.entidad_tipo == entidad_tipo, Adjunto.entidad_id == entidad_id)
        .count()
    )


def map_adjuntos_por_entidad(
    db: Session, entidad_tipo: str, entidad_ids: list[int]
) -> dict[int, list[Adjunto]]:
    if not entidad_ids:
        return {}
    rows = (
        db.query(Adjunto)
        .filter(Adjunto.entidad_tipo == entidad_tipo, Adjunto.entidad_id.in_(entidad_ids))
        .order_by(Adjunto.id.asc())
        .all()
    )
    out: dict[int, list[Adjunto]] = {i: [] for i in entidad_ids}
    for row in rows:
        out.setdefault(row.entidad_id, []).append(row)
    return out


async def crear_adjunto(
    db: Session,
    *,
    user: Usuario,
    entidad_tipo: str,
    entidad_id: int,
    kind: str,
    archivo: UploadFile,
) -> Adjunto:
    total = contar_adjuntos(db, entidad_tipo, entidad_id)
    if total >= MAX_POR_ENTIDAD:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {MAX_POR_ENTIDAD} archivos por registro",
        )
    rel, nombre, mime = await save_upload(
        archivo, user_id=user.id, kind=kind, entity_id=entidad_id
    )
    row = Adjunto(
        usuario_id=user.id,
        entidad_tipo=entidad_tipo,
        entidad_id=entidad_id,
        nombre=nombre,
        mime=mime,
        path=rel,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_owned_adjunto(db: Session, user: Usuario, adjunto_id: int) -> Adjunto:
    row = (
        db.query(Adjunto)
        .filter(Adjunto.id == adjunto_id, Adjunto.usuario_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")
    return row


def eliminar_adjunto(db: Session, user: Usuario, adjunto_id: int) -> None:
    row = get_owned_adjunto(db, user, adjunto_id)
    delete_file(row.path)
    db.delete(row)
    db.commit()


def eliminar_adjuntos_entidad(db: Session, entidad_tipo: str, entidad_id: int) -> None:
    rows = listar_adjuntos(db, entidad_tipo, entidad_id)
    for row in rows:
        delete_file(row.path)
        db.delete(row)


def migrar_adjunto_legado(
    db: Session,
    *,
    user_id: int,
    entidad_tipo: str,
    entidad_id: int,
    nombre: str | None,
    mime: str | None,
    path: str | None,
) -> None:
    if not path:
        return
    exists = (
        db.query(Adjunto)
        .filter(
            Adjunto.entidad_tipo == entidad_tipo,
            Adjunto.entidad_id == entidad_id,
            Adjunto.path == path,
        )
        .first()
    )
    if exists:
        return
    db.add(
        Adjunto(
            usuario_id=user_id,
            entidad_tipo=entidad_tipo,
            entidad_id=entidad_id,
            nombre=nombre or Path(path).name,
            mime=mime or "application/octet-stream",
            path=path,
        )
    )


def migrar_adjuntos_legados(db: Session) -> None:
    """Copia adjuntos de columnas antiguas a la tabla adjuntos (una vez)."""
    for doc in db.query(Comprobante).filter(Comprobante.adjunto_path.isnot(None)).all():
        migrar_adjunto_legado(
            db,
            user_id=doc.usuario_id,
            entidad_tipo=ENTIDAD_COMPROBANTE,
            entidad_id=doc.id,
            nombre=doc.adjunto_nombre,
            mime=doc.adjunto_mime,
            path=doc.adjunto_path,
        )
    for mov in db.query(MovimientoCaja).filter(MovimientoCaja.adjunto_path.isnot(None)).all():
        migrar_adjunto_legado(
            db,
            user_id=mov.usuario_id,
            entidad_tipo=ENTIDAD_CAJA,
            entidad_id=mov.id,
            nombre=mov.adjunto_nombre,
            mime=mov.adjunto_mime,
            path=mov.adjunto_path,
        )
    for mov in (
        db.query(MovimientoCombustible).filter(MovimientoCombustible.adjunto_path.isnot(None)).all()
    ):
        migrar_adjunto_legado(
            db,
            user_id=mov.usuario_id,
            entidad_tipo=ENTIDAD_COMBUSTIBLE,
            entidad_id=mov.id,
            nombre=mov.adjunto_nombre,
            mime=mov.adjunto_mime,
            path=mov.adjunto_path,
        )
    db.commit()
