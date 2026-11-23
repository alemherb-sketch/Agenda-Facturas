"""Gastos externos: registros por tipo (peaje, alimentación, hospedaje u otro)."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import GastoExterno, Usuario
from app.schemas import AdjuntoOut, GastoExternoCreate, GastoExternoOut, GastoExternoResumenOut, GastoExternoUpdate
from app.services.adjuntos import (
    ENTIDAD_GASTO,
    crear_adjunto,
    eliminar_adjuntos_entidad,
    listar_adjuntos,
    map_adjuntos_por_entidad,
)

router = APIRouter(prefix="/api/gastos-externos", tags=["gastos-externos"])

TIPOS_GASTO_EXTERNO = [
    "Peaje",
    "Alimentación",
    "Hospedaje",
    "Pasajes",
    "Movilidad",
    "Repuestos",
    "Materiales",
    "Servicios",
    "Viáticos",
    "Mantenimiento",
    "Otros",
]
_CENTAVO = Decimal("0.01")


def _clean(value: str | None, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split())
    if not text:
        return None
    if max_len:
        return text[:max_len]
    return text


def normalizar_tipo(valor: str) -> str:
    texto = _clean(valor, 80)
    if not texto:
        raise HTTPException(status_code=400, detail="Indique el tipo de gasto")
    for sugerido in TIPOS_GASTO_EXTERNO:
        if texto.casefold() == sugerido.casefold():
            return sugerido
    return texto


def _monto(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(_CENTAVO, rounding=ROUND_HALF_UP)


def _get_owned(db: Session, user: Usuario, gasto_id: int) -> GastoExterno:
    gasto = (
        db.query(GastoExterno)
        .filter(GastoExterno.id == gasto_id, GastoExterno.usuario_id == user.id)
        .first()
    )
    if not gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    return gasto


def _out(db: Session, gasto: GastoExterno, adjuntos_rows=None) -> GastoExternoOut:
    rows = adjuntos_rows if adjuntos_rows is not None else listar_adjuntos(db, ENTIDAD_GASTO, gasto.id)
    data = GastoExternoOut.model_validate(gasto)
    data.adjuntos = [AdjuntoOut.from_row(r) for r in rows]
    data.tiene_adjunto = bool(data.adjuntos)
    return data


def _apply_filters(query, *, tipo: str | None, q: str | None, fecha_desde: date | None, fecha_hasta: date | None):
    if tipo:
        query = query.filter(GastoExterno.tipo == normalizar_tipo(tipo))
    if fecha_desde:
        query = query.filter(GastoExterno.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(GastoExterno.fecha <= fecha_hasta)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                GastoExterno.tipo.ilike(like),
                GastoExterno.concepto.ilike(like),
                GastoExterno.proveedor.ilike(like),
                GastoExterno.comprobante.ilike(like),
                GastoExterno.notas.ilike(like),
            )
        )
    return query


def _tipos_del_usuario(db: Session, user: Usuario) -> list[str]:
    usados = [
        row[0]
        for row in db.query(GastoExterno.tipo)
        .filter(GastoExterno.usuario_id == user.id)
        .distinct()
        .order_by(GastoExterno.tipo)
        .all()
    ]
    tipos = list(TIPOS_GASTO_EXTERNO)
    for tipo in usados:
        if tipo not in tipos:
            tipos.append(tipo)
    return tipos


@router.get("/resumen", response_model=GastoExternoResumenOut)
def resumen(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    tipo: str | None = None,
    q: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    limit: int = Query(300, le=500),
):
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(status_code=400, detail="La fecha desde no puede ser mayor a la fecha hasta")

    base = db.query(GastoExterno).filter(GastoExterno.usuario_id == user.id)
    base = _apply_filters(base, tipo=tipo, q=q, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)

    totales = (
        db.query(
            GastoExterno.tipo,
            func.coalesce(func.sum(GastoExterno.monto), 0),
            func.count(GastoExterno.id),
        )
        .filter(GastoExterno.usuario_id == user.id)
    )
    totales = _apply_filters(totales, tipo=tipo, q=q, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    por_tipo = [
        {"tipo": nombre, "total": _monto(Decimal(str(total))), "cantidad": int(cantidad)}
        for nombre, total, cantidad in totales.group_by(GastoExterno.tipo).all()
    ]
    por_tipo.sort(key=lambda item: item["total"], reverse=True)

    gastos = base.order_by(GastoExterno.fecha.desc(), GastoExterno.id.desc()).limit(limit).all()
    by_adj = map_adjuntos_por_entidad(db, ENTIDAD_GASTO, [g.id for g in gastos])
    total = sum((item["total"] for item in por_tipo), Decimal("0.00"))
    cantidad = sum(item["cantidad"] for item in por_tipo)
    return GastoExternoResumenOut(
        total=total,
        cantidad=cantidad,
        por_tipo=por_tipo,
        tipos=_tipos_del_usuario(db, user),
        gastos=[_out(db, g, by_adj.get(g.id, [])) for g in gastos],
    )


@router.get("", response_model=list[GastoExternoOut])
def listar(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    tipo: str | None = None,
    q: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    limit: int = Query(300, le=500),
):
    query = db.query(GastoExterno).filter(GastoExterno.usuario_id == user.id)
    query = _apply_filters(query, tipo=tipo, q=q, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    rows = query.order_by(GastoExterno.fecha.desc(), GastoExterno.id.desc()).limit(limit).all()
    by_adj = map_adjuntos_por_entidad(db, ENTIDAD_GASTO, [g.id for g in rows])
    return [_out(db, g, by_adj.get(g.id, [])) for g in rows]


@router.post("", response_model=GastoExternoOut, status_code=201)
def crear(
    payload: GastoExternoCreate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    gasto = GastoExterno(
        usuario_id=user.id,
        tipo=normalizar_tipo(payload.tipo),
        concepto=_clean(payload.concepto, 300) or "",
        monto=_monto(payload.monto),
        fecha=payload.fecha,
        proveedor=_clean(payload.proveedor, 200),
        comprobante=_clean(payload.comprobante, 40),
        metodo_pago=payload.metodo_pago,
        notas=_clean(payload.notas, 300),
    )
    if not gasto.concepto:
        raise HTTPException(status_code=400, detail="Indique el concepto del gasto")
    db.add(gasto)
    db.commit()
    db.refresh(gasto)
    return _out(db, gasto)


@router.put("/{gasto_id}", response_model=GastoExternoOut)
def actualizar(
    gasto_id: int,
    payload: GastoExternoUpdate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    gasto = _get_owned(db, user, gasto_id)
    data = payload.model_dump(exclude_unset=True)
    if "tipo" in data:
        data["tipo"] = normalizar_tipo(data["tipo"])
    if "concepto" in data:
        data["concepto"] = _clean(data["concepto"], 300)
        if not data["concepto"]:
            raise HTTPException(status_code=400, detail="Indique el concepto del gasto")
    if "monto" in data and data["monto"] is not None:
        data["monto"] = _monto(data["monto"])
    for key, limite in (("proveedor", 200), ("comprobante", 40), ("notas", 300)):
        if key in data:
            data[key] = _clean(data[key], limite)
    for key, value in data.items():
        setattr(gasto, key, value)
    db.commit()
    db.refresh(gasto)
    return _out(db, gasto)


@router.post("/{gasto_id}/adjuntos", response_model=GastoExternoOut)
async def subir_adjuntos(
    gasto_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    archivos: list[UploadFile] = File(...),
):
    gasto = _get_owned(db, user, gasto_id)
    if not archivos:
        raise HTTPException(status_code=400, detail="Seleccione al menos un archivo")
    for archivo in archivos:
        await crear_adjunto(
            db,
            user=user,
            entidad_tipo=ENTIDAD_GASTO,
            entidad_id=gasto.id,
            kind="gastos",
            archivo=archivo,
        )
    return _out(db, gasto)


@router.delete("/{gasto_id}")
def eliminar(
    gasto_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    gasto = _get_owned(db, user, gasto_id)
    eliminar_adjuntos_entidad(db, ENTIDAD_GASTO, gasto.id)
    db.delete(gasto)
    db.commit()
    return {"ok": True}
