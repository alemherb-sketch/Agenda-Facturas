import json
import re
import unicodedata
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import ReporteOperativo, Usuario
from app.schemas import ReporteIn, ReporteOut, ReporteUpdate
from app.services.reportes_datos import faltantes, limpiar_datos, resumen
from app.services.reportes_formatos import FORMATOS_POR_ID, formatos_publicos, numero_display
from app.services.reportes_pdf import generar_pdf_reporte

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


def _formato(formato_id: str) -> dict:
    formato = FORMATOS_POR_ID.get(formato_id)
    if not formato:
        raise HTTPException(status_code=404, detail="Formato de reporte no encontrado")
    return formato


def _get_owned(db: Session, user: Usuario, reporte_id: int) -> ReporteOperativo:
    rep = (
        db.query(ReporteOperativo)
        .filter(ReporteOperativo.id == reporte_id, ReporteOperativo.usuario_id == user.id)
        .first()
    )
    if not rep:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return rep


def _datos(rep: ReporteOperativo) -> dict:
    try:
        valor = json.loads(rep.datos or "{}")
    except ValueError:
        return {}
    return valor if isinstance(valor, dict) else {}


def _out(rep: ReporteOperativo, *, con_datos: bool = True) -> ReporteOut:
    formato = FORMATOS_POR_ID.get(rep.formato) or {"titulo": rep.formato, "prefijo": "", "digitos": 1}
    return ReporteOut(
        id=rep.id,
        formato=rep.formato,
        formato_titulo=formato["titulo"],
        numero=rep.numero,
        numero_display=numero_display(formato, rep.numero),
        fecha=rep.fecha,
        turno=rep.turno,
        equipo=rep.equipo,
        responsable=rep.responsable,
        datos=_datos(rep) if con_datos else None,
        creado_en=rep.creado_en,
        actualizado_en=rep.actualizado_en,
    )


def _siguiente(db: Session, user: Usuario, formato: dict) -> int:
    maximo = (
        db.query(func.max(ReporteOperativo.numero))
        .filter(ReporteOperativo.usuario_id == user.id, ReporteOperativo.formato == formato["id"])
        .scalar()
    )
    return max(int(maximo or 0) + 1, formato["inicio"])


def _numero_libre(db: Session, user: Usuario, formato: dict, numero: int, excluir_id: int | None = None) -> None:
    q = db.query(ReporteOperativo.id).filter(
        ReporteOperativo.usuario_id == user.id,
        ReporteOperativo.formato == formato["id"],
        ReporteOperativo.numero == numero,
    )
    if excluir_id:
        q = q.filter(ReporteOperativo.id != excluir_id)
    if q.first():
        raise HTTPException(
            status_code=400,
            detail=f"El N° {numero_display(formato, numero)} ya está registrado",
        )


def _aplicar(rep: ReporteOperativo, formato: dict, datos_in: dict) -> None:
    datos = limpiar_datos(formato, datos_in)
    pendientes = faltantes(formato, datos)
    if pendientes:
        raise HTTPException(status_code=400, detail=f"Complete: {', '.join(pendientes)}")
    info = resumen(formato, datos)
    rep.fecha = date.fromisoformat(datos["fecha"])
    rep.turno = info["turno"]
    rep.equipo = info["equipo"]
    rep.responsable = info["responsable"]
    rep.datos = json.dumps(datos, ensure_ascii=False)


def _guardar(db: Session, rep: ReporteOperativo) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Ese número de reporte ya está registrado")
    db.refresh(rep)


@router.get("/formatos")
def listar_formatos(user: Annotated[Usuario, Depends(get_current_user)]):
    return formatos_publicos()


@router.get("/conteo")
def conteo(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    rows = (
        db.query(ReporteOperativo.formato, func.count(ReporteOperativo.id))
        .filter(ReporteOperativo.usuario_id == user.id)
        .group_by(ReporteOperativo.formato)
        .all()
    )
    return {formato: int(n) for formato, n in rows}


@router.get("/siguiente")
def siguiente_numero(
    formato: str,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    fmt = _formato(formato)
    numero = _siguiente(db, user, fmt)
    return {"numero": numero, "numero_display": numero_display(fmt, numero)}


@router.get("/ultimo", response_model=ReporteOut | None)
def ultimo(
    formato: str,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _formato(formato)
    rep = (
        db.query(ReporteOperativo)
        .filter(ReporteOperativo.usuario_id == user.id, ReporteOperativo.formato == formato)
        .order_by(ReporteOperativo.id.desc())
        .first()
    )
    return _out(rep) if rep else None


@router.get("", response_model=list[ReporteOut])
def listar(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    formato: str | None = None,
    q: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    limit: int = Query(300, le=1000),
):
    query = db.query(ReporteOperativo).filter(ReporteOperativo.usuario_id == user.id)
    if formato:
        query = query.filter(ReporteOperativo.formato == formato)
    if fecha_desde:
        query = query.filter(ReporteOperativo.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(ReporteOperativo.fecha <= fecha_hasta)
    if q and q.strip():
        texto = q.strip()
        like = f"%{texto}%"
        filtros = [
            ReporteOperativo.equipo.ilike(like),
            ReporteOperativo.responsable.ilike(like),
            ReporteOperativo.turno.ilike(like),
        ]
        digitos = "".join(ch for ch in texto if ch.isdigit())
        if digitos:
            filtros.append(ReporteOperativo.numero == int(digitos[-9:]))
        query = query.filter(or_(*filtros))
    rows = (
        query.order_by(ReporteOperativo.fecha.desc(), ReporteOperativo.id.desc()).limit(limit).all()
    )
    return [_out(r, con_datos=False) for r in rows]


@router.get("/{reporte_id}", response_model=ReporteOut)
def obtener(
    reporte_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return _out(_get_owned(db, user, reporte_id))


@router.post("", response_model=ReporteOut, status_code=201)
def crear(
    payload: ReporteIn,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    formato = _formato(payload.formato)
    numero = payload.numero or _siguiente(db, user, formato)
    _numero_libre(db, user, formato, numero)
    rep = ReporteOperativo(usuario_id=user.id, formato=formato["id"], numero=numero)
    _aplicar(rep, formato, payload.datos)
    db.add(rep)
    _guardar(db, rep)
    return _out(rep)


@router.put("/{reporte_id}", response_model=ReporteOut)
def actualizar(
    reporte_id: int,
    payload: ReporteUpdate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    rep = _get_owned(db, user, reporte_id)
    formato = _formato(rep.formato)
    if payload.numero and payload.numero != rep.numero:
        _numero_libre(db, user, formato, payload.numero, excluir_id=rep.id)
        rep.numero = payload.numero
    if payload.datos is not None:
        _aplicar(rep, formato, payload.datos)
    _guardar(db, rep)
    return _out(rep)


@router.post("/{reporte_id}/duplicar", response_model=ReporteOut, status_code=201)
def duplicar(
    reporte_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    original = _get_owned(db, user, reporte_id)
    formato = _formato(original.formato)
    datos = _datos(original)
    datos["fecha"] = date.today().isoformat()
    copia = ReporteOperativo(
        usuario_id=user.id, formato=formato["id"], numero=_siguiente(db, user, formato)
    )
    _aplicar(copia, formato, datos)
    db.add(copia)
    _guardar(db, copia)
    return _out(copia)


@router.get("/{reporte_id}/pdf")
def pdf(
    reporte_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    rep = _get_owned(db, user, reporte_id)
    formato = _formato(rep.formato)
    contenido = generar_pdf_reporte(formato, numero_display(formato, rep.numero), _datos(rep))
    ascii_nombre = unicodedata.normalize("NFKD", numero_display(formato, rep.numero)).encode("ascii", "ignore").decode()
    nombre = re.sub(r"[^A-Za-z0-9-]+", "", ascii_nombre) or f"reporte-{rep.id}"
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre}.pdf"'},
    )


@router.delete("/{reporte_id}")
def eliminar(
    reporte_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    rep = _get_owned(db, user, reporte_id)
    db.delete(rep)
    db.commit()
    return {"ok": True}
