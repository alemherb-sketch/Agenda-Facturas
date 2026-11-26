"""Reporte de mantenimiento: registros de PM por equipo según el plan de repuestos de su hoja."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Mantenimiento, MantenimientoRepuesto, Usuario
from app.schemas import MantenimientoIn, MantenimientoOut
from app.services.mantenimiento_planes import (
    EQUIPOS_POR_ID,
    LEYENDA_PM,
    catalogo_publico,
    frecuencia,
    normalizar_parte,
    partes_programadas,
    proximo,
)

router = APIRouter(prefix="/api/mantenimientos", tags=["mantenimientos"])

_DECIMO = Decimal("0.1")
_CENTESIMO = Decimal("0.01")


def _clean(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split())
    return text[:max_len] if text else None


def _texto(value: str | None, max_len: int) -> str | None:
    """Texto de varias líneas: conserva los saltos de línea y quita espacios sobrantes."""
    if value is None:
        return None
    lineas = [" ".join(linea.split()) for linea in value.replace("\r\n", "\n").split("\n")]
    text = "\n".join(lineas).strip()
    return text[:max_len] if text else None


def _get_owned(db: Session, user: Usuario, mant_id: int) -> Mantenimiento:
    mant = (
        db.query(Mantenimiento)
        .options(selectinload(Mantenimiento.repuestos))
        .filter(Mantenimiento.id == mant_id, Mantenimiento.usuario_id == user.id)
        .first()
    )
    if not mant:
        raise HTTPException(status_code=404, detail="Mantenimiento no encontrado")
    return mant


def _out(mant: Mantenimiento) -> MantenimientoOut:
    data = MantenimientoOut.model_validate(mant)
    data.pm_label = LEYENDA_PM.get(mant.pm, mant.pm)
    return data


def _aplicar(mant: Mantenimiento, payload: MantenimientoIn) -> None:
    equipo = EQUIPOS_POR_ID.get(payload.equipo.strip().upper())
    if not equipo:
        raise HTTPException(status_code=400, detail="Equipo no encontrado")
    columna = frecuencia(equipo, payload.frecuencia_horas)
    if not columna:
        raise HTTPException(
            status_code=400,
            detail=f"El {equipo['modelo']} no tiene mantenimiento a las {payload.frecuencia_horas} h de su ciclo",
        )
    programadas = partes_programadas(equipo, columna["horas"])
    repuestos: list[MantenimientoRepuesto] = []
    for item, rep in enumerate(payload.repuestos, start=1):
        descripcion = _clean(rep.descripcion, 200)
        if not descripcion:
            raise HTTPException(status_code=400, detail="Indique la descripción de cada repuesto")
        parte = _clean(rep.numero_parte, 30)
        parte = parte.upper() if parte else None
        repuestos.append(
            MantenimientoRepuesto(
                item=item,
                numero_parte=parte,
                descripcion=descripcion,
                cantidad=Decimal(rep.cantidad).quantize(_CENTESIMO, rounding=ROUND_HALF_UP),
                programado=bool(parte) and normalizar_parte(parte) in programadas,
            )
        )

    mant.equipo = equipo["id"]
    mant.equipo_tipo = equipo["tipo"]
    mant.marca = equipo["marca"]
    mant.modelo = equipo["modelo"]
    mant.serie = equipo["serie"]
    mant.motor_modelo = equipo["motor_modelo"]
    mant.motor_serie = equipo["motor_serie"]
    mant.anio = equipo["anio"]
    mant.pm = columna["pm"]
    mant.frecuencia_horas = columna["horas"]
    mant.fecha = payload.fecha
    mant.horometro = (
        Decimal(payload.horometro).quantize(_DECIMO, rounding=ROUND_HALF_UP)
        if payload.horometro is not None
        else None
    )
    mant.responsable = _clean(payload.responsable, 150)
    mant.observaciones = _texto(payload.observaciones, 2000)
    mant.repuestos = repuestos


def _apply_filters(
    query,
    *,
    equipo: str | None,
    pm: str | None,
    q: str | None,
    fecha_desde: date | None,
    fecha_hasta: date | None,
):
    if equipo:
        query = query.filter(Mantenimiento.equipo == equipo.strip().upper())
    if pm:
        query = query.filter(Mantenimiento.pm == pm.strip().upper())
    if fecha_desde:
        query = query.filter(Mantenimiento.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Mantenimiento.fecha <= fecha_hasta)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Mantenimiento.equipo_tipo.ilike(like),
                Mantenimiento.modelo.ilike(like),
                Mantenimiento.serie.ilike(like),
                Mantenimiento.responsable.ilike(like),
                Mantenimiento.observaciones.ilike(like),
                Mantenimiento.repuestos.any(
                    or_(
                        MantenimientoRepuesto.numero_parte.ilike(like),
                        MantenimientoRepuesto.descripcion.ilike(like),
                    )
                ),
            )
        )
    return query


@router.get("/equipos")
def listar_equipos(user: Annotated[Usuario, Depends(get_current_user)]):
    return catalogo_publico()


@router.get("/resumen")
def resumen(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Por equipo: cuántos mantenimientos hay, el último registrado y el PM que sigue en su ciclo."""
    conteos = (
        db.query(Mantenimiento.equipo, func.count(Mantenimiento.id))
        .filter(Mantenimiento.usuario_id == user.id)
        .group_by(Mantenimiento.equipo)
        .all()
    )
    salida: dict[str, dict] = {}
    for equipo_id, cantidad in conteos:
        ultimo = (
            db.query(Mantenimiento)
            .filter(Mantenimiento.usuario_id == user.id, Mantenimiento.equipo == equipo_id)
            .order_by(Mantenimiento.fecha.desc(), Mantenimiento.id.desc())
            .first()
        )
        horometro = float(ultimo.horometro) if ultimo.horometro is not None else None
        equipo = EQUIPOS_POR_ID.get(equipo_id)
        salida[equipo_id] = {
            "cantidad": int(cantidad),
            "ultimo": {
                "id": ultimo.id,
                "fecha": ultimo.fecha.isoformat(),
                "pm": ultimo.pm,
                "frecuencia_horas": ultimo.frecuencia_horas,
                "horometro": horometro,
            },
            "proximo": proximo(equipo, ultimo.frecuencia_horas, horometro) if equipo else None,
        }
    return salida


@router.get("", response_model=list[MantenimientoOut])
def listar(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    equipo: str | None = None,
    pm: str | None = None,
    q: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    limit: int = Query(300, ge=1, le=1000),
):
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(status_code=400, detail="La fecha desde no puede ser mayor a la fecha hasta")
    query = (
        db.query(Mantenimiento)
        .options(selectinload(Mantenimiento.repuestos))
        .filter(Mantenimiento.usuario_id == user.id)
    )
    query = _apply_filters(query, equipo=equipo, pm=pm, q=q, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    rows = query.order_by(Mantenimiento.fecha.desc(), Mantenimiento.id.desc()).limit(limit).all()
    return [_out(m) for m in rows]


@router.get("/{mant_id}", response_model=MantenimientoOut)
def obtener(
    mant_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return _out(_get_owned(db, user, mant_id))


@router.post("", response_model=MantenimientoOut, status_code=201)
def crear(
    payload: MantenimientoIn,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    mant = Mantenimiento(usuario_id=user.id)
    _aplicar(mant, payload)
    db.add(mant)
    db.commit()
    db.refresh(mant)
    return _out(mant)


@router.put("/{mant_id}", response_model=MantenimientoOut)
def actualizar(
    mant_id: int,
    payload: MantenimientoIn,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    mant = _get_owned(db, user, mant_id)
    _aplicar(mant, payload)
    db.commit()
    db.refresh(mant)
    return _out(mant)


@router.delete("/{mant_id}")
def eliminar(
    mant_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    mant = _get_owned(db, user, mant_id)
    db.delete(mant)
    db.commit()
    return {"ok": True}
