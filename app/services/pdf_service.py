from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Comprobante, Usuario
from app.services.comprobante_calc import ESTADO_LABELS, TIPO_LABELS


def generar_pdf_comprobante(comprobante: Comprobante, emisor: Usuario) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitlePE",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#0f3d2e"),
        spaceAfter=6,
    )
    normal = ParagraphStyle("NormalPE", parent=styles["Normal"], fontSize=9, leading=12)
    small = ParagraphStyle("SmallPE", parent=styles["Normal"], fontSize=8, textColor=colors.grey)

    story = []
    razon = emisor.razon_social or emisor.nombre
    story.append(Paragraph(razon, title_style))
    if emisor.ruc_empresa:
        story.append(Paragraph(f"RUC: {emisor.ruc_empresa}", normal))
    if emisor.direccion:
        story.append(Paragraph(emisor.direccion, small))
    story.append(Spacer(1, 8))

    tipo = TIPO_LABELS.get(comprobante.tipo, str(comprobante.tipo))
    story.append(
        Paragraph(
            f"<b>{tipo}</b> &nbsp;&nbsp; {comprobante.serie}-{comprobante.numero.zfill(8)}",
            ParagraphStyle("DocTitle", parent=styles["Heading2"], fontSize=13, textColor=colors.HexColor("#b45309")),
        )
    )
    story.append(Spacer(1, 6))

    info = [
        ["Fecha de emisión:", comprobante.fecha_emision.strftime("%d/%m/%Y")],
        ["Estado:", ESTADO_LABELS.get(comprobante.estado.value, comprobante.estado.value)],
        ["Moneda:", "Soles (PEN)" if comprobante.moneda == "PEN" else comprobante.moneda],
        ["Cliente:", comprobante.cliente_nombre],
        ["Documento:", comprobante.cliente_documento or "—"],
    ]
    if comprobante.fecha_vencimiento:
        info.append(["Vencimiento:", comprobante.fecha_vencimiento.strftime("%d/%m/%Y")])

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
            "Documento generado por Agenda Facturas Perú. Representación impresa referencial "
            "(no sustituye el CPE SUNAT).",
            small,
        )
    )

    doc.build(story)
    return buffer.getvalue()
