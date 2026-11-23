"""Limpieza de los datos de un reporte contra su formato y cálculos derivados."""

from __future__ import annotations

import re
from datetime import date

from app.services.reportes_formatos import secciones

_HORA = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
TEXTO_MAX = 500
TEXTAREA_MAX = 4000


def _texto(valor, maximo: int) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        valor = str(valor)
    if not isinstance(valor, str):
        return None
    limpio = valor.strip()
    return limpio[:maximo] if limpio else None


def _numero(valor) -> float | None:
    if valor is None or valor == "" or isinstance(valor, bool):
        return None
    try:
        num = float(str(valor).replace(",", "."))
    except ValueError:
        return None
    if num != num or abs(num) > 1e12:
        return None
    return round(num, 4)


def _valor(definicion: dict, valor):
    tipo = definicion.get("tipo", "text")
    opciones = definicion.get("opciones") or []
    if tipo == "number":
        return _numero(valor)
    if tipo == "date":
        txt = _texto(valor, 10)
        if not txt:
            return None
        try:
            return date.fromisoformat(txt).isoformat()
        except ValueError:
            return None
    if tipo == "time":
        txt = _texto(valor, 5)
        if not txt or not _HORA.match(txt):
            return None
        h, m = txt.split(":")
        return f"{int(h):02d}:{m}"
    if tipo in ("select", "radio"):
        txt = _texto(valor, 120)
        return txt if txt in opciones else None
    if tipo == "check":
        return True if valor in (True, "true", "1", 1, "on") else None
    if tipo in ("checks", "multi"):
        if not isinstance(valor, list):
            return None
        elegidos = [o for o in opciones if o in {str(v) for v in valor}]
        return elegidos or None
    if tipo == "calc":
        return None
    maximo = definicion.get("max") or (TEXTAREA_MAX if tipo == "textarea" else TEXTO_MAX)
    return _texto(valor, maximo)


def _minutos(hora: str | None) -> int | None:
    if not hora or not _HORA.match(hora):
        return None
    h, m = hora.split(":")
    return int(h) * 60 + int(m)


def formatear_duracion(minutos: int | float | None) -> str:
    if minutos is None:
        return ""
    total = int(round(minutos))
    return f"{total // 60}:{total % 60:02d}"


def calcular(columna: dict, fila: dict):
    """Valor de una columna calculada (duración en minutos o diferencia numérica)."""
    calc = columna.get("calc") or {}
    if calc.get("tipo") == "duracion":
        ini, fin = _minutos(fila.get(calc["desde"])), _minutos(fila.get(calc["hasta"]))
        if ini is None or fin is None:
            return None
        return (fin - ini) % (24 * 60)
    if calc.get("tipo") == "resta":
        a, b = fila.get(calc["a"]), fila.get(calc["b"])
        if a is None or b is None:
            return None
        return round(a - b, 4)
    return None


def _fila_vacia(fila: dict) -> bool:
    return all(v in (None, "", [], False) for v in fila.values())


def limpiar_datos(formato: dict, datos: dict | None) -> dict:
    datos = datos if isinstance(datos, dict) else {}
    limpio: dict = {}
    for sec in secciones(formato):
        tipo = sec["tipo"]
        if tipo == "campos":
            for c in sec["campos"]:
                valor = _valor(c, datos.get(c["id"]))
                if valor is not None:
                    limpio[c["id"]] = valor
        elif tipo == "tabla":
            filas_in = datos.get(sec["id"])
            filas_in = filas_in if isinstance(filas_in, list) else []
            columnas = [c for c in sec["columnas"] if not c.get("solo_impresion")]
            filas: list[dict] = []
            for fila_in in filas_in[: sec["filas"]]:
                fila_in = fila_in if isinstance(fila_in, dict) else {}
                fila = {}
                for c in columnas:
                    valor = _valor(c, fila_in.get(c["id"]))
                    if valor is not None:
                        fila[c["id"]] = valor
                filas.append(fila)
            while filas and _fila_vacia(filas[-1]):
                filas.pop()
            if filas:
                limpio[sec["id"]] = filas
        elif tipo == "checklist":
            entrada = datos.get(sec["id"])
            entrada = entrada if isinstance(entrada, dict) else {}
            evaluadores = {e["id"] for e in sec["evaluadores"]}
            marcas: dict = {}
            for grupo in sec["grupos"]:
                for item in grupo["items"]:
                    por_eval = entrada.get(item["id"])
                    if not isinstance(por_eval, dict):
                        continue
                    fila = {k: v for k, v in por_eval.items() if k in evaluadores and v in sec["opciones"]}
                    if fila:
                        marcas[item["id"]] = fila
            if marcas:
                limpio[sec["id"]] = marcas
    return limpio


def faltantes(formato: dict, datos: dict) -> list[str]:
    return [
        c["label"]
        for sec in secciones(formato)
        if sec["tipo"] == "campos"
        for c in sec["campos"]
        if c.get("requerido") and datos.get(c["id"]) in (None, "", [])
    ]


def resumen(formato: dict, datos: dict) -> dict:
    spec = formato.get("resumen") or {}
    equipo = datos.get(spec.get("equipo") or "")
    responsable = None
    fuente = spec.get("responsable")
    if fuente:
        origen, claves = fuente
        if origen == "campos":
            responsable = " ".join(str(datos[k]) for k in claves if datos.get(k))
        else:
            for fila in datos.get(origen) or []:
                nombre = " ".join(str(fila[k]) for k in claves if fila.get(k))
                if nombre:
                    responsable = nombre
                    break
    return {
        "equipo": str(equipo)[:80] if equipo not in (None, "") else None,
        "responsable": (responsable or None) and responsable[:200],
        "turno": (str(datos["turno"])[:30] if datos.get("turno") else None),
    }


def conformidad(campo: dict, valor) -> str | None:
    limite = campo.get("limite")
    if not limite or valor is None:
        return None
    if "min" in limite and valor <= limite["min"]:
        return "NC"
    if "max" in limite and valor >= limite["max"]:
        return "NC"
    return "C"
