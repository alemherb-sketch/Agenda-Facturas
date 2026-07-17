from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Producto, Usuario
from app.schemas import ProductoCreate, ProductoOut, ProductoUpdate
from app.services.catalogo import upsert_producto

router = APIRouter(prefix="/api/productos", tags=["productos"])


def _get_owned(db: Session, user: Usuario, producto_id: int) -> Producto:
    item = db.query(Producto).filter(Producto.id == producto_id, Producto.usuario_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return item


@router.get("", response_model=list[ProductoOut])
def listar(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = None,
    tipo: str | None = None,
    limit: int = Query(300, le=500),
):
    query = (
        db.query(Producto)
        .filter(Producto.usuario_id == user.id, Producto.activo.is_(True))
        .order_by(Producto.nombre.asc())
    )
    if q:
        like = f"%{q}%"
        query = query.filter((Producto.nombre.ilike(like)) | (Producto.codigo.ilike(like)))
    if tipo:
        query = query.filter(Producto.tipo == tipo)
    return query.limit(limit).all()


@router.post("", response_model=ProductoOut, status_code=201)
def crear(
    payload: ProductoCreate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    producto = upsert_producto(
        db,
        user.id,
        descripcion=payload.nombre,
        precio_unitario=payload.precio_unitario,
        unidad=payload.unidad,
        tipo=payload.tipo,
    )
    if payload.codigo:
        producto.codigo = payload.codigo
    db.commit()
    db.refresh(producto)
    return producto


@router.put("/{producto_id}", response_model=ProductoOut)
def actualizar(
    producto_id: int,
    payload: ProductoUpdate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    producto = _get_owned(db, user, producto_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(producto, key, value)
    db.commit()
    db.refresh(producto)
    return producto


@router.delete("/{producto_id}")
def eliminar(
    producto_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    producto = _get_owned(db, user, producto_id)
    producto.activo = False
    db.commit()
    return {"ok": True}
