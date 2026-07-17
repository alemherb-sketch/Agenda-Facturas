from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Agenda, Comprobante, EstadoComprobante, Usuario
from app.schemas import ComprobanteOut, DashboardOut
from app.services.comprobante_calc import TIPO_LABELS

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def resumen(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    docs = (
        db.query(Comprobante)
        .options(joinedload(Comprobante.items))
        .filter(Comprobante.usuario_id == user.id)
        .all()
    )

    total_facturado = Decimal("0")
    total_cobrado = Decimal("0")
    total_pendiente = Decimal("0")
    total_anulado = Decimal("0")
    por_estado: dict[str, int] = defaultdict(int)
    por_tipo: dict[str, int] = defaultdict(int)
    por_mes_map: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for doc in docs:
        por_estado[doc.estado.value] += 1
        por_tipo[TIPO_LABELS.get(doc.tipo, doc.tipo.value)] += 1
        if doc.estado != EstadoComprobante.ANULADO:
            total_facturado += doc.total
            key = doc.fecha_emision.strftime("%Y-%m")
            por_mes_map[key] += doc.total
        if doc.estado == EstadoComprobante.PAGADO:
            total_cobrado += doc.total
        elif doc.estado in {EstadoComprobante.NO_PAGADO, EstadoComprobante.EMITIDO}:
            total_pendiente += doc.total
        elif doc.estado == EstadoComprobante.ANULADO:
            total_anulado += doc.total

    hoy = date.today()
    inicio_hoy = datetime.combine(hoy, datetime.min.time())
    fin_hoy = datetime.combine(hoy, datetime.max.time())
    proximos_7 = datetime.utcnow() + timedelta(days=7)

    agendas_hoy = (
        db.query(func.count(Agenda.id))
        .filter(
            Agenda.usuario_id == user.id,
            Agenda.fecha_inicio >= inicio_hoy,
            Agenda.fecha_inicio <= fin_hoy,
        )
        .scalar()
        or 0
    )
    agendas_proximas = (
        db.query(func.count(Agenda.id))
        .filter(
            Agenda.usuario_id == user.id,
            Agenda.completado.is_(False),
            Agenda.fecha_inicio >= datetime.utcnow(),
            Agenda.fecha_inicio <= proximos_7,
        )
        .scalar()
        or 0
    )
    documentos_vencidos = (
        db.query(func.count(Comprobante.id))
        .filter(
            Comprobante.usuario_id == user.id,
            Comprobante.estado == EstadoComprobante.NO_PAGADO,
            Comprobante.fecha_vencimiento.is_not(None),
            Comprobante.fecha_vencimiento < hoy,
        )
        .scalar()
        or 0
    )

    recientes = sorted(docs, key=lambda d: (d.fecha_emision, d.id), reverse=True)[:8]
    por_mes = [
        {"mes": k, "total": float(v)}
        for k, v in sorted(por_mes_map.items())[-12:]
    ]

    return DashboardOut(
        total_comprobantes=len(docs),
        total_facturado=total_facturado,
        total_cobrado=total_cobrado,
        total_pendiente=total_pendiente,
        total_anulado=total_anulado,
        por_estado=dict(por_estado),
        por_tipo=dict(por_tipo),
        por_mes=por_mes,
        agendas_proximas=agendas_proximas,
        agendas_hoy=agendas_hoy,
        documentos_vencidos=documentos_vencidos,
        recientes=[ComprobanteOut.model_validate(r) for r in recientes],
    )
