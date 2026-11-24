from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Agenda, Comprobante, EstadoComprobante, Usuario
from app.schemas import ComprobanteOut, DashboardOut
from app.services.caja_comprobante import suma_egresos_comprobantes
from app.services.comprobante_calc import TIPO_LABELS

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _grupos_dashboard(mapa: dict[str, dict]) -> list[dict]:
    filas = [(nombre, vals["cantidad"], vals["total"]) for nombre, vals in mapa.items()]
    filas.sort(key=lambda fila: (fila[2], fila[1], fila[0].lower()), reverse=True)
    base = sum((total for _, _, total in filas), Decimal("0"))
    base_cant = sum(cantidad for _, cantidad, _ in filas)
    grupos = []
    for nombre, cantidad, total in filas:
        if base:
            pct = total / base * Decimal("100")
        elif base_cant:
            pct = Decimal(cantidad) / Decimal(base_cant) * Decimal("100")
        else:
            pct = Decimal("0")
        grupos.append(
            {
                "nombre": nombre,
                "cantidad": int(cantidad),
                "total": float(total),
                "porcentaje": float(round(pct, 1)),
            }
        )
    return grupos


def _doc_en_filtro(
    doc: Comprobante,
    *,
    fecha_desde: date | None,
    fecha_hasta: date | None,
    estado: str | None,
    tipo: str | None,
    zona: str | None,
    cliente: str | None,
) -> bool:
    if fecha_desde and doc.fecha_emision < fecha_desde:
        return False
    if fecha_hasta and doc.fecha_emision > fecha_hasta:
        return False
    if estado and doc.estado.value != estado:
        return False
    if tipo and doc.tipo.value != tipo:
        return False
    if zona and (doc.zona or "") != zona:
        return False
    if cliente and cliente.casefold() not in (doc.cliente_nombre or "").casefold():
        return False
    return True


@router.get("", response_model=DashboardOut)
def resumen(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    estado: str | None = None,
    tipo: str | None = None,
    zona: str | None = None,
    cliente: str | None = None,
):
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(status_code=400, detail="La fecha desde no puede ser mayor a la fecha hasta")
    cliente = (cliente or "").strip() or None
    zona = (zona or "").strip() or None
    estado = (estado or "").strip() or None
    tipo = (tipo or "").strip() or None
    docs = (
        db.query(Comprobante)
        .options(joinedload(Comprobante.items))
        .filter(Comprobante.usuario_id == user.id)
        .all()
    )
    docs = [
        doc
        for doc in docs
        if _doc_en_filtro(
            doc,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            estado=estado,
            tipo=tipo,
            zona=zona,
            cliente=cliente,
        )
    ]

    total_facturado = Decimal("0")
    total_cobrado = Decimal("0")
    total_pendiente = Decimal("0")
    total_anulado = Decimal("0")
    por_estado: dict[str, int] = defaultdict(int)
    por_tipo: dict[str, int] = defaultdict(int)
    por_mes_map: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    por_cliente_map: dict[str, dict] = defaultdict(lambda: {"cantidad": 0, "total": Decimal("0")})
    por_zona_map: dict[str, dict] = defaultdict(lambda: {"cantidad": 0, "total": Decimal("0")})

    for doc in docs:
        por_estado[doc.estado.value] += 1
        por_tipo[TIPO_LABELS.get(doc.tipo, doc.tipo.value)] += 1
        # El facturado del panel sigue siendo de ventas.
        if (doc.operacion or "venta") == "compra":
            continue
        if doc.estado != EstadoComprobante.ANULADO:
            total_facturado += doc.total
            key = doc.fecha_emision.strftime("%Y-%m")
            por_mes_map[key] += doc.total
            cliente = (doc.cliente_nombre or "").strip() or "Sin cliente"
            zona = (doc.zona or "").strip() or "Sin zona"
            por_cliente_map[cliente]["cantidad"] += 1
            por_cliente_map[cliente]["total"] += doc.total
            por_zona_map[zona]["cantidad"] += 1
            por_zona_map[zona]["total"] += doc.total
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
    documentos_vencidos = sum(
        1
        for doc in docs
        if (doc.operacion or "venta") != "compra"
        and doc.estado == EstadoComprobante.NO_PAGADO
        and doc.fecha_vencimiento is not None
        and doc.fecha_vencimiento < hoy
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
        por_cliente=_grupos_dashboard(por_cliente_map),
        por_zona=_grupos_dashboard(por_zona_map),
        agendas_proximas=agendas_proximas,
        agendas_hoy=agendas_hoy,
        documentos_vencidos=documentos_vencidos,
        total_egresos_comprobantes=suma_egresos_comprobantes(db, user.id),
        recientes=[ComprobanteOut.model_validate(r) for r in recientes],
    )
