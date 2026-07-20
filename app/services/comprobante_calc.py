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


def tipo_permite_igv(tipo: TipoDocumento) -> bool:
    return tipo in TIPOS_CON_IGV


def calcular_totales(tipo: TipoDocumento, items: list[ItemCreate]) -> tuple[list[dict], Decimal, Decimal, Decimal]:
    """
    Precios con IGV: si el ítem tiene aplica_igv=True, el importe de línea incluye IGV 18%.
    Ítems sin IGV se suman como operación inafecta/exonerada.
    """
    detalle = []
    gravado_inc = Decimal("0.00")
    sin_igv = Decimal("0.00")
    permite = tipo_permite_igv(tipo)

    for item in items:
        line_total = money(item.cantidad * item.precio_unitario)
        aplica = bool(getattr(item, "aplica_igv", True)) and permite
        detalle.append(
            {
                "descripcion": item.descripcion,
                "cantidad": item.cantidad,
                "precio_unitario": money(item.precio_unitario),
                "subtotal": line_total,
                "unidad": item.unidad,
                "aplica_igv": aplica,
            }
        )
        if aplica:
            gravado_inc += line_total
        else:
            sin_igv += line_total

    if permite and gravado_inc > 0:
        base_gravada = money(gravado_inc / (Decimal("1") + IGV_RATE))
        igv = money(gravado_inc - base_gravada)
        subtotal = money(base_gravada + sin_igv)
        total = money(gravado_inc + sin_igv)
    else:
        subtotal = money(gravado_inc + sin_igv)
        igv = Decimal("0.00")
        total = subtotal

    return detalle, subtotal, igv, total


TIPO_LABELS = {
    TipoDocumento.FACTURA: "Factura Electrónica",
    TipoDocumento.BOLETA: "Boleta de Venta",
    TipoDocumento.NOTA_VENTA: "Nota de Venta",
    TipoDocumento.COTIZACION: "Cotización",
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
    TipoDocumento.COTIZACION: "CT01",
    TipoDocumento.NOTA_CREDITO: "FC01",
    TipoDocumento.NOTA_DEBITO: "FD01",
    TipoDocumento.RECIBO_HONORARIOS: "E001",
    TipoDocumento.GUIA_REMISION: "T001",
    TipoDocumento.TICKET: "T001",
}
