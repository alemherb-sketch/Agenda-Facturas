from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Producto, Usuario
from app.schemas import AdjuntoOut, ProductoCreate, ProductoOut, ProductoUpdate
from app.services.adjuntos import (
    ENTIDAD_PRODUCTO,
    crear_adjunto,
    listar_adjuntos,
    map_adjuntos_por_entidad,
)
from app.services.catalogo import upsert_producto

router = APIRouter(prefix="/api/productos", tags=["productos"])


def _get_owned(db: Session, user: Usuario, producto_id: int) -> Producto:
    item = db.query(Producto).filter(Producto.id == producto_id, Producto.usuario_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return item


def _producto_out(item: Producto, adjuntos_rows=None) -> ProductoOut:
    rows = adjuntos_rows if adjuntos_rows is not None else []
    out = ProductoOut.model_validate(item)
    out.adjuntos = [AdjuntoOut.from_row(r) for r in rows]
    out.tiene_adjunto = bool(out.adjuntos)
    return out


def _producto_out_db(db: Session, item: Producto) -> ProductoOut:
    return _producto_out(item, listar_adjuntos(db, ENTIDAD_PRODUCTO, item.id))


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
    items = query.limit(limit).all()
    by_adj = map_adjuntos_por_entidad(db, ENTIDAD_PRODUCTO, [i.id for i in items])
    return [_producto_out(i, by_adj.get(i.id, [])) for i in items]


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
    return _producto_out_db(db, producto)


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
    return _producto_out_db(db, producto)


@router.post("/{producto_id}/adjuntos", response_model=ProductoOut)
async def subir_adjuntos(
    producto_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    archivos: list[UploadFile] = File(...),
):
    producto = _get_owned(db, user, producto_id)
    if not archivos:
        raise HTTPException(status_code=400, detail="Seleccione al menos un archivo")
    for archivo in archivos:
        await crear_adjunto(
            db,
            user=user,
            entidad_tipo=ENTIDAD_PRODUCTO,
            entidad_id=producto.id,
            kind="productos",
            archivo=archivo,
        )
    return _producto_out_db(db, _get_owned(db, user, producto.id))


@router.get("/{producto_id}/adjuntos", response_model=list[AdjuntoOut])
def listar_adjuntos_producto(
    producto_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _get_owned(db, user, producto_id)
    return [AdjuntoOut.from_row(r) for r in listar_adjuntos(db, ENTIDAD_PRODUCTO, producto_id)]


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
