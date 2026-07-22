from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Caja, MovimientoCaja, TipoMovimientoCaja, Usuario
from app.schemas import (
    CajaCreate,
    CajaDashboardOut,
    CajaOut,
    CajaUpdate,
    MovimientoCajaCreate,
    MovimientoCajaOut,
    MovimientoCajaUpdate,
)
from app.services.pdf_service import generar_pdf_reporte_cajas

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


def _clean_numero(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _mov_out(mov: MovimientoCaja) -> MovimientoCajaOut:
    return MovimientoCajaOut(
        id=mov.id,
        caja_id=mov.caja_id,
        caja_nombre=mov.caja.nombre if mov.caja else "",
        tipo=mov.tipo,
        monto=mov.monto,
        numero_transaccion=mov.numero_transaccion,
        concepto=mov.concepto,
        fecha=mov.fecha,
        creado_en=mov.creado_en,
    )


def _apply_mov_filters(
    query,
    *,
    caja_id: int | None = None,
    tipo: str | None = None,
    q: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
):
    if caja_id:
        query = query.filter(MovimientoCaja.caja_id == caja_id)
    if tipo:
        query = query.filter(MovimientoCaja.tipo == tipo)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                MovimientoCaja.concepto.ilike(like),
                MovimientoCaja.numero_transaccion.ilike(like),
            )
        )
    if fecha_desde:
        query = query.filter(MovimientoCaja.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(MovimientoCaja.fecha <= fecha_hasta)
    return query


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


@router.get("/dashboard", response_model=CajaDashboardOut)
def dashboard_cajas(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    caja_id: int | None = None,
    tipo: str | None = None,
    q: str | None = None,
    limit: int = Query(300, le=500),
):
    hoy = date.today()
    if fecha_hasta is None:
        fecha_hasta = hoy
    if fecha_desde is None:
        fecha_desde = fecha_hasta.replace(day=1)
    if fecha_desde > fecha_hasta:
        raise HTTPException(status_code=400, detail="La fecha desde no puede ser mayor a la fecha hasta")

    query = (
        db.query(MovimientoCaja)
        .options(joinedload(MovimientoCaja.caja))
        .filter(MovimientoCaja.usuario_id == user.id)
    )
    query = _apply_mov_filters(
        query,
        caja_id=caja_id,
        tipo=tipo,
        q=q,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    totales = (
        db.query(MovimientoCaja.tipo, func.coalesce(func.sum(MovimientoCaja.monto), 0))
        .filter(MovimientoCaja.usuario_id == user.id)
    )
    totales = _apply_mov_filters(
        totales,
        caja_id=caja_id,
        tipo=tipo,
        q=q,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    total_ingresos = Decimal("0.00")
    total_egresos = Decimal("0.00")
    for tipo_row, total in totales.group_by(MovimientoCaja.tipo).all():
        valor = Decimal(str(total))
        if tipo_row == TipoMovimientoCaja.INGRESO:
            total_ingresos = valor
        elif tipo_row == TipoMovimientoCaja.EGRESO:
            total_egresos = valor

    cantidad = (
        db.query(func.count(MovimientoCaja.id)).filter(MovimientoCaja.usuario_id == user.id)
    )
    cantidad = _apply_mov_filters(
        cantidad,
        caja_id=caja_id,
        tipo=tipo,
        q=q,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    ).scalar() or 0

    movimientos = query.order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc()).limit(limit).all()

    por_caja_map: dict[str, dict] = defaultdict(
        lambda: {"ingresos": Decimal("0.00"), "egresos": Decimal("0.00")}
    )
    por_dia_map: dict[str, dict] = defaultdict(
        lambda: {"ingresos": Decimal("0.00"), "egresos": Decimal("0.00")}
    )

    # Agregados de gráficos sobre el universo filtrado (sin tope de listado)
    agg_rows = (
        db.query(MovimientoCaja)
        .options(joinedload(MovimientoCaja.caja))
        .filter(MovimientoCaja.usuario_id == user.id)
    )
    agg_rows = _apply_mov_filters(
        agg_rows,
        caja_id=caja_id,
        tipo=tipo,
        q=q,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    ).all()

    for mov in agg_rows:
        monto = Decimal(str(mov.monto))
        caja_nombre = mov.caja.nombre if mov.caja else f"Caja #{mov.caja_id}"
        dia = mov.fecha.isoformat()
        if mov.tipo == TipoMovimientoCaja.INGRESO:
            por_caja_map[caja_nombre]["ingresos"] += monto
            por_dia_map[dia]["ingresos"] += monto
        else:
            por_caja_map[caja_nombre]["egresos"] += monto
            por_dia_map[dia]["egresos"] += monto

    por_caja = [
        {
            "caja": nombre,
            "ingresos": float(vals["ingresos"]),
            "egresos": float(vals["egresos"]),
            "saldo": float(vals["ingresos"] - vals["egresos"]),
        }
        for nombre, vals in sorted(por_caja_map.items())
    ]
    por_dia = [
        {
            "fecha": dia,
            "ingresos": float(vals["ingresos"]),
            "egresos": float(vals["egresos"]),
            "saldo": float(vals["ingresos"] - vals["egresos"]),
        }
        for dia, vals in sorted(por_dia_map.items())
    ]

    return CajaDashboardOut(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        total_ingresos=total_ingresos,
        total_egresos=total_egresos,
        saldo_periodo=total_ingresos - total_egresos,
        cantidad_movimientos=int(cantidad),
        por_caja=por_caja,
        por_dia=por_dia,
        movimientos=[_mov_out(m) for m in movimientos],
    )


@router.get("/reporte")
def reporte_pdf(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    caja_id: int | None = None,
    tipo: str | None = None,
    q: str | None = None,
    limit: int = Query(500, le=1000),
):
    hoy = date.today()
    if fecha_hasta is None:
        fecha_hasta = hoy
    if fecha_desde is None:
        fecha_desde = fecha_hasta.replace(day=1)
    if fecha_desde > fecha_hasta:
        raise HTTPException(status_code=400, detail="La fecha desde no puede ser mayor a la fecha hasta")

    query = (
        db.query(MovimientoCaja)
        .options(joinedload(MovimientoCaja.caja))
        .filter(MovimientoCaja.usuario_id == user.id)
    )
    query = _apply_mov_filters(
        query,
        caja_id=caja_id,
        tipo=tipo,
        q=q,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    movimientos = query.order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc()).limit(limit).all()

    totales = (
        db.query(MovimientoCaja.tipo, func.coalesce(func.sum(MovimientoCaja.monto), 0))
        .filter(MovimientoCaja.usuario_id == user.id)
    )
    totales = _apply_mov_filters(
        totales,
        caja_id=caja_id,
        tipo=tipo,
        q=q,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    total_ingresos = Decimal("0.00")
    total_egresos = Decimal("0.00")
    for tipo_row, total in totales.group_by(MovimientoCaja.tipo).all():
        valor = Decimal(str(total))
        if tipo_row == TipoMovimientoCaja.INGRESO:
            total_ingresos = valor
        elif tipo_row == TipoMovimientoCaja.EGRESO:
            total_egresos = valor

    caja_nombre = None
    if caja_id:
        caja = _get_caja(db, user, caja_id)
        caja_nombre = caja.nombre

    pdf = generar_pdf_reporte_cajas(
        movimientos,
        filtros={
            "fecha_desde": fecha_desde.isoformat(),
            "fecha_hasta": fecha_hasta.isoformat(),
            "caja": caja_nombre,
            "tipo": tipo,
            "q": q,
        },
        total_ingresos=float(total_ingresos),
        total_egresos=float(total_egresos),
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="reporte-cajas.pdf"'},
    )


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
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    limit: int = Query(200, le=500),
):
    query = (
        db.query(MovimientoCaja)
        .options(joinedload(MovimientoCaja.caja))
        .filter(MovimientoCaja.usuario_id == user.id)
        .order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc())
    )
    query = _apply_mov_filters(
        query,
        caja_id=caja_id,
        tipo=tipo,
        q=q,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
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
        numero_transaccion=_clean_numero(payload.numero_transaccion),
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
    if "numero_transaccion" in data:
        data["numero_transaccion"] = _clean_numero(data["numero_transaccion"])
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
