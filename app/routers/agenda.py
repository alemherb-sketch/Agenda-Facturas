from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Agenda, EstadoAgenda, Usuario
from app.schemas import (
    AdjuntoOut,
    AgendaCreate,
    AgendaOut,
    AgendaReprogramarIn,
    AgendaUpdate,
)
from app.services.adjuntos import (
    ENTIDAD_AGENDA,
    crear_adjunto,
    eliminar_adjuntos_entidad,
    listar_adjuntos,
    map_adjuntos_por_entidad,
)
from app.services.pdf_service import generar_pdf_agenda

router = APIRouter(prefix="/api/agenda", tags=["agenda"])


def _sync_completado(item: Agenda) -> None:
    """Mantiene completado alineado con estado (recordatorios usan completado)."""
    estado = item.estado
    if isinstance(estado, str):
        try:
            estado = EstadoAgenda(estado)
        except ValueError:
            estado = EstadoAgenda.PROGRAMADO
            item.estado = estado
    item.completado = estado in (EstadoAgenda.FINALIZADO, EstadoAgenda.ANULADO)


def _get_owned(db: Session, user: Usuario, agenda_id: int) -> Agenda:
    item = db.query(Agenda).filter(Agenda.id == agenda_id, Agenda.usuario_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Evento de agenda no encontrado")
    return item


def _agenda_out(item: Agenda, adjuntos_rows=None) -> AgendaOut:
    rows = adjuntos_rows if adjuntos_rows is not None else []
    # Compat: filas sin estado (legado)
    if not getattr(item, "estado", None):
        item.estado = EstadoAgenda.FINALIZADO if item.completado else EstadoAgenda.PROGRAMADO
    out = AgendaOut.model_validate(item)
    out.adjuntos = [AdjuntoOut.from_row(r) for r in rows]
    out.tiene_adjunto = bool(out.adjuntos)
    return out


def _agenda_out_db(db: Session, item: Agenda) -> AgendaOut:
    return _agenda_out(item, listar_adjuntos(db, ENTIDAD_AGENDA, item.id))


@router.get("", response_model=list[AgendaOut])
def listar(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    desde: date | None = None,
    hasta: date | None = None,
    tipo: str | None = None,
    estado: str | None = None,
    pendientes: bool = False,
    limit: int = Query(200, le=500),
):
    query = db.query(Agenda).filter(Agenda.usuario_id == user.id).order_by(Agenda.fecha_inicio.desc())
    if desde:
        query = query.filter(Agenda.fecha_inicio >= datetime.combine(desde, datetime.min.time()))
    if hasta:
        query = query.filter(Agenda.fecha_inicio <= datetime.combine(hasta, datetime.max.time()))
    if tipo:
        query = query.filter(Agenda.tipo == tipo)
    if estado:
        query = query.filter(Agenda.estado == estado)
    if pendientes:
        query = query.filter(
            Agenda.estado == EstadoAgenda.PROGRAMADO,
            Agenda.completado.is_(False),
            Agenda.fecha_inicio >= datetime.utcnow(),
        )
    items = query.limit(limit).all()
    by_adj = map_adjuntos_por_entidad(db, ENTIDAD_AGENDA, [i.id for i in items])
    return [_agenda_out(i, by_adj.get(i.id, [])) for i in items]


@router.post("", response_model=AgendaOut, status_code=201)
def crear(
    payload: AgendaCreate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    data = payload.model_dump()
    item = Agenda(usuario_id=user.id, **data)
    _sync_completado(item)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _agenda_out_db(db, item)


@router.get("/{agenda_id}", response_model=AgendaOut)
def obtener(
    agenda_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return _agenda_out_db(db, _get_owned(db, user, agenda_id))


@router.put("/{agenda_id}", response_model=AgendaOut)
def actualizar(
    agenda_id: int,
    payload: AgendaUpdate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    item = _get_owned(db, user, agenda_id)
    data = payload.model_dump(exclude_unset=True)
    # Compat: si solo envían completado
    if "completado" in data and "estado" not in data:
        data["estado"] = (
            EstadoAgenda.FINALIZADO if data["completado"] else EstadoAgenda.PROGRAMADO
        )
    for key, value in data.items():
        if key == "completado":
            continue
        setattr(item, key, value)
        if key in {"fecha_inicio", "recordatorio_minutos"}:
            item.notificado = False
    _sync_completado(item)
    db.commit()
    db.refresh(item)
    return _agenda_out_db(db, item)


@router.patch("/{agenda_id}/estado", response_model=AgendaOut)
def cambiar_estado(
    agenda_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    estado: EstadoAgenda = Query(...),
):
    item = _get_owned(db, user, agenda_id)
    item.estado = estado
    _sync_completado(item)
    db.commit()
    db.refresh(item)
    return _agenda_out_db(db, item)


@router.post("/{agenda_id}/reprogramar", response_model=AgendaOut)
def reprogramar(
    agenda_id: int,
    payload: AgendaReprogramarIn,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    item = _get_owned(db, user, agenda_id)
    if item.estado == EstadoAgenda.ANULADO:
        raise HTTPException(status_code=400, detail="No se puede reprogramar una agenda anulada")
    item.fecha_inicio = payload.fecha_inicio
    if payload.fecha_fin is not None:
        item.fecha_fin = payload.fecha_fin
    elif item.fecha_fin and item.fecha_fin < payload.fecha_inicio:
        item.fecha_fin = None
    item.estado = EstadoAgenda.PROGRAMADO
    item.notificado = False
    _sync_completado(item)
    db.commit()
    db.refresh(item)
    return _agenda_out_db(db, item)


@router.get("/{agenda_id}/pdf")
def pdf_agenda(
    agenda_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    item = _get_owned(db, user, agenda_id)
    pdf = generar_pdf_agenda(item, user)
    nombre = f"agenda-{item.id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nombre}"'},
    )


@router.post("/{agenda_id}/adjuntos", response_model=AgendaOut)
async def subir_adjuntos(
    agenda_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    archivos: list[UploadFile] = File(...),
):
    item = _get_owned(db, user, agenda_id)
    if not archivos:
        raise HTTPException(status_code=400, detail="Seleccione al menos un archivo")
    for archivo in archivos:
        await crear_adjunto(
            db,
            user=user,
            entidad_tipo=ENTIDAD_AGENDA,
            entidad_id=item.id,
            kind="agendas",
            archivo=archivo,
        )
    return _agenda_out_db(db, _get_owned(db, user, item.id))


@router.get("/{agenda_id}/adjuntos", response_model=list[AdjuntoOut])
def listar_adjuntos_agenda(
    agenda_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _get_owned(db, user, agenda_id)
    return [AdjuntoOut.from_row(r) for r in listar_adjuntos(db, ENTIDAD_AGENDA, agenda_id)]


@router.delete("/{agenda_id}")
def eliminar(
    agenda_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    item = _get_owned(db, user, agenda_id)
    eliminar_adjuntos_entidad(db, ENTIDAD_AGENDA, item.id)
    db.delete(item)
    db.commit()
    return {"ok": True}
