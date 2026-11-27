"""Plan trabajo: labores de minería convencional y uso diario de equipos, con las listas de la hoja DATOS."""

import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import PlanConvencional, PlanEquipo, Usuario
from app.schemas import (
    PlanConvencionalIn,
    PlanConvencionalListaOut,
    PlanConvencionalOut,
    PlanEquipoIn,
    PlanEquipoListaOut,
    PlanEquipoOut,
)
from app.services.plan_trabajo_datos import (
    GUARDIAS_POR_CODIGO,
    INSUMOS_IDS,
    LABORES_POR_CODIGO,
    MAESTROS,
    MAQUINAS_POR_CODIGO,
    MATERIALES_POR_CODIGO,
    TAREAS_POR_CODIGO,
    TIPOS_POR_CODIGO,
    TURNOS,
    catalogo_publico,
)

router = APIRouter(prefix="/api/plan-trabajo", tags=["plan-trabajo"])

_CENTESIMO = Decimal("0.01")
_MAXIMO = Decimal("9999999.99")


def _dec(valor) -> Decimal | None:
    return None if valor is None else Decimal(valor).quantize(_CENTESIMO, rounding=ROUND_HALF_UP)


def _clean(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split())
    return text[:max_len] if text else None


def _elegir(valor: str | None, por_codigo: dict, que: str) -> dict:
    """Busca el código en la lista de la hoja DATOS sin importar mayúsculas."""
    clave = (valor or "").strip().casefold()
    for codigo, item in por_codigo.items():
        if codigo.casefold() == clave:
            return item
    raise HTTPException(status_code=400, detail=f"{que} no está en la lista")


def _turno(valor: str | None) -> str:
    clave = (valor or "").strip().casefold()
    for t in TURNOS:
        if clave in (t["valor"].casefold(), t["label"].casefold()):
            return t["valor"]
    raise HTTPException(status_code=400, detail="El turno debe ser Día o Noche")


def _maestro(valor: str | None) -> str:
    clave = " ".join((valor or "").split()).casefold()
    for nombre in MAESTROS:
        if nombre.casefold() == clave:
            return nombre
    raise HTTPException(status_code=400, detail="El maestro perforista no está en la lista")


def _rango(fecha_desde: date | None, fecha_hasta: date | None) -> None:
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(status_code=400, detail="La fecha desde no puede ser mayor a la fecha hasta")


# ---------- Convencional ----------


def _insumos_limpios(entrada: dict[str, Decimal | None]) -> dict[str, Decimal]:
    cantidades: dict[str, Decimal] = {}
    for clave, cantidad in entrada.items():
        if clave not in INSUMOS_IDS:
            raise HTTPException(status_code=400, detail=f"Insumo desconocido: {clave}")
        if cantidad is None or cantidad == 0:
            continue
        if cantidad < 0 or cantidad > _MAXIMO:
            raise HTTPException(status_code=400, detail="Las cantidades de insumos deben ser positivas")
        cantidades[clave] = _dec(cantidad)
    return {clave: cantidades[clave] for clave in INSUMOS_IDS if clave in cantidades}


def _insumos_guardados(reg: PlanConvencional) -> dict[str, Decimal]:
    try:
        datos = json.loads(reg.insumos or "{}")
    except ValueError:
        return {}
    return {k: Decimal(str(v)) for k, v in datos.items()} if isinstance(datos, dict) else {}


def _out_conv(reg: PlanConvencional) -> PlanConvencionalOut:
    datos = {campo: getattr(reg, campo) for campo in PlanConvencionalOut.model_fields if campo != "insumos"}
    return PlanConvencionalOut(**datos, insumos=_insumos_guardados(reg))


def _aplicar_conv(reg: PlanConvencional, payload: PlanConvencionalIn) -> None:
    guardia = _elegir(payload.guardia, GUARDIAS_POR_CODIGO, "La guardia")
    labor = _elegir(payload.labor_codigo, LABORES_POR_CODIGO, "El código de labor")
    tarea = _elegir(payload.tarea_codigo, TAREAS_POR_CODIGO, "El código de tarea")
    material = _elegir(payload.material_codigo, MATERIALES_POR_CODIGO, "El código de material") if (
        payload.material_codigo or ""
    ).strip() else None
    tipo = _elegir(payload.tipo_codigo, TIPOS_POR_CODIGO, "El tipo de perforación") if (
        payload.tipo_codigo or ""
    ).strip() else None
    insumos = _insumos_limpios(payload.insumos)

    reg.fecha = payload.fecha
    reg.turno = _turno(payload.turno)
    reg.guardia = guardia["codigo"]
    reg.jefe_guardia = guardia["jefe"]
    reg.labor_codigo = labor["codigo"]
    reg.labor = labor["labor"]
    reg.fase = labor["fase"]
    reg.unidad = labor["unidad"]
    reg.nivel = labor["nivel"]
    reg.meta = labor["meta"]
    reg.seccion = labor["seccion"]
    reg.programa_m = _dec(labor["programa_m"])
    reg.maestro = _maestro(payload.maestro)
    reg.tarea_codigo = tarea["codigo"]
    reg.tarea = tarea["tarea"]
    reg.material_codigo = material["codigo"] if material else None
    reg.material = material["material"] if material else None
    reg.tipo_codigo = tipo["codigo"] if tipo else None
    reg.tipo_perforacion = tipo["tipo"] if tipo else None
    equipo = _clean(payload.equipo_perforacion, 60)
    reg.equipo_perforacion = equipo.upper() if equipo else None
    reg.numero_maquina = _clean(payload.numero_maquina, 20)
    reg.taladros_perforados = payload.taladros_perforados
    reg.longitud_perforacion = _dec(payload.longitud_perforacion)
    reg.pies_perforados = (
        _dec(payload.taladros_perforados * payload.longitud_perforacion)
        if payload.taladros_perforados is not None and payload.longitud_perforacion is not None
        else None
    )
    reg.taladros_disparados = payload.taladros_disparados
    reg.insumos = json.dumps({k: str(v) for k, v in insumos.items()})
    reg.tn_oxidos = _dec(payload.tn_oxidos)
    reg.tn_sulfuros = _dec(payload.tn_sulfuros)
    reg.avance_ml = _dec(payload.avance_ml)


def _conv_owned(db: Session, user: Usuario, reg_id: int) -> PlanConvencional:
    reg = (
        db.query(PlanConvencional)
        .filter(PlanConvencional.id == reg_id, PlanConvencional.usuario_id == user.id)
        .first()
    )
    if not reg:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return reg


@router.get("/catalogo")
def catalogo(user: Annotated[Usuario, Depends(get_current_user)]):
    return catalogo_publico()


@router.get("/convencional", response_model=PlanConvencionalListaOut)
def listar_convencional(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    turno: str | None = None,
    guardia: str | None = None,
    labor: str | None = None,
    tarea: str | None = None,
    maestro: str | None = None,
    limit: int = Query(500, ge=1, le=2000),
):
    _rango(fecha_desde, fecha_hasta)
    query = db.query(PlanConvencional).filter(PlanConvencional.usuario_id == user.id)
    if fecha_desde:
        query = query.filter(PlanConvencional.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(PlanConvencional.fecha <= fecha_hasta)
    if turno:
        query = query.filter(PlanConvencional.turno == _turno(turno))
    if guardia:
        query = query.filter(PlanConvencional.guardia == guardia.strip().upper())
    if labor:
        query = query.filter(PlanConvencional.labor_codigo == labor.strip().upper())
    if tarea:
        query = query.filter(PlanConvencional.tarea_codigo == tarea.strip().upper())
    if maestro:
        query = query.filter(PlanConvencional.maestro == " ".join(maestro.split()))
    cantidad, pies, disparados, avance, oxidos, sulfuros = query.with_entities(
        func.count(PlanConvencional.id),
        func.coalesce(func.sum(PlanConvencional.pies_perforados), 0),
        func.coalesce(func.sum(PlanConvencional.taladros_disparados), 0),
        func.coalesce(func.sum(PlanConvencional.avance_ml), 0),
        func.coalesce(func.sum(PlanConvencional.tn_oxidos), 0),
        func.coalesce(func.sum(PlanConvencional.tn_sulfuros), 0),
    ).one()
    filas = (
        query.order_by(PlanConvencional.fecha.desc(), PlanConvencional.turno.desc(), PlanConvencional.id.desc())
        .limit(limit)
        .all()
    )
    return PlanConvencionalListaOut(
        registros=[_out_conv(r) for r in filas],
        cantidad=int(cantidad),
        pies_perforados=_dec(pies),
        taladros_disparados=int(disparados),
        avance_ml=_dec(avance),
        toneladas=_dec(Decimal(str(oxidos)) + Decimal(str(sulfuros))),
    )


@router.get("/convencional/{reg_id}", response_model=PlanConvencionalOut)
def obtener_convencional(
    reg_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return _out_conv(_conv_owned(db, user, reg_id))


@router.post("/convencional", response_model=PlanConvencionalOut, status_code=201)
def crear_convencional(
    payload: PlanConvencionalIn,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    reg = PlanConvencional(usuario_id=user.id)
    _aplicar_conv(reg, payload)
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return _out_conv(reg)


@router.put("/convencional/{reg_id}", response_model=PlanConvencionalOut)
def actualizar_convencional(
    reg_id: int,
    payload: PlanConvencionalIn,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    reg = _conv_owned(db, user, reg_id)
    _aplicar_conv(reg, payload)
    db.commit()
    db.refresh(reg)
    return _out_conv(reg)


@router.delete("/convencional/{reg_id}")
def eliminar_convencional(
    reg_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    db.delete(_conv_owned(db, user, reg_id))
    db.commit()
    return {"ok": True}


# ---------- Equipos ----------


def _aplicar_equipo(reg: PlanEquipo, payload: PlanEquipoIn) -> None:
    maquina = _elegir(payload.maquina_codigo, MAQUINAS_POR_CODIGO, "El código de máquina")
    inicial = _dec(payload.horometro_inicial)
    final = _dec(payload.horometro_final)
    if inicial is not None and final is not None and final < inicial:
        raise HTTPException(status_code=400, detail="El horómetro final no puede ser menor que el inicial")
    reg.fecha = payload.fecha
    reg.turno = _turno(payload.turno)
    reg.maquina_codigo = maquina["codigo"]
    reg.equipo = maquina["equipo"]
    reg.marca = maquina["marca"]
    reg.modelo = maquina["modelo"]
    reg.horometro_inicial = inicial
    reg.horometro_final = final
    reg.horas_trabajadas = final - inicial if inicial is not None and final is not None else None
    reg.petroleo_gl = _dec(payload.petroleo_gl)


def _equipo_owned(db: Session, user: Usuario, reg_id: int) -> PlanEquipo:
    reg = db.query(PlanEquipo).filter(PlanEquipo.id == reg_id, PlanEquipo.usuario_id == user.id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return reg


@router.get("/equipos", response_model=PlanEquipoListaOut)
def listar_equipos(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    turno: str | None = None,
    maquina: str | None = None,
    limit: int = Query(500, ge=1, le=2000),
):
    _rango(fecha_desde, fecha_hasta)
    query = db.query(PlanEquipo).filter(PlanEquipo.usuario_id == user.id)
    if fecha_desde:
        query = query.filter(PlanEquipo.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(PlanEquipo.fecha <= fecha_hasta)
    if turno:
        query = query.filter(PlanEquipo.turno == _turno(turno))
    if maquina:
        query = query.filter(PlanEquipo.maquina_codigo == maquina.strip().upper())
    cantidad, horas, petroleo = query.with_entities(
        func.count(PlanEquipo.id),
        func.coalesce(func.sum(PlanEquipo.horas_trabajadas), 0),
        func.coalesce(func.sum(PlanEquipo.petroleo_gl), 0),
    ).one()
    filas = (
        query.order_by(PlanEquipo.fecha.desc(), PlanEquipo.turno.desc(), PlanEquipo.id.desc()).limit(limit).all()
    )
    return PlanEquipoListaOut(
        registros=[PlanEquipoOut.model_validate(r) for r in filas],
        cantidad=int(cantidad),
        horas_trabajadas=_dec(horas),
        petroleo_gl=_dec(petroleo),
    )


@router.get("/equipos/ultimos")
def ultimos_horometros(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Último horómetro final de cada máquina: el inicial del siguiente turno, como en el Excel."""
    salida: dict[str, float] = {}
    for codigo in MAQUINAS_POR_CODIGO:
        ultimo = (
            db.query(PlanEquipo.horometro_final)
            .filter(
                PlanEquipo.usuario_id == user.id,
                PlanEquipo.maquina_codigo == codigo,
                PlanEquipo.horometro_final.isnot(None),
            )
            .order_by(PlanEquipo.fecha.desc(), PlanEquipo.turno.desc(), PlanEquipo.id.desc())
            .first()
        )
        if ultimo:
            salida[codigo] = float(ultimo[0])
    return salida


@router.post("/equipos", response_model=PlanEquipoOut, status_code=201)
def crear_equipo(
    payload: PlanEquipoIn,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    reg = PlanEquipo(usuario_id=user.id)
    _aplicar_equipo(reg, payload)
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return PlanEquipoOut.model_validate(reg)


@router.put("/equipos/{reg_id}", response_model=PlanEquipoOut)
def actualizar_equipo(
    reg_id: int,
    payload: PlanEquipoIn,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    reg = _equipo_owned(db, user, reg_id)
    _aplicar_equipo(reg, payload)
    db.commit()
    db.refresh(reg)
    return PlanEquipoOut.model_validate(reg)


@router.delete("/equipos/{reg_id}")
def eliminar_equipo(
    reg_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    db.delete(_equipo_owned(db, user, reg_id))
    db.commit()
    return {"ok": True}
