from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Cliente, Usuario
from app.schemas import ClienteCreate, ClienteOut, ClienteUpdate
from app.services.catalogo import upsert_cliente

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


def _get_owned(db: Session, user: Usuario, cliente_id: int) -> Cliente:
    item = db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.usuario_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return item


@router.get("", response_model=list[ClienteOut])
def listar(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = None,
    limit: int = Query(200, le=500),
):
    query = (
        db.query(Cliente)
        .filter(Cliente.usuario_id == user.id, Cliente.activo.is_not(False))
        .order_by(Cliente.nombre.asc())
    )
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Cliente.nombre.ilike(like))
            | (Cliente.documento.ilike(like))
            | (Cliente.email.ilike(like))
        )
    return query.limit(limit).all()


@router.post("", response_model=ClienteOut, status_code=201)
def crear(
    payload: ClienteCreate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    cliente = upsert_cliente(
        db,
        user.id,
        nombre=payload.nombre,
        documento=payload.documento,
        email=payload.email,
        telefono=payload.telefono,
        direccion=payload.direccion,
    )
    if payload.tipo_documento:
        cliente.tipo_documento = payload.tipo_documento
    db.commit()
    db.refresh(cliente)
    return cliente


@router.put("/{cliente_id}", response_model=ClienteOut)
def actualizar(
    cliente_id: int,
    payload: ClienteUpdate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    cliente = _get_owned(db, user, cliente_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(cliente, key, value)
    db.commit()
    db.refresh(cliente)
    return cliente


@router.delete("/{cliente_id}")
def eliminar(
    cliente_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    cliente = _get_owned(db, user, cliente_id)
    cliente.activo = False
    db.commit()
    return {"ok": True}
