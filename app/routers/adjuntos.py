from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Usuario
from app.schemas import AdjuntoOut
from app.services.adjuntos import eliminar_adjunto, file_response, get_owned_adjunto

router = APIRouter(prefix="/api/adjuntos", tags=["adjuntos"])


@router.get("/{adjunto_id}")
def ver_adjunto(
    adjunto_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    row = get_owned_adjunto(db, user, adjunto_id)
    return file_response(row.path, row.nombre, row.mime)


@router.delete("/{adjunto_id}", response_model=AdjuntoOut)
def borrar_adjunto(
    adjunto_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    row = get_owned_adjunto(db, user, adjunto_id)
    out = AdjuntoOut.from_row(row)
    eliminar_adjunto(db, user, adjunto_id)
    return out
