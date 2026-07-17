"""Consulta en línea de RUC/DNI (datos públicos SUNAT / RENIEC vía API)."""

from __future__ import annotations

import re

import httpx

from app.config import get_settings

settings = get_settings()

HEADERS_BASE = {
    "Accept": "application/json",
    "User-Agent": "AgendaFacturasPeru/1.0",
}


def limpiar_numero(numero: str) -> str:
    return re.sub(r"\D", "", numero or "")


def validar_ruc(ruc: str) -> bool:
    if not re.fullmatch(r"\d{11}", ruc):
        return False
    factores = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(ruc[i]) * factores[i] for i in range(10))
    resto = suma % 11
    digito = 11 - resto
    if digito == 10:
        digito = 0
    elif digito == 11:
        digito = 1
    return digito == int(ruc[10])


def detectar_tipo(numero: str) -> str | None:
    if len(numero) == 8:
        return "dni"
    if len(numero) == 11 and validar_ruc(numero):
        return "ruc"
    if len(numero) == 11:
        return "ruc"  # permitir consulta aunque el dígito verificador falle
    return None


async def _get_json(url: str, headers: dict) -> tuple[int, dict | None, str]:
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return 200, res.json(), ""
            if res.status_code == 404:
                return 404, None, "Documento no encontrado"
            if res.status_code == 429:
                return 429, None, "Límite de consultas alcanzado. Intente en unos segundos."
            if res.status_code == 401:
                return 401, None, "Token de API inválido. Configure SUNAT_API_TOKEN en .env"
            try:
                detail = res.json()
                msg = detail.get("message") or detail.get("error") or res.text[:200]
            except Exception:  # noqa: BLE001
                msg = res.text[:200] or f"Error HTTP {res.status_code}"
            return res.status_code, None, str(msg)
    except httpx.TimeoutException:
        return 504, None, "Tiempo de espera agotado al consultar SUNAT"
    except httpx.RequestError as exc:
        return 502, None, f"No se pudo conectar al servicio de consulta: {exc}"


def _normalizar(tipo: str, data: dict) -> dict:
    nombre = (
        data.get("nombre")
        or data.get("razonSocial")
        or data.get("nombreCompleto")
        or " ".join(
            p
            for p in [
                data.get("nombres", ""),
                data.get("apellidoPaterno", ""),
                data.get("apellidoMaterno", ""),
            ]
            if p
        ).strip()
    )
    numero = str(data.get("numeroDocumento") or data.get("numero") or data.get("ruc") or data.get("dni") or "")
    direccion = data.get("direccion") or data.get("direccionCompleta") or ""
    if not direccion and data.get("distrito"):
        partes = [
            data.get("viaTipo"),
            data.get("viaNombre"),
            data.get("numero"),
            data.get("distrito"),
            data.get("provincia"),
            data.get("departamento"),
        ]
        direccion = " ".join(str(p) for p in partes if p and str(p) not in {"-", "None"})

    return {
        "tipo": tipo,
        "numero": numero,
        "nombre": nombre.strip(),
        "estado": data.get("estado") or "",
        "condicion": data.get("condicion") or "",
        "direccion": direccion.strip(),
        "ubigeo": data.get("ubigeo") or "",
        "distrito": data.get("distrito") or "",
        "provincia": data.get("provincia") or "",
        "departamento": data.get("departamento") or "",
    }


async def consultar_documento(numero: str) -> tuple[bool, dict | str]:
    limpio = limpiar_numero(numero)
    tipo = detectar_tipo(limpio)
    if not tipo:
        return False, "Ingrese un DNI (8 dígitos) o RUC (11 dígitos) válido"

    token = (settings.sunat_api_token or "").strip()
    headers = {**HEADERS_BASE}

    # 1) Intento gratuito / v1 (apis.net.pe)
    if tipo == "ruc":
        url_v1 = f"https://api.apis.net.pe/v1/ruc?numero={limpio}"
        headers_v1 = {**headers, "Referer": "https://apis.net.pe/api-consulta-ruc"}
    else:
        url_v1 = f"https://api.apis.net.pe/v1/dni?numero={limpio}"
        headers_v1 = {**headers, "Referer": "https://apis.net.pe/api-consulta-dni"}

    code, data, err = await _get_json(url_v1, headers_v1)
    if code == 200 and data:
        return True, _normalizar(tipo, data)

    # 2) Si hay token, usar API v2 / decolecta
    if token:
        headers_auth = {
            **headers,
            "Authorization": f"Bearer {token}",
            "Referer": "https://apis.net.pe/",
        }
        if tipo == "ruc":
            urls = [
                f"https://api.apis.net.pe/v2/sunat/ruc?numero={limpio}",
                f"https://api.decolecta.com/v1/sunat/ruc?numero={limpio}",
            ]
        else:
            urls = [
                f"https://api.apis.net.pe/v2/reniec/dni?numero={limpio}",
                f"https://api.decolecta.com/v1/reniec/dni?numero={limpio}",
            ]
        for url in urls:
            code2, data2, err2 = await _get_json(url, headers_auth)
            if code2 == 200 and data2:
                return True, _normalizar(tipo, data2)
            err = err2 or err

    if code == 404:
        return False, "Documento no encontrado en SUNAT / RENIEC"
    return False, err or "No se pudo consultar el documento"
