from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Cliente, Usuario
from app.schemas import AdjuntoOut, ClienteCreate, ClienteOut, ClienteUpdate
from app.services.adjuntos import (
    ENTIDAD_CLIENTE,
    crear_adjunto,
    listar_adjuntos,
    map_adjuntos_por_entidad,
)
from app.services.catalogo import upsert_cliente

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


def _get_owned(db: Session, user: Usuario, cliente_id: int) -> Cliente:
    item = db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.usuario_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return item


def _cliente_out(item: Cliente, adjuntos_rows=None) -> ClienteOut:
    rows = adjuntos_rows if adjuntos_rows is not None else []
    out = ClienteOut.model_validate(item)
    out.adjuntos = [AdjuntoOut.from_row(r) for r in rows]
    out.tiene_adjunto = bool(out.adjuntos)
    return out


def _cliente_out_db(db: Session, item: Cliente) -> ClienteOut:
    return _cliente_out(item, listar_adjuntos(db, ENTIDAD_CLIENTE, item.id))


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
    items = query.limit(limit).all()
    by_adj = map_adjuntos_por_entidad(db, ENTIDAD_CLIENTE, [i.id for i in items])
    return [_cliente_out(i, by_adj.get(i.id, [])) for i in items]


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
    return _cliente_out_db(db, cliente)


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
    return _cliente_out_db(db, cliente)


@router.post("/{cliente_id}/adjuntos", response_model=ClienteOut)
async def subir_adjuntos(
    cliente_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    archivos: list[UploadFile] = File(...),
):
    cliente = _get_owned(db, user, cliente_id)
    if not archivos:
        raise HTTPException(status_code=400, detail="Seleccione al menos un archivo")
    for archivo in archivos:
        await crear_adjunto(
            db,
            user=user,
            entidad_tipo=ENTIDAD_CLIENTE,
            entidad_id=cliente.id,
            kind="clientes",
            archivo=archivo,
        )
    return _cliente_out_db(db, _get_owned(db, user, cliente.id))


@router.get("/{cliente_id}/adjuntos", response_model=list[AdjuntoOut])
def listar_adjuntos_cliente(
    cliente_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _get_owned(db, user, cliente_id)
    return [AdjuntoOut.from_row(r) for r in listar_adjuntos(db, ENTIDAD_CLIENTE, cliente_id)]


@router.delete("/{cliente_id}")
def eliminar(
    cliente_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    cliente = _get_owned(db, user, cliente_id)
    # Soft-delete: conservamos adjuntos por si se reactiva el registro
    cliente.activo = False
    db.commit()
    return {"ok": True}
