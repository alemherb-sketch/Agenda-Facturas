from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Caja, MovimientoCaja, TipoMovimientoCaja, Usuario
from app.schemas import (
    CajaCreate,
    CajaOut,
    CajaUpdate,
    MovimientoCajaCreate,
    MovimientoCajaOut,
    MovimientoCajaUpdate,
)

router = APIRouter(prefix="/api/cajas", tags=["cajas"])


def _get_caja(db: Session, user: Usuario, caja_id: int) -> Caja:
    caja = db.query(Caja).filter(Caja.id == caja_id, Caja.usuario_id == user.id).first()
    if not caja:
        raise HTTPException(status_code=404, detail="Caja no encontrada")
    return caja


def _totales_caja(db: Session, caja_id: int) -> tuple[Decimal, Decimal, Decimal]:
    rows = (
        db.query(MovimientoCaja.tipo, func.coalesce(func.sum(MovimientoCaja.monto), 0))
        .filter(MovimientoCaja.caja_id == caja_id)
        .group_by(MovimientoCaja.tipo)
        .all()
    )
    ingresos = Decimal("0.00")
    egresos = Decimal("0.00")
    for tipo, total in rows:
        valor = Decimal(str(total))
        if tipo == TipoMovimientoCaja.INGRESO:
            ingresos = valor
        elif tipo == TipoMovimientoCaja.EGRESO:
            egresos = valor
    return ingresos - egresos, ingresos, egresos


def _caja_out(db: Session, caja: Caja) -> CajaOut:
    saldo, ingresos, egresos = _totales_caja(db, caja.id)
    return CajaOut(
        id=caja.id,
        nombre=caja.nombre,
        descripcion=caja.descripcion,
        activo=caja.activo,
        saldo=saldo,
        total_ingresos=ingresos,
        total_egresos=egresos,
        creado_en=caja.creado_en,
    )


def _mov_out(mov: MovimientoCaja) -> MovimientoCajaOut:
    return MovimientoCajaOut(
        id=mov.id,
        caja_id=mov.caja_id,
        caja_nombre=mov.caja.nombre if mov.caja else "",
        tipo=mov.tipo,
        monto=mov.monto,
        concepto=mov.concepto,
        fecha=mov.fecha,
        creado_en=mov.creado_en,
    )


@router.get("", response_model=list[CajaOut])
def listar_cajas(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    activas: bool = True,
):
    query = db.query(Caja).filter(Caja.usuario_id == user.id)
    if activas:
        query = query.filter(Caja.activo.is_(True))
    cajas = query.order_by(Caja.nombre.asc()).all()
    return [_caja_out(db, c) for c in cajas]


@router.post("", response_model=CajaOut, status_code=201)
def crear_caja(
    payload: CajaCreate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    nombre = payload.nombre.strip()
    existe = (
        db.query(Caja)
        .filter(Caja.usuario_id == user.id, Caja.nombre == nombre)
        .first()
    )
    if existe:
        raise HTTPException(status_code=400, detail="Ya existe una caja con ese nombre")
    caja = Caja(usuario_id=user.id, nombre=nombre, descripcion=payload.descripcion)
    db.add(caja)
    db.commit()
    db.refresh(caja)
    return _caja_out(db, caja)


@router.put("/{caja_id}", response_model=CajaOut)
def actualizar_caja(
    caja_id: int,
    payload: CajaUpdate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    caja = _get_caja(db, user, caja_id)
    data = payload.model_dump(exclude_unset=True)
    if "nombre" in data and data["nombre"]:
        data["nombre"] = data["nombre"].strip()
        dup = (
            db.query(Caja)
            .filter(
                Caja.usuario_id == user.id,
                Caja.nombre == data["nombre"],
                Caja.id != caja.id,
            )
            .first()
        )
        if dup:
            raise HTTPException(status_code=400, detail="Ya existe una caja con ese nombre")
    for key, value in data.items():
        setattr(caja, key, value)
    db.commit()
    db.refresh(caja)
    return _caja_out(db, caja)


@router.delete("/{caja_id}")
def eliminar_caja(
    caja_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    caja = _get_caja(db, user, caja_id)
    caja.activo = False
    db.commit()
    return {"ok": True}


@router.get("/movimientos", response_model=list[MovimientoCajaOut])
def listar_movimientos(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    caja_id: int | None = None,
    tipo: str | None = None,
    q: str | None = None,
    limit: int = Query(200, le=500),
):
    query = (
        db.query(MovimientoCaja)
        .options(joinedload(MovimientoCaja.caja))
        .filter(MovimientoCaja.usuario_id == user.id)
        .order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc())
    )
    if caja_id:
        query = query.filter(MovimientoCaja.caja_id == caja_id)
    if tipo:
        query = query.filter(MovimientoCaja.tipo == tipo)
    if q:
        like = f"%{q}%"
        query = query.filter(MovimientoCaja.concepto.ilike(like))
    return [_mov_out(m) for m in query.limit(limit).all()]


@router.post("/movimientos", response_model=MovimientoCajaOut, status_code=201)
def crear_movimiento(
    payload: MovimientoCajaCreate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    caja = _get_caja(db, user, payload.caja_id)
    if not caja.activo:
        raise HTTPException(status_code=400, detail="La caja está inactiva")
    mov = MovimientoCaja(
        usuario_id=user.id,
        caja_id=caja.id,
        tipo=payload.tipo,
        monto=payload.monto,
        concepto=payload.concepto.strip(),
        fecha=payload.fecha,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    mov = (
        db.query(MovimientoCaja)
        .options(joinedload(MovimientoCaja.caja))
        .filter(MovimientoCaja.id == mov.id)
        .first()
    )
    return _mov_out(mov)


@router.put("/movimientos/{movimiento_id}", response_model=MovimientoCajaOut)
def actualizar_movimiento(
    movimiento_id: int,
    payload: MovimientoCajaUpdate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    mov = (
        db.query(MovimientoCaja)
        .options(joinedload(MovimientoCaja.caja))
        .filter(MovimientoCaja.id == movimiento_id, MovimientoCaja.usuario_id == user.id)
        .first()
    )
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    data = payload.model_dump(exclude_unset=True)
    if "caja_id" in data and data["caja_id"] is not None:
        _get_caja(db, user, data["caja_id"])
    if "concepto" in data and data["concepto"]:
        data["concepto"] = data["concepto"].strip()
    for key, value in data.items():
        setattr(mov, key, value)
    db.commit()
    db.refresh(mov)
    mov = (
        db.query(MovimientoCaja)
        .options(joinedload(MovimientoCaja.caja))
        .filter(MovimientoCaja.id == mov.id)
        .first()
    )
    return _mov_out(mov)


@router.delete("/movimientos/{movimiento_id}")
def eliminar_movimiento(
    movimiento_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    mov = (
        db.query(MovimientoCaja)
        .filter(MovimientoCaja.id == movimiento_id, MovimientoCaja.usuario_id == user.id)
        .first()
    )
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    db.delete(mov)
    db.commit()
    return {"ok": True}
