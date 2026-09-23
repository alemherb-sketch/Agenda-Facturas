from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import MovimientoCombustible, TipoMovimientoCombustible, Usuario
from app.schemas import (
    AdjuntoOut,
    CombustibleResumenOut,
    MovimientoCombustibleCreate,
    MovimientoCombustibleOut,
    MovimientoCombustibleUpdate,
)
from app.services.adjuntos import (
    ENTIDAD_COMBUSTIBLE,
    crear_adjunto,
    eliminar_adjuntos_entidad,
    listar_adjuntos,
    map_adjuntos_por_entidad,
)
from app.services.excel_service import generar_excel_reporte_combustibles
from app.services.pdf_service import generar_pdf_reporte_combustibles


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


def _comb_out(db: Session, mov: MovimientoCombustible, adjuntos_rows=None) -> MovimientoCombustibleOut:
    rows = adjuntos_rows if adjuntos_rows is not None else listar_adjuntos(db, ENTIDAD_COMBUSTIBLE, mov.id)
    out = MovimientoCombustibleOut.model_validate(mov)
    out.adjuntos = [AdjuntoOut.from_row(r) for r in rows]
    out.tiene_adjunto = bool(out.adjuntos)
    return out


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

    agg_rows = (
        db.query(MovimientoCombustible)
        .filter(MovimientoCombustible.usuario_id == user.id)
    )
    agg_rows = _apply_filters(
        agg_rows, tipo=tipo, q=q, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, placa=placa
    ).all()

    por_dia_map: dict[str, dict] = defaultdict(
        lambda: {"ingresos": Decimal("0"), "salidas": Decimal("0")}
    )
    por_placa_map: dict[str, dict] = defaultdict(
        lambda: {"ingresos": Decimal("0"), "salidas": Decimal("0")}
    )
    por_conductor_map: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    por_marca_map: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for mov in agg_rows:
        g = Decimal(str(mov.galones))
        dia = mov.fecha.isoformat()
        placa_key = (mov.placa or "Sin placa").upper()
        if mov.tipo == TipoMovimientoCombustible.INGRESO:
            por_dia_map[dia]["ingresos"] += g
            por_placa_map[placa_key]["ingresos"] += g
        else:
            por_dia_map[dia]["salidas"] += g
            por_placa_map[placa_key]["salidas"] += g
            por_conductor_map[mov.conductor or "Sin conductor"] += g
            por_marca_map[mov.marca or "Sin marca"] += g

    por_dia = [
        {
            "fecha": dia,
            "ingresos": float(vals["ingresos"]),
            "salidas": float(vals["salidas"]),
            "neto": float(vals["ingresos"] - vals["salidas"]),
        }
        for dia, vals in sorted(por_dia_map.items())
    ]
    por_placa = sorted(
        [
            {
                "placa": placa_key,
                "ingresos": float(vals["ingresos"]),
                "salidas": float(vals["salidas"]),
                "neto": float(vals["ingresos"] - vals["salidas"]),
            }
            for placa_key, vals in por_placa_map.items()
        ],
        key=lambda x: x["salidas"],
        reverse=True,
    )[:10]
    por_conductor = sorted(
        [
            {"conductor": nombre, "salidas": float(total)}
            for nombre, total in por_conductor_map.items()
        ],
        key=lambda x: x["salidas"],
        reverse=True,
    )[:8]
    por_marca = sorted(
        [{"marca": nombre, "salidas": float(total)} for nombre, total in por_marca_map.items()],
        key=lambda x: x["salidas"],
        reverse=True,
    )[:8]

    by_adj = map_adjuntos_por_entidad(db, ENTIDAD_COMBUSTIBLE, [m.id for m in movimientos])
    return CombustibleResumenOut(
        total_ingresos=ingresos,
        total_salidas=salidas,
        saldo_galones=ingresos - salidas,
        cantidad_movimientos=int(cantidad),
        por_dia=por_dia,
        por_placa=por_placa,
        por_conductor=por_conductor,
        por_marca=por_marca,
        movimientos=[_comb_out(db, m, by_adj.get(m.id, [])) for m in movimientos],
    )


@router.get("/reporte")
def reporte_pdf(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    tipo: str | None = None,
    q: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    placa: str | None = None,
    limit: int = Query(500, le=1000),
):
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(status_code=400, detail="La fecha desde no puede ser mayor a la fecha hasta")

    query = db.query(MovimientoCombustible).filter(MovimientoCombustible.usuario_id == user.id)
    query = _apply_filters(
        query, tipo=tipo, q=q, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, placa=placa
    )
    movimientos = (
        query.order_by(MovimientoCombustible.fecha.desc(), MovimientoCombustible.id.desc())
        .limit(limit)
        .all()
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

    pdf = generar_pdf_reporte_combustibles(
        movimientos,
        filtros={
            "fecha_desde": fecha_desde.isoformat() if fecha_desde else None,
            "fecha_hasta": fecha_hasta.isoformat() if fecha_hasta else None,
            "tipo": tipo,
            "q": q,
            "placa": placa,
        },
        total_ingresos=float(ingresos),
        total_salidas=float(salidas),
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="reporte-combustibles.pdf"'},
    )


@router.get("/reporte-excel")
def reporte_excel(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    tipo: str | None = None,
    q: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    placa: str | None = None,
    limit: int = Query(1000, le=5000),
):
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(status_code=400, detail="La fecha desde no puede ser mayor a la fecha hasta")

    query = db.query(MovimientoCombustible).filter(MovimientoCombustible.usuario_id == user.id)
    query = _apply_filters(
        query, tipo=tipo, q=q, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, placa=placa
    )
    movimientos = (
        query.order_by(MovimientoCombustible.fecha.desc(), MovimientoCombustible.id.desc())
        .limit(limit)
        .all()
    )
    content = generar_excel_reporte_combustibles(movimientos)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="reporte-combustibles.xlsx"'},
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
    rows = (
        query.order_by(MovimientoCombustible.fecha.desc(), MovimientoCombustible.id.desc())
        .limit(limit)
        .all()
    )
    by_adj = map_adjuntos_por_entidad(db, ENTIDAD_COMBUSTIBLE, [m.id for m in rows])
    return [_comb_out(db, m, by_adj.get(m.id, [])) for m in rows]


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
    return _comb_out(db, mov)


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
    return _comb_out(db, mov)


@router.post("/{movimiento_id}/adjuntos", response_model=MovimientoCombustibleOut)
async def subir_adjuntos(
    movimiento_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    archivos: list[UploadFile] = File(...),
):
    mov = _get_owned(db, user, movimiento_id)
    if not archivos:
        raise HTTPException(status_code=400, detail="Seleccione al menos un archivo")
    for archivo in archivos:
        await crear_adjunto(
            db,
            user=user,
            entidad_tipo=ENTIDAD_COMBUSTIBLE,
            entidad_id=mov.id,
            kind="combustibles",
            archivo=archivo,
        )
    return _comb_out(db, mov)


@router.get("/{movimiento_id}/adjuntos", response_model=list[AdjuntoOut])
def listar_adjuntos_combustible(
    movimiento_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _get_owned(db, user, movimiento_id)
    return [AdjuntoOut.from_row(r) for r in listar_adjuntos(db, ENTIDAD_COMBUSTIBLE, movimiento_id)]


@router.delete("/{movimiento_id}")
def eliminar(
    movimiento_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    mov = _get_owned(db, user, movimiento_id)
    eliminar_adjuntos_entidad(db, ENTIDAD_COMBUSTIBLE, mov.id)
    db.delete(mov)
    db.commit()
    return {"ok": True}
