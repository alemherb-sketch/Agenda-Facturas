"""Planes de mantenimiento preventivo de los equipos, tal como están en sus hojas PDF.

Cada equipo trae sus datos de placa, el ciclo de frecuencias (horas del ciclo → nivel PM)
y sus repuestos con las horas del ciclo en que se cambian (las "X" de la hoja).
El mismo catálogo alimenta el formulario del frontend y la validación del servidor.
"""

from __future__ import annotations

from copy import deepcopy

LEYENDA_PM = {
    "PM1": "Mantenimiento Preventivo Nivel 1",
    "PM2": "Mantenimiento Preventivo Nivel 2",
    "PM3": "Mantenimiento Preventivo Nivel 3",
    "PM4": "Mantenimiento Preventivo Nivel 4",
    "PM3000": "Mantenimiento Preventivo General",
}

# Ciclo de 2000 h: PM1 cada 250 h, PM2 a las 500 y 1500, PM3 a las 1000 y PM4 a las 2000.
CICLO_2000 = [
    (250, "PM1"), (500, "PM2"), (750, "PM1"), (1000, "PM3"),
    (1250, "PM1"), (1500, "PM2"), (1750, "PM1"), (2000, "PM4"),
]
# Ciclo de 3000 h del 950L: el PM3 vuelve a las 2000 h y el PM3000 (general) cierra el ciclo.
CICLO_3000 = [
    (250, "PM1"), (500, "PM2"), (750, "PM1"), (1000, "PM3"),
    (1250, "PM1"), (1500, "PM2"), (1750, "PM1"), (2000, "PM3"),
    (2250, "PM1"), (2500, "PM2"), (2750, "PM1"), (3000, "PM3000"),
]


def _cada(paso: int, fin: int) -> list[int]:
    return list(range(paso, fin + 1, paso))


# Horas del ciclo de 2000 h en que se cambia cada repuesto
C250 = _cada(250, 2000)
C500 = _cada(500, 2000)
C1000 = _cada(1000, 2000)
C2000 = [2000]
# Horas del ciclo de 3000 h (950L)
L250 = _cada(250, 3000)
L500 = _cada(500, 3000)
L1000 = _cada(1000, 3000)
L2000_3000 = [2000, 3000]
L3000 = [3000]


def _equipo(
    id_: str,
    *,
    tipo: str,
    marca: str,
    serie: str,
    motor_modelo: str,
    motor_serie: str,
    anio: int,
    ciclo: list[tuple[int, str]],
    repuestos: list[tuple[str, str, int, list[int]]],
) -> dict:
    return {
        "id": id_,
        "tipo": tipo,
        "marca": marca,
        "modelo": id_,
        "serie": serie,
        "motor_modelo": motor_modelo,
        "motor_serie": motor_serie,
        "anio": anio,
        "titulo": f"{tipo} {id_}",
        "ciclo_horas": ciclo[-1][0],
        "frecuencias": [{"horas": h, "pm": pm} for h, pm in ciclo],
        "repuestos": [
            {"item": i, "numero_parte": parte, "descripcion": desc, "cantidad": cant, "horas": list(horas)}
            for i, (parte, desc, cant, horas) in enumerate(repuestos, start=1)
        ],
    }


EQUIPOS: list[dict] = [
    _equipo(
        "950L",
        tipo="CARGADOR FRONTAL",
        marca="CATERPILLAR",
        serie="LXX10206",
        motor_modelo="C7.1",
        motor_serie="E7A07440",
        anio=2017,
        ciclo=CICLO_3000,
        repuestos=[
            ("462-1171", "FILTRO ACEITE MOTOR", 1, L250),
            ("423-8524", "FILTRO SEPARADOR AGUA/COMBUSTIBLE", 1, L250),
            ("360-8960", "FILTRO ELEMENTO COMBUSTIBLE", 2, L250),
            ("2040TN", "FILTRO RACORD", 1, L250),
            ("577-1433", "FILTRO DE AIRE PRIMARIO", 1, L250),
            ("3E-9713", "ACEITE MOTOR 15W 40 - BALDE", 1, L250),
            ("3E-9902", "ACEITE MOTOR 15W 40 - GALON", 1, L250),
            ("337-0790", "FILTRO DE AIRE SECUNDARIO", 1, L500),
            ("273-5711", "FILTRO RESPIRADERO MOTOR (ELIMINACION DE HUMOS)", 1, L500),
            ("350-8742", "FAJA DE ACCESORIOS", 1, L1000),
            ("389-1079", "FILTRO DE TRANSMISION", 1, L1000),
            ("376-1288", "FILTRO HIDRAULICO RETORNO", 1, L1000),
            ("436-3443", "FILTRO HIDRAULICO LINEA", 1, L1000),
            ("5K-1787", "SELLO FILTRO HIDRAULICO DE RETORNO", 1, L1000),
            ("095-1671", "SELLO FILTRO DE TRANSMISION", 1, L1000),
            ("527-1641", "EMPAQUETADURA TAPA BALANCINES", 1, L1000),
            ("8H-7521", "SELLO SCREAM MAGNETICO", 1, L1000),
            ("7M-8485", "SELLO TAPON DRENAJE ACEITE TRANSMISION", 1, L1000),
            ("077-3241", "SELLO BASE TAPON DRENAJE", 1, L1000),
            ("290-2287", "FILTRO AIRE CABINA", 1, L1000),
            ("290-2288", "FILTRO AIRE ACONDICIONADO", 1, L1000),
            ("346-8340", "RESPIRADERO DEL TANQUE HIDRAULICO", 1, L2000_3000),
            ("350-7735", "FILTRO TAPA TANQUE COMBUSTIBLE", 1, L2000_3000),
            ("1U-9891", "ADITIVO DE ACEITE HIDRAULICO", 2, L2000_3000),
            ("8T-9572", "ACEITE TRANSMISION SAE 30 - BALDE", 3, L2000_3000),
            ("8T-9576", "ACEITE DIFERENCIALES SAE 50 - BALDE", 5, L2000_3000),
            ("309-6931", "ACEITE HIDRAULICO ADV10W - BALDE", 10, L3000),
        ],
    ),
    _equipo(
        "962H",
        tipo="CARGADOR FRONTAL",
        marca="CATERPILLAR",
        serie="N4A00325",
        motor_modelo="C7",
        motor_serie="C7C02357",
        anio=2006,
        ciclo=CICLO_2000,
        repuestos=[
            ("1R-1807", "FILTRO ACEITE MOTOR", 1, C250),
            ("1R-0762", "FILTRO COMBUSTIBLE", 1, C250),
            ("326-1644", "FILTRO SEPARADOR AGUA/COMBUSTIBLE", 1, C250),
            ("2040TN", "FILTRO RACORD", 1, C250),
            ("245-6375", "FILTRO AIRE PRIMARIO", 1, C250),
            # La hoja del 962H no marca el aceite de motor a las 1250 h ni a las 1750 h.
            ("3E-9713", "ACEITE MOTOR 15W 40 - BALDE", 1, [250, 500, 750, 1000, 1500, 2000]),
            ("3E-9902", "ACEITE MOTOR 15W 40 - GALON", 3, [250, 500, 750, 1000, 1500, 2000]),
            ("245-6376", "FILTRO AIRE SECUNDARIO", 1, C500),
            # Sin ninguna X en la hoja: queda en la lista para marcarlo cuando se cambie.
            ("220-8678", "SELLO FILTRO SEPARADOR COMBUSTIBLE", 1, []),
            ("1G-8878", "FILTRO TRANSMISION", 1, C1000),
            ("144-0832", "FILTRO HIDRAULICO DRENAJE", 1, C2000),
            ("225-4118", "FILTRO HIDRAULICO LINEA", 1, C2000),
            ("8H-2046", "SELLO RESPIRADERO MOTOR", 1, C2000),
            ("8H-7521", "SELLO RESPIRADERO TRANSMISION", 1, C2000),
            ("8T-9572", "ACEITE TRANSMISION SAE 30 - BALDE", 2, C2000),
            ("8T-9576", "ACEITE DIFERENCIALES SAE 50 - BALDE", 4, C2000),
            ("1U-9891", "ADITIVO -1/4GALON", 1, C2000),
            ("272-0388", "EMPAQUETADURA TAPA BALANCINES", 1, C2000),
            ("253-4531", "FAJA DE ACCESORIOS", 1, C2000),
            ("309-6931", "ACEITE HIDRAULICO ADV 10 - BALDE", 10, C2000),
        ],
    ),
    _equipo(
        "330DL",
        tipo="EXCAVADORA",
        marca="CATERPILLAR",
        serie="ERN00280",
        motor_modelo="C9",
        motor_serie="THY02375",
        anio=2005,
        ciclo=CICLO_2000,
        repuestos=[
            ("1R-1808", "FILTRO ACEITE MOTOR", 1, C250),
            ("1R-0762", "FILTRO COMBUSTIBLE", 2, C250),
            ("326-1644", "FILTRO SEPARADOR AGUA COMBUSTIBLE", 1, C250),
            ("2040TN", "FILTRO RACORD", 1, C250),
            ("142-1339", "FILTRO AIRE PRIMARIO", 1, C250),
            ("3E-9713", "ACEITE MOTOR 15W 40 - BALDE", 5, C250),
            ("3E-9902", "ACEITE MOTOR 15W 40 - GALON", 1, C250),
            ("142-1404", "FILTRO AIRE SECUNDARIO", 1, C500),
            ("093-7521", "FILTRO HIDRAULICO DRENAJE", 1, C500),
            ("5I-8670", "FILTRO HIDRAULICO PILOTO", 1, C500),
            ("179-9806", "FILTRO HIDRÁULICO RETORNO", 1, C500),
            ("095-1681", "SELLO DE FILTRO HIDRÁULICO", 1, C500),
            ("293-1183", "ELEMENTO FILTRO AIRE CABINA", 1, C1000),
            ("546-0006", "FILTRO AIRE ACONDICIONADO", 1, C1000),
            ("285-4106", "EMPAQUETADURA TAPA BALANCINES", 1, C1000),
            ("7F-8268", "SELLO RESPIRADERO MOTOR DIESEL", 1, C1000),
            ("4H-6112", "RESPIRADERO MOTOR DE GIRO", 1, C1000),
            ("227-0590", "RESPIRADERO TANQUE HIDRAULICO", 1, C1000),
            ("8T-9576", "ACEITE MANDOS FINALES Y MOTOR GIRO SAE 50 - BALDE", 2, C1000),
            ("309-6931", "ACEITE HIDRAULICO SAE 10 - BALDE", 12, C2000),
        ],
    ),
    _equipo(
        "330D2L",
        tipo="EXCAVADORA",
        marca="CATERPILLAR",
        serie="RCK00279",
        motor_modelo="C7",
        motor_serie="E7A04793",
        anio=2016,
        ciclo=CICLO_2000,
        repuestos=[
            ("322-3155", "FILTRO ACEITE MOTOR", 1, C250),
            ("360-8960", "FILTRO COMBUSTIBLE", 2, C250),
            ("438-5386", "FILTRO SEPARADOR AGUA COMBUSTIBLE", 1, C250),
            ("2040TN", "FILTRO RACORD", 1, C250),
            ("6I-2503", "FILTRO AIRE PRIMARIO", 1, C250),
            ("3E-9713", "ACEITE MOTOR 15W 40 - BALDE", 5, C250),
            ("3E-9902", "ACEITE MOTOR 15W 40 - GALON", 1, C250),
            ("6I-2504", "FILTRO AIRE SECUNDARIO", 1, C500),
            ("093-7521", "FILTRO HIDRAULICO DRENAJE", 1, C500),
            ("5I-8670", "FILTRO HIDRAULICO PILOTO", 1, C500),
            ("179-9806", "FILTRO HIDRÁULICO RETORNO", 1, C500),
            ("095-1681", "SELLO DE FILTRO HIDRÁULICO", 1, C500),
            ("327-6618", "ELEMENTO FILTRO AIRE CABINA", 1, C1000),
            ("293-1137", "FILTRO AIRE ACONDICIONADO", 1, C1000),
            ("527-1641", "EMPAQUETADURA TAPA BALANCINES", 1, C1000),
            ("326-7289", "SELLO RESPIRADERO MOTOR DIESEL", 1, C1000),
            ("4H-6112", "RESPIRADERO MOTOR DE GIRO", 1, C1000),
            ("227-0590", "RESPIRADERO TANQUE HIDRAULICO", 1, C1000),
            ("8T-9576", "ACEITE MANDOS FINALES Y MOTOR GIRO SAE 50 - BALDE", 2, C1000),
            ("309-6931", "ACEITE HIDRAULICO SAE 10 - BALDE", 12, C2000),
        ],
    ),
    _equipo(
        "420F2",
        tipo="RETROEXCAVADORA",
        marca="CAT",
        serie="LBS00193",
        motor_modelo="3054C - C4.4",
        motor_serie="G4D55509",
        anio=2016,
        ciclo=CICLO_2000,
        repuestos=[
            ("7W-2326", "FILTRO DE ACEITE DE MOTOR", 1, C250),
            ("1R-1804", "FILTRO DE COMBUSTIBLE", 1, C250),
            ("460-0310", "FILTRO SEPARADOR DE COMBUSTIBLE", 1, C250),
            ("528-0585", "FILTRO DE AIRE PRIMARIO", 1, C250),
            ("3E-9902", "ACEITE DE MOTOR 15W40 - 1G", 3, C250),
            ("346-6688", "FILTRO DE AIRE SECUNDARIO", 1, C500),
            ("362-1163", "ELEMENTO DE FILTRO HIDRAULICO", 1, C500),
            ("471-7003", "FILTRO DE TRANSMISION", 1, C500),
            ("8T-9572", "ACEITE DE TRANSMISION SAE 30 - 5G", 1, C1000),
            ("105-3335", "ACEITE MULTIPROPÓSITO - 5G", 2, C1000),
            ("417-8134", "FILTRO DE CABINA", 1, C2000),
            ("211-2660", "FILTRO DE AIRE ACONDICIONADO", 1, C2000),
            ("9R-9925", "RESPIRADERO HIDRAULICO", 1, C2000),
            ("9G-5127", "RESPIRADERO DE TRANSMISION", 1, C2000),
            ("275-9883", "SELLO DE TAPON DE CARTER", 1, C2000),
            ("055-1990", "RESPIRADERO DEL DIFERENCIAL POSTERIOR", 1, C2000),
            ("225-6451", "EMPAQUETADURA DE LA TAPA DE BALANCINES", 1, C2000),
            ("309-6931", "ACEITE HIDRAULICO ADV10W - 5G", 3, C2000),
            ("390-0536", "FAJA DE ACCESORIOS", 1, C2000),
        ],
    ),
]

EQUIPOS_POR_ID = {e["id"]: e for e in EQUIPOS}


def catalogo_publico() -> dict:
    return {
        "leyenda": [{"pm": pm, "label": label} for pm, label in LEYENDA_PM.items()],
        "equipos": deepcopy(EQUIPOS),
    }


def frecuencia(equipo: dict, horas: int) -> dict | None:
    """Columna del ciclo del equipo para esas horas (p. ej. 1000 → PM3)."""
    return next((f for f in equipo["frecuencias"] if f["horas"] == horas), None)


def normalizar_parte(numero: str | None) -> str:
    return "".join((numero or "").split()).upper()


def partes_programadas(equipo: dict, horas: int) -> set[str]:
    """N° de parte que la hoja marca con X en esa columna del ciclo."""
    return {normalizar_parte(r["numero_parte"]) for r in equipo["repuestos"] if horas in r["horas"]}


def proximo(equipo: dict, horas: int, horometro: float | None) -> dict | None:
    """Siguiente PM del ciclo después del hecho a esas horas, con el horómetro estimado si se conoce."""
    columnas = equipo["frecuencias"]
    idx = next((i for i, f in enumerate(columnas) if f["horas"] == horas), None)
    if idx is None:
        return None
    siguiente = columnas[(idx + 1) % len(columnas)]
    faltan = (siguiente["horas"] - horas) % equipo["ciclo_horas"]
    return {
        "pm": siguiente["pm"],
        "frecuencia_horas": siguiente["horas"],
        "horometro": round(float(horometro) + faltan, 1) if horometro is not None else None,
    }
