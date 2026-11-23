"""PDF de los reportes operativos al tamaño de papel de cada formato (cara y reverso)."""

from __future__ import annotations

from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.reportes_datos import calcular, conformidad, formatear_duracion

MARGEN = 7 * mm
GRIS = colors.HexColor("#e5e7eb")
GRIS_OSCURO = colors.HexColor("#374151")
BORDE = colors.HexColor("#6b7280")
ROJO = colors.HexColor("#c0262d")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


def _estilo(nombre: str, size: float = 6.5, bold: bool = False, align=None, color=None, leading=None) -> ParagraphStyle:
    return ParagraphStyle(
        nombre,
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=size,
        leading=leading or size * 1.2,
        alignment=align if align is not None else 0,
        textColor=color or colors.black,
    )


ST_VALOR = _estilo("RepValor")
ST_LABEL = _estilo("RepLabel", 6, bold=True)
ST_HEAD = _estilo("RepHead", 5.8, bold=True, align=TA_CENTER)
ST_CELDA = _estilo("RepCelda", 6.3, align=TA_CENTER)
ST_CELDA_IZQ = _estilo("RepCeldaIzq", 6.3)
ST_SECCION = _estilo("RepSeccion", 7.5, bold=True, color=colors.white)
ST_TITULO = _estilo("RepTitulo", 12, bold=True, leading=14)
ST_NUMERO = _estilo("RepNumero", 11, bold=True, align=TA_RIGHT, leading=13)
ST_NOTA = _estilo("RepNota", 6, color=colors.HexColor("#4b5563"))


def _xml(texto) -> str:
    return str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _num(valor) -> str:
    if valor is None or valor == "":
        return ""
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return _xml(valor)
    return f"{n:,.2f}".rstrip("0").rstrip(".") if n % 1 else f"{int(n):,}"


def _fecha(valor) -> str:
    if not valor:
        return ""
    try:
        d = date.fromisoformat(str(valor))
    except ValueError:
        return _xml(valor)
    return d.strftime("%d/%m/%Y")


def _fecha_larga(valor) -> str:
    try:
        d = date.fromisoformat(str(valor))
    except (TypeError, ValueError):
        return ""
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _texto_valor(definicion: dict, valor) -> str:
    tipo = definicion.get("tipo")
    if valor in (None, "", []):
        return ""
    if tipo == "date":
        return _fecha(valor)
    if tipo == "number":
        texto = _num(valor)
        estado = conformidad(definicion, valor)
        return f"{texto}  <b>({estado})</b>" if estado else texto
    if tipo == "check":
        return "X"
    if tipo in ("checks", "multi"):
        return _xml(", ".join(valor))
    return _xml(valor).replace("\n", "<br/>")


def _barra(titulo: str, ancho: float) -> Table:
    t = Table([[Paragraph(_xml(titulo).upper(), ST_SECCION)]], colWidths=[ancho])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS_OSCURO),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    return t


def _encabezado(formato: dict, numero: str, ancho: float) -> Table:
    prefijo = formato["prefijo"]
    correlativo = numero[len(prefijo):] if numero.startswith(prefijo) else numero
    caja = Paragraph(f"{_xml(prefijo.strip())} <font color='#c0262d'>{_xml(correlativo)}</font>", ST_NUMERO)
    ancho_caja = min(max(len(numero) * 2.6 * mm + 8 * mm, 48 * mm), ancho * 0.45)
    t = Table(
        [[Paragraph(_xml(formato["titulo"]).upper(), ST_TITULO), caja]],
        colWidths=[ancho - ancho_caja, ancho_caja],
    )
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (1, 0), (1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, 0), (0, 0), 0.8, colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _grilla_checks(opciones: list[str], elegidos: list[str], ancho: float, columnas: int = 3) -> Table:
    celdas = [Paragraph(f"<b>[{'X' if o in elegidos else '&nbsp;&nbsp;'}]</b> {_xml(o)}", ST_VALOR) for o in opciones]
    filas = [celdas[i:i + columnas] for i in range(0, len(celdas), columnas)]
    if filas and len(filas[-1]) < columnas:
        filas[-1] += [""] * (columnas - len(filas[-1]))
    t = Table(filas, colWidths=[ancho / columnas] * columnas)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, BORDE),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    return t


def _seccion_campos(sec: dict, datos: dict, ancho: float, escala: float = 1.0) -> list:
    por_fila = 4 if ancho > 260 * mm else 3 if ancho > 185 * mm else 2
    slot = ancho / por_fila
    ancho_label, ancho_valor = slot * 0.42, slot * 0.58
    filas: list[list] = []
    spans: list[tuple] = []
    alto_min: dict[int, float] = {}
    actual: list = []
    usados = 0

    def cerrar():
        nonlocal actual, usados
        if actual:
            actual += ["", ""] * (por_fila - usados)
            filas.append(actual)
        actual, usados = [], 0

    for c in sec["campos"]:
        span = por_fila if c.get("span", 1) >= 3 else min(c.get("span", 1), por_fila)
        if usados + span > por_fila:
            cerrar()
        valor = datos.get(c["id"])
        ancho_celda = ancho_valor + slot * (span - 1)
        if c["tipo"] == "checks":
            contenido = _grilla_checks(c.get("opciones") or [], valor or [], ancho_celda - 4)
        else:
            texto = _texto_valor(c, valor)
            if c["tipo"] == "textarea":
                lineas = texto.count("<br/>") + 1 if texto else 0
                texto += "<br/>" * max(0, round(c.get("filas", 3) * escala) - lineas)
            contenido = Paragraph(texto or "&nbsp;", ST_VALOR)
        col0 = usados * 2
        actual += [Paragraph(_xml(c["label"]), ST_LABEL), contenido] + ["", ""] * (span - 1)
        if span > 1:
            spans.append((len(filas), col0 + 1, col0 + span * 2 - 1))
        if c["tipo"] == "textarea":
            alto_min[len(filas)] = c.get("filas", 3) * 4 * mm
        usados += span
        if usados == por_fila:
            cerrar()
    cerrar()
    if not filas:
        return []

    t = Table(filas, colWidths=[ancho_label, ancho_valor] * por_fila)
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    for i in range(por_fila):
        estilo.append(("BACKGROUND", (i * 2, 0), (i * 2, -1), GRIS))
    for fila, c0, c1 in spans:
        estilo.append(("SPAN", (c0, fila), (c1, fila)))
        estilo.append(("BACKGROUND", (c0, fila), (c1, fila), colors.white))
    for fila in alto_min:
        estilo.append(("VALIGN", (0, fila), (-1, fila), "TOP"))
    t.setStyle(TableStyle(estilo))
    salida = []
    if sec.get("titulo"):
        salida.append(_barra(sec["titulo"], ancho))
    salida += [t, Spacer(1, 2.5 * mm)]
    return salida


def _celda_tabla(c: dict, fila: dict, prefill_valor):
    if c.get("solo_impresion"):
        return ""
    if c["tipo"] == "calc":
        valor = calcular(c, fila)
        if valor is None:
            return ""
        return formatear_duracion(valor) if c["calc"]["tipo"] == "duracion" else _num(valor)
    valor = fila.get(c["id"])
    if valor in (None, "", []) and prefill_valor:
        valor = prefill_valor
    if c["tipo"] == "number":
        return _num(valor)
    return _texto_valor(c, valor)


def _tabla(sec: dict, datos: dict, ancho: float, escala: float = 1.0) -> list:
    cols = sec["columnas"]
    filas_datos = datos.get(sec["id"]) or []
    etiquetas = sec.get("etiquetas_filas")
    numerar = sec.get("numerar", True)
    lleva_guia = bool(numerar or etiquetas)
    ancho_guia = sec.get("ancho_item", 1.0 if etiquetas else 0.7)
    pesos = ([ancho_guia] if lleva_guia else []) + [c.get("ancho", 1) for c in cols]
    factor_ancho = ancho / sum(pesos)
    anchos = [p * factor_ancho for p in pesos]
    desplaz = 1 if lleva_guia else 0
    muchas = len(cols) > 16
    st_head = _estilo("RepHeadT", 5.2 if muchas else 5.8, bold=True, align=TA_CENTER)
    st_celda = _estilo("RepCeldaT", 5.8 if muchas else 6.3, align=TA_CENTER)
    st_izq = _estilo("RepCeldaTI", 5.8 if muchas else 6.3)

    hay_grupos = any(c.get("grupo") for c in cols)
    encabezado: list[list] = []
    estilo: list = [
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
    ]
    if hay_grupos:
        fila0, fila1 = [], []
        if lleva_guia:
            fila0.append(Paragraph("ITEM" if numerar else "", st_head))
            fila1.append("")
            estilo.append(("SPAN", (0, 0), (0, 1)))
        i = 0
        while i < len(cols):
            grupo = cols[i].get("grupo")
            if not grupo:
                fila0.append(Paragraph(_xml(cols[i]["label"]), st_head))
                fila1.append("")
                estilo.append(("SPAN", (i + desplaz, 0), (i + desplaz, 1)))
                i += 1
                continue
            j = i
            while j < len(cols) and cols[j].get("grupo") == grupo:
                j += 1
            fila0.append(Paragraph(_xml(grupo), st_head))
            fila0 += [""] * (j - i - 1)
            fila1 += [Paragraph(_xml(c["label"]), st_head) for c in cols[i:j]]
            if j - i > 1:
                estilo.append(("SPAN", (i + desplaz, 0), (j - 1 + desplaz, 0)))
            i = j
        encabezado = [fila0, fila1]
    else:
        encabezado = [([Paragraph("ITEM" if numerar else "", st_head)] if lleva_guia else [])
                      + [Paragraph(_xml(c["label"]), st_head) for c in cols]]
    n_head = len(encabezado)
    estilo.append(("BACKGROUND", (0, 0), (-1, n_head - 1), GRIS))

    prefill = sec.get("prefill") or {}
    cuerpo = []
    totales = {c["id"]: 0.0 for c in cols if c.get("total")}
    con_datos = 0
    for i in range(sec["filas"]):
        fila = filas_datos[i] if i < len(filas_datos) and isinstance(filas_datos[i], dict) else {}
        if any(v not in (None, "", [], False) for v in fila.values()):
            con_datos += 1
        celdas = []
        if lleva_guia:
            guia = etiquetas[i] if etiquetas and i < len(etiquetas) else str(i + 1)
            celdas.append(Paragraph(f"<b>{_xml(guia)}</b>", st_celda))
        for c in cols:
            pre = (prefill.get(c["id"]) or [])
            texto = _celda_tabla(c, fila, pre[i] if i < len(pre) else None)
            estilo_celda = st_izq if c["tipo"] in ("text", "textarea", "multi") and c.get("ancho", 1) >= 1.5 else st_celda
            celdas.append(Paragraph(texto, estilo_celda) if texto else "")
            if c["id"] in totales:
                valor = calcular(c, fila) if c["tipo"] == "calc" else fila.get(c["id"])
                if isinstance(valor, (int, float)):
                    totales[c["id"]] += valor
        cuerpo.append(celdas)

    filas = encabezado + cuerpo
    alto = max(3.8, sec.get("fila_alto_mm", 5.2) * escala) * mm
    alturas = [None] * n_head + [alto] * len(cuerpo)
    if totales or sec.get("contar_filas"):
        etiqueta = "TOTALES"
        if sec.get("contar_filas"):
            etiqueta += f" · {con_datos} {sec['contar_filas'].lower()}"
        fila_tot = [""] * len(anchos)
        fila_tot[0] = Paragraph(f"<b>{etiqueta}</b>", st_izq)
        for idx, c in enumerate(cols):
            if c["id"] in totales:
                v = totales[c["id"]]
                es_dur = c.get("calc", {}).get("tipo") == "duracion"
                fila_tot[idx + desplaz] = Paragraph(
                    f"<b>{formatear_duracion(v) if es_dur else _num(v)}</b>", st_celda
                )
        primera_total = min(
            (idx + desplaz for idx, c in enumerate(cols) if c["id"] in totales), default=len(anchos)
        )
        if primera_total > 1:
            estilo.append(("SPAN", (0, len(filas)), (primera_total - 1, len(filas))))
        estilo.append(("BACKGROUND", (0, len(filas)), (-1, len(filas)), GRIS))
        filas.append(fila_tot)
        alturas.append(alto)

    t = Table(filas, colWidths=anchos, rowHeights=alturas, repeatRows=n_head)
    t.setStyle(TableStyle(estilo))
    salida = []
    if sec.get("titulo"):
        salida.append(_barra(sec["titulo"], ancho))
    salida += [t, Spacer(1, 2.5 * mm)]
    return salida


def _grupo_codigos(grupo: dict, ancho: float) -> Table:
    filas = [[Paragraph(_xml(grupo["titulo"]), ST_SECCION), ""]]
    for item in grupo["items"]:
        filas.append([Paragraph(f"<b>{_xml(item['codigo'])}</b>", ST_CELDA),
                      Paragraph(_xml(item["descripcion"]), ST_CELDA_IZQ)])
    ancho_cod = min(15 * mm, ancho * 0.26)
    t = Table(filas, colWidths=[ancho_cod, ancho - ancho_cod])
    t.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), GRIS_OSCURO),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("BACKGROUND", (0, 1), (0, -1), GRIS),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


def _columnas_de_grupos(grupos: list[dict], columnas: int, ancho: float, constructor) -> Table:
    gap = 3 * mm
    ancho_col = (ancho - gap * (columnas - 1)) / columnas
    pilas: list[list] = [[] for _ in range(columnas)]
    pesos = [0] * columnas
    for grupo in grupos:
        destino = pesos.index(min(pesos))
        pilas[destino] += [constructor(grupo, ancho_col), Spacer(1, 2.5 * mm)]
        pesos[destino] += len(grupo["items"]) + 2
    celdas, anchos = [], []
    for i, pila in enumerate(pilas):
        celdas.append(pila or "")
        anchos.append(ancho_col)
        if i < columnas - 1:
            celdas.append("")
            anchos.append(gap)
    t = Table([celdas], colWidths=anchos)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _catalogo(sec: dict, ancho: float) -> list:
    return [
        _barra(sec["titulo"], ancho),
        Spacer(1, 1.5 * mm),
        _columnas_de_grupos(sec["grupos"], sec.get("columnas", 2), ancho, _grupo_codigos),
    ]


def _lista(sec: dict, ancho: float) -> list:
    salida = [_barra(sec["titulo"], ancho)]
    if sec.get("nota"):
        salida.append(Paragraph(_xml(sec["nota"]), ST_NOTA))
    salida += [Spacer(1, 1.5 * mm), _columnas_de_grupos(sec["grupos"], 2, ancho, _grupo_codigos)]
    return salida


def _checklist(sec: dict, datos: dict, ancho: float) -> list:
    marcas = datos.get(sec["id"]) or {}
    evaluadores = sec["evaluadores"]
    opciones = sec["opciones"]
    ancho_marca = 6 * mm
    ancho_num, ancho_rb = 6 * mm, 6 * mm
    ancho_texto = ancho - ancho_num - ancho_rb - ancho_marca * len(opciones) * len(evaluadores)
    anchos = [ancho_num, ancho_texto, ancho_rb] + [ancho_marca] * (len(opciones) * len(evaluadores))
    st_txt = _estilo("RepCheck", 5.8)

    fila0 = [Paragraph("N°", ST_HEAD), Paragraph(_xml(sec["titulo"]).upper(), ST_HEAD), Paragraph("RB", ST_HEAD)]
    fila1 = ["", "", ""]
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 1), GRIS),
        ("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (1, 1)), ("SPAN", (2, 0), (2, 1)),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
    ]
    for i, ev in enumerate(evaluadores):
        c0 = 3 + i * len(opciones)
        fila0 += [Paragraph(_xml(ev["label"]), ST_HEAD)] + [""] * (len(opciones) - 1)
        fila1 += [Paragraph(o, ST_HEAD) for o in opciones]
        estilo.append(("SPAN", (c0, 0), (c0 + len(opciones) - 1, 0)))
    filas = [fila0, fila1]
    for grupo in sec["grupos"]:
        filas.append([Paragraph(f"<b>{_xml(grupo['titulo'])}</b>", st_txt)] + [""] * (len(anchos) - 1))
        estilo.append(("SPAN", (0, len(filas) - 1), (-1, len(filas) - 1)))
        estilo.append(("BACKGROUND", (0, len(filas) - 1), (-1, len(filas) - 1), colors.HexColor("#f3f4f6")))
        for item in grupo["items"]:
            elegidos = marcas.get(item["id"]) or {}
            fila = [
                Paragraph(_xml(item["id"]) if item["id"].isdigit() else "", ST_CELDA),
                Paragraph(_xml(item["texto"]), st_txt),
                Paragraph(f"<b>{_xml(item.get('rb') or '')}</b>", ST_CELDA),
            ]
            for ev in evaluadores:
                fila += [Paragraph("<b>X</b>", ST_CELDA) if elegidos.get(ev["id"]) == o else "" for o in opciones]
            filas.append(fila)
    t = Table(filas, colWidths=anchos, repeatRows=2)
    t.setStyle(TableStyle(estilo))
    salida = []
    if sec.get("nota"):
        salida.append(Paragraph(_xml(sec["nota"]), ST_NOTA))
        salida.append(Spacer(1, 1.5 * mm))
    return salida + [t]


def _seccion(sec: dict, datos: dict, ancho: float, escala: float) -> list:
    tipo = sec["tipo"]
    if tipo == "campos":
        return _seccion_campos(sec, datos, ancho, escala)
    if tipo == "tabla":
        return _tabla(sec, datos, ancho, escala)
    if tipo == "catalogo":
        return _catalogo(sec, ancho)
    if tipo == "lista":
        return _lista(sec, ancho)
    if tipo == "checklist":
        return _checklist(sec, datos, ancho)
    return []


def _cuerpo(secciones: list[dict], datos: dict, ancho: float, escala: float) -> list:
    story: list = []
    por_id = {s.get("id"): s for s in secciones if s.get("id")}
    saltar: set[str] = set()
    for sec in secciones:
        if sec.get("id") in saltar:
            continue
        pareja = por_id.get(sec.get("lado_a_lado") or "")
        if pareja:
            saltar.add(pareja["id"])
            gap = 4 * mm
            mitad = (ancho - gap) / 2
            t = Table(
                [[_seccion(sec, datos, mitad, escala), "", _seccion(pareja, datos, mitad, escala)]],
                colWidths=[mitad, gap, mitad],
            )
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(t)
            continue
        story += _seccion(sec, datos, ancho, escala)
    while story and isinstance(story[-1], Spacer):
        story.pop()
    return story


def _carta(formato: dict, numero: str, datos: dict, ancho: float) -> list:
    st_txt = _estilo("CartaTxt", 10, leading=14, align=TA_JUSTIFY)
    st_lbl = _estilo("CartaLbl", 10, bold=True, leading=14)
    st_val = _estilo("CartaVal", 10, leading=14)
    st_centro = _estilo("CartaCentro", 10, align=TA_CENTER, leading=13)
    st_anio = _estilo("CartaAnio", 9, align=TA_CENTER, color=colors.HexColor("#374151"))

    anio = (datos.get("fecha") or date.today().isoformat())[:4]
    entidad = datos.get("entidad")
    numero_completo = f"{numero}-{entidad}-{anio}" if entidad else f"{numero}-{anio}"
    story: list = []
    if datos.get("denominacion_anio"):
        story += [Paragraph(f"<i>“{_xml(datos['denominacion_anio'])}”</i>", st_anio), Spacer(1, 3 * mm)]
    story += [_encabezado(formato, numero_completo, ancho), Spacer(1, 6 * mm)]

    medico = datos.get("medico") or ""
    filas = [
        ("DE", f"Dr(a). {_xml(medico)}<br/>{_xml(datos.get('cargo_medico') or '')}" if medico else _xml(datos.get("cargo_medico") or "")),
        ("ASUNTO", _xml(datos.get("asunto") or "")),
        ("FECHA", _fecha_larga(datos.get("fecha"))),
        ("H. CLÍNICA LABORAL", _xml(datos.get("historia_clinica") or datos.get("dni") or "")),
        ("USUARIO", _xml(datos.get("paciente") or "")),
        ("EDAD", f"{_num(datos['edad'])} años" if datos.get("edad") is not None else ""),
        ("DNI", _xml(datos.get("dni") or "")),
    ]
    t = Table([[Paragraph(k, st_lbl), Paragraph(":", st_lbl), Paragraph(v or "&nbsp;", st_val)] for k, v in filas],
              colWidths=[42 * mm, 4 * mm, ancho - 46 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ("LINEBELOW", (0, -1), (-1, -1), 0.8, colors.black),
    ]))
    story += [t, Spacer(1, 6 * mm)]

    for parrafo in (datos.get("contenido") or "").split("\n"):
        story.append(Paragraph(_xml(parrafo) or "&nbsp;", st_txt))
    story.append(Spacer(1, 6 * mm))
    if datos.get("cierre"):
        story += [Paragraph(_xml(datos["cierre"]), st_txt), Spacer(1, 4 * mm)]
    story += [Paragraph("Atentamente,", st_txt), Spacer(1, 22 * mm)]
    firma = Table([[""]], colWidths=[70 * mm])
    firma.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.8, colors.black)]))
    firma.hAlign = "CENTER"
    story += [firma, Paragraph(f"<b>Dr(a). {_xml(medico)}</b>" if medico else "&nbsp;", st_centro),
              Paragraph(_xml(datos.get("cargo_medico") or ""), st_centro), Spacer(1, 8 * mm)]
    if datos.get("iniciales"):
        story.append(Paragraph(_xml(datos["iniciales"]), _estilo("CartaIni", 8)))
    if datos.get("cc"):
        story.append(Paragraph(f"CC.: {_xml(datos['cc'])}", _estilo("CartaCc", 8)))
    return story


def generar_pdf_reporte(formato: dict, numero: str, datos: dict) -> bytes:
    papel = formato["papel"]
    ancho_pag, alto_pag = papel["ancho_mm"] * mm, papel["alto_mm"] * mm
    ancho = ancho_pag - 2 * MARGEN
    pie = (datos.get("pie") or "") if formato.get("layout") == "carta" else ""

    def nuevo_doc(destino):
        return SimpleDocTemplate(
            destino,
            pagesize=(ancho_pag, alto_pag),
            leftMargin=MARGEN,
            rightMargin=MARGEN,
            topMargin=MARGEN,
            bottomMargin=MARGEN + (10 * mm if pie else 4 * mm),
            title=f"{formato['titulo']} {numero}",
        )

    def cara(escala):
        return [_encabezado(formato, numero, ancho), Spacer(1, 3 * mm)] + _cuerpo(
            formato.get("cara") or [], datos, ancho, escala
        )

    def reverso(escala):
        return [
            Paragraph("<b>REVERSO</b>", _estilo("RepRev", 8, color=colors.HexColor("#6b7280"))),
            Spacer(1, 2 * mm),
        ] + _cuerpo(formato["reverso"], datos, ancho, escala)

    def escala_que_entra(constructor) -> float:
        """Achica la altura de filas hasta que la cara (o el reverso) quepa en una sola hoja."""
        escalas = (1.0, 0.92, 0.85, 0.78, 0.72, 0.66, 0.6)
        for escala in escalas:
            prueba = nuevo_doc(BytesIO())
            prueba.build(constructor(escala))
            if prueba.page <= 1:
                return escala
        return escalas[-1]

    buffer = BytesIO()
    doc = nuevo_doc(buffer)

    def al_pintar(canv, doc_):
        canv.saveState()
        if pie:
            p = Paragraph(_xml(pie), _estilo("CartaPie", 7.5, align=TA_CENTER, color=colors.HexColor("#374151")))
            _, h = p.wrap(ancho, 20 * mm)
            canv.setStrokeColor(colors.HexColor("#9ca3af"))
            canv.line(MARGEN, MARGEN + h + 2 * mm, ancho_pag - MARGEN, MARGEN + h + 2 * mm)
            p.drawOn(canv, MARGEN, MARGEN)
        else:
            canv.setFont("Helvetica", 5.5)
            canv.setFillColor(colors.HexColor("#6b7280"))
            canv.drawString(MARGEN, MARGEN - 2 * mm, f"{numero} · Formato {papel['etiqueta']}")
            canv.drawRightString(ancho_pag - MARGEN, MARGEN - 2 * mm, f"Pág. {doc_.page}")
        canv.restoreState()

    if formato.get("layout") == "carta":
        story = _carta(formato, numero, datos, ancho)
    else:
        story = cara(escala_que_entra(cara))
        if formato.get("reverso"):
            story += [PageBreak()] + reverso(escala_que_entra(reverso))
    doc.build(story, onFirstPage=al_pintar, onLaterPages=al_pintar)
    return buffer.getvalue()
