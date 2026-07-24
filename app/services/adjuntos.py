"""Guardado y validación de adjuntos (PDF / imágenes)."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import get_settings

ALLOWED_MIME = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_BYTES = 8 * 1024 * 1024  # 8 MB


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
    # Evitar path traversal
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
