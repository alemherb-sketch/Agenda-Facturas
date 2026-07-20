from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import MovimientoCombustible, TipoMovimientoCombustible, Usuario
from app.schemas import (
    CombustibleResumenOut,
    MovimientoCombustibleCreate,
    MovimientoCombustibleOut,
    MovimientoCombustibleUpdate,
)

router = APIRouter(prefix="/api/combustibles", tags=["combustibles"])


def _clean(value: str | None, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if max_len:
        return text[:max_len]
    return text


def _get_owned(db: Session, user: Usuario, movimiento_id: int) -> MovimientoCombustible:
    mov = (
        db.query(MovimientoCombustible)
        .filter(
            MovimientoCombustible.id == movimiento_id,
            MovimientoCombustible.usuario_id == user.id,
        )
        .first()
    )
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento de combustible no encontrado")
    return mov


def _apply_filters(
    query,
    *,
    tipo: str | None = None,
    q: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    placa: str | None = None,
):
    if tipo:
        query = query.filter(MovimientoCombustible.tipo == tipo)
    if placa:
        query = query.filter(MovimientoCombustible.placa.ilike(f"%{placa.strip()}%"))
    if fecha_desde:
        query = query.filter(MovimientoCombustible.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(MovimientoCombustible.fecha <= fecha_hasta)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                MovimientoCombustible.conductor.ilike(like),
                MovimientoCombustible.marca.ilike(like),
                MovimientoCombustible.placa.ilike(like),
                MovimientoCombustible.notas.ilike(like),
            )
        )
    return query


@router.get("/resumen", response_model=CombustibleResumenOut)
def resumen(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    tipo: str | None = None,
    q: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    placa: str | None = None,
    limit: int = Query(300, le=500),
):
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(status_code=400, detail="La fecha desde no puede ser mayor a la fecha hasta")

    base = db.query(MovimientoCombustible).filter(MovimientoCombustible.usuario_id == user.id)
    base = _apply_filters(
        base, tipo=tipo, q=q, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, placa=placa
    )

    totales = (
        db.query(
            MovimientoCombustible.tipo,
            func.coalesce(func.sum(MovimientoCombustible.galones), 0),
        )
        .filter(MovimientoCombustible.usuario_id == user.id)
    )
    totales = _apply_filters(
        totales, tipo=tipo, q=q, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, placa=placa
    )
    ingresos = Decimal("0.000")
    salidas = Decimal("0.000")
    for tipo_row, total in totales.group_by(MovimientoCombustible.tipo).all():
        valor = Decimal(str(total))
        if tipo_row == TipoMovimientoCombustible.INGRESO:
            ingresos = valor
        elif tipo_row == TipoMovimientoCombustible.SALIDA:
            salidas = valor

    cantidad = base.with_entities(func.count(MovimientoCombustible.id)).scalar() or 0
    movimientos = (
        base.order_by(MovimientoCombustible.fecha.desc(), MovimientoCombustible.id.desc())
        .limit(limit)
        .all()
    )

    return CombustibleResumenOut(
        total_ingresos=ingresos,
        total_salidas=salidas,
        saldo_galones=ingresos - salidas,
        cantidad_movimientos=int(cantidad),
        movimientos=movimientos,
    )


@router.get("", response_model=list[MovimientoCombustibleOut])
def listar(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    tipo: str | None = None,
    q: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    placa: str | None = None,
    limit: int = Query(200, le=500),
):
    query = db.query(MovimientoCombustible).filter(MovimientoCombustible.usuario_id == user.id)
    query = _apply_filters(
        query, tipo=tipo, q=q, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, placa=placa
    )
    return query.order_by(MovimientoCombustible.fecha.desc(), MovimientoCombustible.id.desc()).limit(limit).all()


@router.post("", response_model=MovimientoCombustibleOut, status_code=201)
def crear(
    payload: MovimientoCombustibleCreate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    mov = MovimientoCombustible(
        usuario_id=user.id,
        tipo=payload.tipo,
        galones=payload.galones,
        fecha=payload.fecha,
        conductor=payload.conductor.strip(),
        marca=_clean(payload.marca, 80),
        placa=_clean(payload.placa, 20),
        notas=_clean(payload.notas, 300),
    )
    if mov.placa:
        mov.placa = mov.placa.upper()
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov


@router.put("/{movimiento_id}", response_model=MovimientoCombustibleOut)
def actualizar(
    movimiento_id: int,
    payload: MovimientoCombustibleUpdate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    mov = _get_owned(db, user, movimiento_id)
    data = payload.model_dump(exclude_unset=True)
    if "conductor" in data and data["conductor"]:
        data["conductor"] = data["conductor"].strip()
    for key in ("marca", "notas"):
        if key in data:
            data[key] = _clean(data[key], 80 if key == "marca" else 300)
    if "placa" in data:
        placa = _clean(data["placa"], 20)
        data["placa"] = placa.upper() if placa else None
    for key, value in data.items():
        setattr(mov, key, value)
    db.commit()
    db.refresh(mov)
    return mov


@router.delete("/{movimiento_id}")
def eliminar(
    movimiento_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    mov = _get_owned(db, user, movimiento_id)
    db.delete(mov)
    db.commit()
    return {"ok": True}
