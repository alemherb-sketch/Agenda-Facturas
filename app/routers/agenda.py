from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Agenda, Usuario
from app.schemas import AgendaCreate, AgendaOut, AgendaUpdate

router = APIRouter(prefix="/api/agenda", tags=["agenda"])


def _get_owned(db: Session, user: Usuario, agenda_id: int) -> Agenda:
    item = db.query(Agenda).filter(Agenda.id == agenda_id, Agenda.usuario_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Evento de agenda no encontrado")
    return item


@router.get("", response_model=list[AgendaOut])
def listar(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    desde: date | None = None,
    hasta: date | None = None,
    tipo: str | None = None,
    pendientes: bool = False,
    limit: int = Query(200, le=500),
):
    query = db.query(Agenda).filter(Agenda.usuario_id == user.id).order_by(Agenda.fecha_inicio.asc())
    if desde:
        query = query.filter(Agenda.fecha_inicio >= datetime.combine(desde, datetime.min.time()))
    if hasta:
        query = query.filter(Agenda.fecha_inicio <= datetime.combine(hasta, datetime.max.time()))
    if tipo:
        query = query.filter(Agenda.tipo == tipo)
    if pendientes:
        query = query.filter(Agenda.completado.is_(False), Agenda.fecha_inicio >= datetime.utcnow())
    return query.limit(limit).all()


@router.post("", response_model=AgendaOut, status_code=201)
def crear(
    payload: AgendaCreate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    item = Agenda(usuario_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{agenda_id}", response_model=AgendaOut)
def obtener(
    agenda_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return _get_owned(db, user, agenda_id)


@router.put("/{agenda_id}", response_model=AgendaOut)
def actualizar(
    agenda_id: int,
    payload: AgendaUpdate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    item = _get_owned(db, user, agenda_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
        if key in {"fecha_inicio", "recordatorio_minutos"}:
            item.notificado = False
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{agenda_id}")
def eliminar(
    agenda_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    item = _get_owned(db, user, agenda_id)
    db.delete(item)
    db.commit()
    return {"ok": True}
