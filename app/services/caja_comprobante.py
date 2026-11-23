"""Los comprobantes no se vinculan a ninguna caja.

El arranque borra los movimientos que un comprobante hubiera generado
y deja caja_id en blanco. Los movimientos manuales de caja se conservan.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    Caja,
    Comprobante,
    EstadoComprobante,
    MovimientoCaja,
    TipoDocumento,
    TipoMovimientoCaja,
    Usuario,
)
from app.services.adjuntos import ENTIDAD_CAJA, eliminar_adjuntos_entidad
from app.services.comprobante_calc import TIPO_LABELS

_SIN_EFECTO_EN_CAJA = {TipoDocumento.COTIZACION, TipoDocumento.GUIA_REMISION}


def validar_caja(db: Session, user: Usuario, caja_id: int, *, permitir_inactiva: bool = False) -> Caja:
    caja = db.query(Caja).filter(Caja.id == caja_id, Caja.usuario_id == user.id).first()
    if not caja:
        raise HTTPException(status_code=400, detail="La caja seleccionada no existe")
    if not caja.activo and not permitir_inactiva:
        raise HTTPException(status_code=400, detail="La caja está inactiva")
    return caja


def tipo_movimiento_comprobante(doc: Comprobante) -> TipoMovimientoCaja | None:
    """Ingreso en ventas y egreso en compras. La nota de crédito invierte el sentido."""
    if doc.estado == EstadoComprobante.ANULADO or not doc.caja_id:
        return None
    if doc.tipo in _SIN_EFECTO_EN_CAJA:
        return None
    if Decimal(str(doc.total or 0)) <= 0:
        return None
    es_ingreso = (doc.operacion or "venta") != "compra"
    if doc.tipo == TipoDocumento.NOTA_CREDITO:
        es_ingreso = not es_ingreso
    return TipoMovimientoCaja.INGRESO if es_ingreso else TipoMovimientoCaja.EGRESO


def _concepto(doc: Comprobante) -> str:
    base = "Compra" if (doc.operacion or "venta") == "compra" else "Venta"
    if doc.tipo == TipoDocumento.NOTA_CREDITO:
        base = f"{base} · nota de crédito"
    elif doc.tipo == TipoDocumento.NOTA_DEBITO:
        base = f"{base} · nota de débito"
    tipo = doc.tipo if isinstance(doc.tipo, TipoDocumento) else TipoDocumento(doc.tipo)
    etiqueta = TIPO_LABELS.get(tipo, tipo.value)
    return f"{base}: {etiqueta} {doc.serie}-{doc.numero} · {doc.cliente_nombre}"[:300]


def _borrar_movimiento(db: Session, mov: MovimientoCaja) -> None:
    eliminar_adjuntos_entidad(db, ENTIDAD_CAJA, mov.id)
    db.delete(mov)
    db.flush()


def desvincular_comprobantes_de_cajas(db: Session) -> None:
    """Los comprobantes no mueven ninguna caja: se quitan sus movimientos y el vínculo."""
    movs = db.query(MovimientoCaja).filter(MovimientoCaja.comprobante_id.isnot(None)).all()
    for mov in movs:
        _borrar_movimiento(db, mov)
    db.query(Comprobante).filter(Comprobante.caja_id.isnot(None)).update(
        {Comprobante.caja_id: None}, synchronize_session=False
    )
    db.commit()


def eliminar_movimiento_comprobante(db: Session, usuario_id: int, comprobante_id: int) -> None:
    mov = (
        db.query(MovimientoCaja)
        .filter(
            MovimientoCaja.comprobante_id == comprobante_id,
            MovimientoCaja.usuario_id == usuario_id,
        )
        .first()
    )
    if mov:
        _borrar_movimiento(db, mov)


def sincronizar_movimiento_comprobante(db: Session, user: Usuario, doc: Comprobante) -> None:
    """Crea, actualiza o quita el movimiento que refleja esta venta o compra en la caja."""
    existente = (
        db.query(MovimientoCaja)
        .filter(MovimientoCaja.comprobante_id == doc.id, MovimientoCaja.usuario_id == user.id)
        .first()
    )
    tipo_mov = tipo_movimiento_comprobante(doc)
    if tipo_mov is None:
        if existente:
            _borrar_movimiento(db, existente)
        return

    caja = db.query(Caja).filter(Caja.id == doc.caja_id, Caja.usuario_id == user.id).first()
    if not caja:
        if existente:
            _borrar_movimiento(db, existente)
        return

    concepto = _concepto(doc)
    numero = f"{doc.serie}-{doc.numero}"[:80]
    if existente:
        existente.caja_id = caja.id
        existente.tipo = tipo_mov
        existente.monto = doc.total
        existente.concepto = concepto
        existente.fecha = doc.fecha_emision
        if not existente.numero_transaccion:
            existente.numero_transaccion = numero
        return

    db.add(
        MovimientoCaja(
            usuario_id=user.id,
            caja_id=caja.id,
            comprobante_id=doc.id,
            tipo=tipo_mov,
            monto=doc.total,
            metodo_pago="efectivo",
            numero_transaccion=numero,
            concepto=concepto,
            fecha=doc.fecha_emision,
        )
    )
    db.flush()
