from io import BytesIO
from datetime import date, datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Comprobante, MovimientoCaja, Usuario
from app.services.comprobante_calc import ESTADO_LABELS, TIPO_LABELS

# Datos fijos de empresa para todos los formatos de impresión
EMPRESA_RAZON = "JAELIN E.I.R.L."
EMPRESA_RUC = "20605739041"
EMPRESA_DIRECCION = (
    "CAL.LOS GIRASOLES NRO. 174 URB. LOS MANGUITOS "
    "LA LIBERTAD - TRUJILLO - VICTOR LARCO HERRERA"
)
LOGO_PATH = Path(__file__).resolve().parent.parent / "static" / "img" / "logo-jaelin.png"
# Solo el isotipo (sin texto JAELIN) para alinear con razón social / RUC / dirección
LOGO_MARK_PATH = Path(__file__).resolve().parent.parent / "static" / "img" / "logo-jaelin-mark.png"


def _styles():
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitlePE",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=colors.HexColor("#0f3d2e"),
        leading=15,
        spaceBefore=0,
        spaceAfter=0,
    )
    normal = ParagraphStyle(
        "NormalPE",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        spaceBefore=0,
        spaceAfter=0,
    )
    small = ParagraphStyle(
        "SmallPE",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#5b6b62"),
        leading=10,
        spaceBefore=0,
        spaceAfter=0,
    )
    subtitle = ParagraphStyle(
        "SubtitlePE",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#b45309"),
        spaceBefore=4,
        spaceAfter=6,
    )
    return title_style, normal, small, subtitle


class EmpresaHeader(Flowable):
    """Isotipo + razón social / RUC / dirección con la misma altura (base y tope alineados)."""

    def __init__(self):
        super().__init__()
        title_style, normal, small, _ = _styles()
        self._razon = Paragraph(EMPRESA_RAZON, title_style)
        self._ruc = Paragraph(f"RUC: {EMPRESA_RUC}", normal)
        self._dir = Paragraph(EMPRESA_DIRECCION, small)
        self._logo = LOGO_MARK_PATH if LOGO_MARK_PATH.exists() else LOGO_PATH
        self._has_logo = self._logo.exists()
        self._logo_aspect = 1.0
        if self._has_logo:
            logo_w_px, logo_h_px = ImageReader(str(self._logo)).getSize()
            self._logo_aspect = logo_w_px / logo_h_px

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        gap = 5 * mm
        # Altura del texto primero
        provisional_logo_w = 22 * mm if self._has_logo else 0
        text_w = max(availWidth - provisional_logo_w - gap, 100 * mm)
        hr = self._razon.wrap(text_w, availHeight)[1]
        hu = self._ruc.wrap(text_w, availHeight)[1]
        hd = self._dir.wrap(text_w, availHeight)[1]
        gap_y = 2
        self._hr, self._hu, self._hd = hr, hu, hd
        self._gap_y = gap_y
        self.height = hr + gap_y + hu + gap_y + hd
        if self._has_logo:
            # Misma altura exacta que el texto → tope y base coinciden
            self._logo_h = self.height
            self._logo_w = self._logo_h * self._logo_aspect
            text_w = max(availWidth - self._logo_w - gap, 100 * mm)
            # Re-wrap por si cambió el ancho disponible
            self._hr = self._razon.wrap(text_w, availHeight)[1]
            self._hu = self._ruc.wrap(text_w, availHeight)[1]
            self._hd = self._dir.wrap(text_w, availHeight)[1]
            self.height = self._hr + gap_y + self._hu + gap_y + self._hd
            self._logo_h = self.height
            self._logo_w = self._logo_h * self._logo_aspect
            self._x_text = self._logo_w + gap
        else:
            self._logo_w = self._logo_h = 0
            self._x_text = 0
        return self.width, self.height

    def draw(self):
        c = self.canv
        if self._has_logo:
            c.drawImage(
                str(self._logo),
                0,
                0,
                width=self._logo_w,
                height=self._logo_h,
                preserveAspectRatio=True,
                mask="auto",
                anchor="c",
            )
        # Texto desde la misma base y=0 hasta height
        y = 0
        self._dir.drawOn(c, self._x_text, y)
        y += self._hd + self._gap_y
        self._ruc.drawOn(c, self._x_text, y)
        y += self._hu + self._gap_y
        self._razon.drawOn(c, self._x_text, y)


def _header_empresa(story, title_style=None, normal=None, small=None, *, logo_mm: float | None = None) -> None:
    story.append(EmpresaHeader())
    story.append(Spacer(1, 8))


def generar_pdf_comprobante(comprobante: Comprobante, emisor: Usuario | None = None) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    title_style, normal, small, subtitle = _styles()

    story = []
    _header_empresa(story, title_style, normal, small)

    tipo = TIPO_LABELS.get(comprobante.tipo, str(comprobante.tipo))
    story.append(
        Paragraph(
            f"<b>{tipo}</b> &nbsp;&nbsp; {comprobante.serie}-{comprobante.numero.zfill(8)}",
            subtitle,
        )
    )
    story.append(Spacer(1, 4))

    info = [
        ["Fecha de emisión:", comprobante.fecha_emision.strftime("%d/%m/%Y")],
        ["Estado:", ESTADO_LABELS.get(comprobante.estado.value, comprobante.estado.value)],
        ["Moneda:", "Soles (PEN)" if comprobante.moneda == "PEN" else comprobante.moneda],
        ["Cliente:", comprobante.cliente_nombre],
        ["Documento:", comprobante.cliente_documento or "—"],
    ]
    if comprobante.fecha_vencimiento:
        info.append(["Vencimiento:", comprobante.fecha_vencimiento.strftime("%d/%m/%Y")])
    zona = getattr(comprobante, "zona", None)
    motivo = getattr(comprobante, "motivo", None)
    if zona:
        info.append(["Zona:", zona])
    if motivo:
        info.append(["Motivo:", motivo])

    info_table = Table(info, colWidths=[40 * mm, 130 * mm])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#334155")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(info_table)
    story.append(Spacer(1, 10))

    rows = [["#", "Descripción", "Cant.", "P. Unit.", "IGV", "Subtotal"]]
    for idx, item in enumerate(comprobante.items, start=1):
        aplica = bool(getattr(item, "aplica_igv", True))
        rows.append(
            [
                str(idx),
                item.descripcion,
                f"{float(item.cantidad):,.3f}".rstrip("0").rstrip("."),
                f"S/ {float(item.precio_unitario):,.2f}",
                "Sí" if aplica else "No",
                f"S/ {float(item.subtotal):,.2f}",
            ]
        )

    items_table = Table(rows, colWidths=[10 * mm, 78 * mm, 22 * mm, 28 * mm, 14 * mm, 28 * mm])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3d2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 10))

    totals = [
        ["Op. Gravada / Subtotal:", f"S/ {float(comprobante.subtotal):,.2f}"],
        ["IGV (18%):", f"S/ {float(comprobante.igv):,.2f}"],
        ["TOTAL:", f"S/ {float(comprobante.total):,.2f}"],
    ]
    totals_table = Table(totals, colWidths=[40 * mm, 35 * mm], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#0f3d2e")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#ecfdf5")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(totals_table)

    if comprobante.observaciones:
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"<b>Observaciones:</b> {comprobante.observaciones}", normal))

    story.append(Spacer(1, 18))
    story.append(
        Paragraph(
            "Documento generado por Agenda Facturas — JAELIN E.I.R.L. "
            "Representación impresa referencial (no sustituye el CPE SUNAT).",
            small,
        )
    )

    doc.build(story)
    return buffer.getvalue()


def _table_style_header() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3d2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
    )


def generar_pdf_reporte_comprobantes(
    docs: list[Comprobante],
    *,
    filtros: dict | None = None,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )
    title_style, normal, small, subtitle = _styles()
    story = []
    _header_empresa(story, title_style, normal, small)
    story.append(Paragraph("Reporte de comprobantes", subtitle))

    filtros = filtros or {}
    filtros_txt = []
    if filtros.get("fecha_desde") or filtros.get("fecha_hasta"):
        filtros_txt.append(
            f"Periodo: {filtros.get('fecha_desde') or '…'} — {filtros.get('fecha_hasta') or '…'}"
        )
    if filtros.get("zona"):
        filtros_txt.append(f"Zona: {filtros['zona']}")
    if filtros.get("estado"):
        filtros_txt.append(f"Estado: {ESTADO_LABELS.get(filtros['estado'], filtros['estado'])}")
    if filtros.get("tipo"):
        tipo_val = filtros["tipo"]
        tipo_lbl = next(
            (lbl for key, lbl in TIPO_LABELS.items() if getattr(key, "value", key) == tipo_val),
            tipo_val,
        )
        filtros_txt.append(f"Tipo: {tipo_lbl}")
    if filtros.get("q"):
        filtros_txt.append(f"Búsqueda: {filtros['q']}")
    if filtros_txt:
        story.append(Paragraph(" · ".join(filtros_txt), small))
    story.append(
        Paragraph(
            f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} · {len(docs)} documento(s)",
            small,
        )
    )
    story.append(Spacer(1, 8))

    rows = [["Fecha", "Tipo", "Serie-Nº", "Cliente", "Zona", "Estado", "Total"]]
    total_general = 0.0
    for c in docs:
        total_general += float(c.total or 0)
        rows.append(
            [
                c.fecha_emision.strftime("%d/%m/%Y"),
                TIPO_LABELS.get(c.tipo, str(c.tipo))[:18],
                f"{c.serie}-{c.numero}",
                (c.cliente_nombre or "")[:36],
                getattr(c, "zona", None) or "—",
                ESTADO_LABELS.get(c.estado.value, c.estado.value),
                f"S/ {float(c.total):,.2f}",
            ]
        )
    rows.append(["", "", "", "", "", "TOTAL", f"S/ {total_general:,.2f}"])

    table = Table(
        rows,
        colWidths=[22 * mm, 38 * mm, 28 * mm, 70 * mm, 32 * mm, 24 * mm, 28 * mm],
    )
    style = _table_style_header()
    style.add("ALIGN", (-1, 1), (-1, -1), "RIGHT")
    style.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    style.add("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#ecfdf5"))
    table.setStyle(style)
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Reporte filtrado — JAELIN E.I.R.L.", small))
    doc.build(story)
    return buffer.getvalue()


def generar_pdf_reporte_cajas(
    movimientos: list[MovimientoCaja],
    *,
    filtros: dict | None = None,
    total_ingresos: float = 0,
    total_egresos: float = 0,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )
    title_style, normal, small, subtitle = _styles()
    story = []
    _header_empresa(story, title_style, normal, small)
    story.append(Paragraph("Reporte de movimientos de cajas", subtitle))

    filtros = filtros or {}
    filtros_txt = []
    if filtros.get("fecha_desde") or filtros.get("fecha_hasta"):
        filtros_txt.append(
            f"Periodo: {filtros.get('fecha_desde') or '…'} — {filtros.get('fecha_hasta') or '…'}"
        )
    if filtros.get("caja"):
        filtros_txt.append(f"Caja: {filtros['caja']}")
    if filtros.get("tipo"):
        filtros_txt.append(f"Tipo: {filtros['tipo']}")
    if filtros.get("q"):
        filtros_txt.append(f"Búsqueda: {filtros['q']}")
    if filtros_txt:
        story.append(Paragraph(" · ".join(filtros_txt), small))
    story.append(
        Paragraph(
            f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} · {len(movimientos)} movimiento(s)",
            small,
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            f"<b>Ingresos:</b> S/ {total_ingresos:,.2f} &nbsp;&nbsp; "
            f"<b>Egresos:</b> S/ {total_egresos:,.2f} &nbsp;&nbsp; "
            f"<b>Saldo periodo:</b> S/ {total_ingresos - total_egresos:,.2f}",
            normal,
        )
    )
    story.append(Spacer(1, 8))

    rows = [["Fecha", "Caja", "Tipo", "N° Transacción", "Concepto", "Monto"]]
    for m in movimientos:
        caja_nombre = m.caja.nombre if getattr(m, "caja", None) else ""
        monto = float(m.monto or 0)
        signo = "−" if str(m.tipo.value if hasattr(m.tipo, "value") else m.tipo) == "egreso" else "+"
        rows.append(
            [
                m.fecha.strftime("%d/%m/%Y") if isinstance(m.fecha, date) else str(m.fecha),
                (caja_nombre or "")[:28],
                "Ingreso" if str(getattr(m.tipo, "value", m.tipo)) == "ingreso" else "Egreso",
                getattr(m, "numero_transaccion", None) or "—",
                (m.concepto or "")[:48],
                f"{signo}S/ {monto:,.2f}",
            ]
        )

    table = Table(
        rows,
        colWidths=[22 * mm, 40 * mm, 22 * mm, 35 * mm, 95 * mm, 28 * mm],
    )
    style = _table_style_header()
    style.add("ALIGN", (-1, 1), (-1, -1), "RIGHT")
    table.setStyle(style)
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Reporte filtrado — JAELIN E.I.R.L.", small))
    doc.build(story)
    return buffer.getvalue()
