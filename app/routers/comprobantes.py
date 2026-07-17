from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Comprobante, ComprobanteItem, Usuario
from app.schemas import (
    ComprobanteCreate,
    ComprobanteOut,
    ComprobanteUpdate,
    EmailShareIn,
    WhatsAppShareOut,
)
from app.services.catalogo import upsert_cliente, upsert_productos_desde_items
from app.services.comprobante_calc import ESTADO_LABELS, TIPO_LABELS, calcular_totales
from app.services.email_service import enviar_correo
from app.services.pdf_service import generar_pdf_comprobante

router = APIRouter(prefix="/api/comprobantes", tags=["comprobantes"])


def _get_owned(db: Session, user: Usuario, comprobante_id: int) -> Comprobante:
    doc = (
        db.query(Comprobante)
        .options(joinedload(Comprobante.items))
        .filter(Comprobante.id == comprobante_id, Comprobante.usuario_id == user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    return doc


def _aplicar_items(doc: Comprobante, payload_items, tipo) -> None:
    detalle, subtotal, igv, total = calcular_totales(tipo, payload_items)
    doc.items.clear()
    for item in detalle:
        doc.items.append(ComprobanteItem(**item))
    doc.subtotal = subtotal
    doc.igv = igv
    doc.total = total


@router.get("", response_model=list[ComprobanteOut])
def listar(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    estado: str | None = None,
    tipo: str | None = None,
    q: str | None = None,
    limit: int = Query(100, le=500),
):
    query = (
        db.query(Comprobante)
        .options(joinedload(Comprobante.items))
        .filter(Comprobante.usuario_id == user.id)
        .order_by(Comprobante.fecha_emision.desc(), Comprobante.id.desc())
    )
    if estado:
        query = query.filter(Comprobante.estado == estado)
    if tipo:
        query = query.filter(Comprobante.tipo == tipo)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Comprobante.cliente_nombre.ilike(like))
            | (Comprobante.numero.ilike(like))
            | (Comprobante.serie.ilike(like))
            | (Comprobante.cliente_documento.ilike(like))
        )
    return query.limit(limit).all()


@router.post("", response_model=ComprobanteOut, status_code=201)
def crear(
    payload: ComprobanteCreate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    cliente = upsert_cliente(
        db,
        user.id,
        nombre=payload.cliente_nombre,
        documento=payload.cliente_documento,
        email=payload.cliente_email,
        telefono=payload.cliente_telefono,
    )
    upsert_productos_desde_items(db, user.id, payload.items)

    doc = Comprobante(
        usuario_id=user.id,
        cliente_id=cliente.id,
        tipo=payload.tipo,
        serie=payload.serie.upper(),
        numero=payload.numero,
        fecha_emision=payload.fecha_emision,
        fecha_vencimiento=payload.fecha_vencimiento,
        moneda=payload.moneda,
        estado=payload.estado,
        observaciones=payload.observaciones,
        cliente_nombre=payload.cliente_nombre,
        cliente_documento=payload.cliente_documento,
    )
    db.add(doc)
    db.flush()
    _aplicar_items(doc, payload.items, payload.tipo)
    db.commit()
    db.refresh(doc)
    return _get_owned(db, user, doc.id)


@router.get("/{comprobante_id}", response_model=ComprobanteOut)
def obtener(
    comprobante_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return _get_owned(db, user, comprobante_id)


@router.put("/{comprobante_id}", response_model=ComprobanteOut)
def actualizar(
    comprobante_id: int,
    payload: ComprobanteUpdate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    doc = _get_owned(db, user, comprobante_id)
    data = payload.model_dump(exclude_unset=True)
    items = data.pop("items", None)
    for key, value in data.items():
        setattr(doc, key, value.upper() if key == "serie" and isinstance(value, str) else value)

    nombre = data.get("cliente_nombre", doc.cliente_nombre)
    documento = data.get("cliente_documento", doc.cliente_documento)
    cliente = upsert_cliente(db, user.id, nombre=nombre, documento=documento)
    doc.cliente_id = cliente.id

    if items is not None:
        upsert_productos_desde_items(db, user.id, payload.items)
        _aplicar_items(doc, payload.items, doc.tipo)
    db.commit()
    return _get_owned(db, user, doc.id)


@router.patch("/{comprobante_id}/estado", response_model=ComprobanteOut)
def cambiar_estado(
    comprobante_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    estado: str = Query(..., description="emitido|pagado|no_pagado|anulado"),
):
    """Cambio rápido de estado desde la lista de documentos."""
    from app.models import EstadoComprobante

    try:
        nuevo = EstadoComprobante(estado)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Estado no válido") from exc

    doc = _get_owned(db, user, comprobante_id)
    doc.estado = nuevo
    db.commit()
    return _get_owned(db, user, doc.id)


@router.delete("/{comprobante_id}")
def eliminar(
    comprobante_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    doc = _get_owned(db, user, comprobante_id)
    db.delete(doc)
    db.commit()
    return {"ok": True}


@router.get("/{comprobante_id}/pdf")
def descargar_pdf(
    comprobante_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    doc = _get_owned(db, user, comprobante_id)
    pdf = generar_pdf_comprobante(doc, user)
    filename = f"{doc.serie}-{doc.numero}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{comprobante_id}/enviar-correo")
async def compartir_correo(
    comprobante_id: int,
    payload: EmailShareIn,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    doc = _get_owned(db, user, comprobante_id)
    pdf = generar_pdf_comprobante(doc, user)
    tipo = TIPO_LABELS.get(doc.tipo, str(doc.tipo))
    asunto = f"{tipo} {doc.serie}-{doc.numero} — {user.razon_social or user.nombre}"
    cuerpo = (
        payload.mensaje
        or (
            f"Estimado/a {doc.cliente_nombre},\n\n"
            f"Adjunto encontrará el comprobante {tipo} {doc.serie}-{doc.numero} "
            f"por un total de S/ {float(doc.total):,.2f}.\n\n"
            f"Estado: {ESTADO_LABELS.get(doc.estado.value, doc.estado.value)}\n\n"
            f"Saludos,\n{user.razon_social or user.nombre}"
        )
    )
    ok, msg = await enviar_correo(
        payload.email,
        asunto,
        cuerpo,
        adjunto_nombre=f"{doc.serie}-{doc.numero}.pdf",
        adjunto_bytes=pdf,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "mensaje": msg}


@router.get("/{comprobante_id}/whatsapp", response_model=WhatsAppShareOut)
def compartir_whatsapp(
    comprobante_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    telefono: str | None = None,
):
    doc = _get_owned(db, user, comprobante_id)
    tipo = TIPO_LABELS.get(doc.tipo, str(doc.tipo))
    mensaje = (
        f"Hola {doc.cliente_nombre}, le comparto el comprobante *{tipo} {doc.serie}-{doc.numero}* "
        f"por *S/ {float(doc.total):,.2f}* "
        f"(estado: {ESTADO_LABELS.get(doc.estado.value, doc.estado.value)}). "
        f"Emisor: {user.razon_social or user.nombre}."
    )
    phone = "".join(c for c in (telefono or "") if c.isdigit())
    if phone and not phone.startswith("51") and len(phone) == 9:
        phone = f"51{phone}"
    base = f"https://wa.me/{phone}" if phone else "https://wa.me/"
    url = f"{base}?text={quote(mensaje)}"
    return WhatsAppShareOut(url=url, mensaje=mensaje)
