from decimal import Decimal, ROUND_HALF_UP

from app.models import TipoDocumento
from app.schemas import ItemCreate

IGV_RATE = Decimal("0.18")

TIPOS_CON_IGV = {
    TipoDocumento.FACTURA,
    TipoDocumento.BOLETA,
    TipoDocumento.NOTA_CREDITO,
    TipoDocumento.NOTA_DEBITO,
    TipoDocumento.TICKET,
}


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_totales(tipo: TipoDocumento, items: list[ItemCreate]) -> tuple[list[dict], Decimal, Decimal, Decimal]:
    detalle = []
    base = Decimal("0.00")
    for item in items:
        subtotal = money(item.cantidad * item.precio_unitario)
        base += subtotal
        detalle.append(
            {
                "descripcion": item.descripcion,
                "cantidad": item.cantidad,
                "precio_unitario": money(item.precio_unitario),
                "subtotal": subtotal,
                "unidad": item.unidad,
            }
        )

    if tipo in TIPOS_CON_IGV:
        # Precios ingresados incluyen IGV (práctica común en negocio peruano)
        total = money(base)
        subtotal = money(total / (Decimal("1") + IGV_RATE))
        igv = money(total - subtotal)
    else:
        subtotal = money(base)
        igv = Decimal("0.00")
        total = subtotal

    return detalle, subtotal, igv, total


TIPO_LABELS = {
    TipoDocumento.FACTURA: "Factura Electrónica",
    TipoDocumento.BOLETA: "Boleta de Venta",
    TipoDocumento.NOTA_VENTA: "Nota de Venta",
    TipoDocumento.NOTA_CREDITO: "Nota de Crédito",
    TipoDocumento.NOTA_DEBITO: "Nota de Débito",
    TipoDocumento.RECIBO_HONORARIOS: "Recibo por Honorarios",
    TipoDocumento.GUIA_REMISION: "Guía de Remisión",
    TipoDocumento.TICKET: "Ticket / Comprobante",
}

ESTADO_LABELS = {
    "emitido": "Emitido",
    "pagado": "Pagado",
    "no_pagado": "No pagado",
    "anulado": "Anulado",
}

SERIE_SUGERIDA = {
    TipoDocumento.FACTURA: "F001",
    TipoDocumento.BOLETA: "B001",
    TipoDocumento.NOTA_VENTA: "NV01",
    TipoDocumento.NOTA_CREDITO: "FC01",
    TipoDocumento.NOTA_DEBITO: "FD01",
    TipoDocumento.RECIBO_HONORARIOS: "E001",
    TipoDocumento.GUIA_REMISION: "T001",
    TipoDocumento.TICKET: "T001",
}
