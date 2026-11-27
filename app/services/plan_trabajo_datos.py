"""Listas de la hoja DATOS de los Excel "BASE DE DATOS CONVENCIONAL" y "BASE DE DATOS DE EQUIPOS".

Son las opciones del formulario de Plan trabajo y lo que valida el servidor. Cada registro guarda
una copia de lo elegido (labor, tarea, máquina...) para que no cambie si estas listas cambian.
"""

from __future__ import annotations

from copy import deepcopy

TURNOS = [{"valor": "Dia", "label": "Día"}, {"valor": "Noche", "label": "Noche"}]

GUARDIAS = [
    {"codigo": "G-1", "jefe": "ING. EGUIL RHONI DIAZ DIAZ"},
    {"codigo": "G-2", "jefe": "ING. EGUIL RHONI DIAZ DIAZ"},
    {"codigo": "G-3", "jefe": "ING. EGUIL RHONI DIAZ DIAZ"},
]


def _labor(codigo, labor, fase, unidad, nivel, meta, seccion, programa_m) -> dict:
    return {
        "codigo": codigo,
        "labor": labor,
        "fase": fase,
        "unidad": unidad,
        "nivel": nivel,
        "meta": meta,
        "seccion": seccion,
        "programa_m": programa_m,
    }


# PROGRAMA DEL MES: lo que el Excel trae con BUSCARV a partir del código de la labor.
LABORES = [
    _labor("SN-3E", "Sub Nivel 3 Este", "Exploracion", "Enrique", 270, "META 1", "1 x 1.7", 30),
    _labor("SN-3W", "Sub Nivel 3 Oeste", "Exploracion", "Enrique", 270, "META 1", "1.2 x 1.9", 30),
    _labor("PQ1", "Pique principal", "Exploracion", "Enrique", 302, "META 1", "2.5 x 2", 76),
    _labor("PQ2", "Pique N°2", "Exploracion", "Enrique", 302, "META 2", "2.5 x 1.5", 76),
    _labor("CH-V", "Chimenea de ventilacion", "Exploracion", "Efrain", 303, "META 1", "1.2 x 1.2", 48),
    _labor("ST", "Estocada", "Preparacion", "Efrain", 303, "META 1", "1.5 x 1.7", 5),
    _labor("GL-195", "Galeria 195", "Preparacion", "Efrain", 303, "META 1", "2.5 X 2", None),
    _labor("PQE-1", "Pique Principal", "Exploracion", "Efrain", 303, "META 1", "2.5 X 1.5", 76),
    _labor("SN-4E", "Sub Nivel 4 Este", "Exploracion", "Enrique", 256, "META 1", "1x1.7", 6),
    _labor("SN-4W", "Sub Nivel 4 Oeste", "Exploracion", "Enrique", 256, "META 1", "1x1.7", 0),
    _labor("SN2", "Sub Nivel 2 Oeste", "Exploracion", "Enrique", 280, "META 2", "1 x 1.7", 35),
    _labor("SN3", "Sub Nivel 3 Oeste", "Exploracion", "Enrique", 292, "META 2", "2 x 1.7", 35),
    _labor("SNE-1E", "Sub Nivel 1 Este", "Exploracion", "Efrain", 288, "META 1", "1 x 1.7", 30),
    _labor("SNE-1O", "Sub Nivel 1 Oeste", "Exploracion", "Efrain", 289, "META 1", "1 x 1.7", 30),
    _labor("PQ3", "Pique N°3", "Exploracion", "Enrique", 302, "META 3", "2.5 X 1.5", 60),
    _labor("SN-1", "Sub Nivel 1", "Exploracion", "Enrique", 285, "META 3", "1x1.7", 17),
    _labor("SN-6E", "Sub Nivel 6 Este", "Exploracion", "Enrique", 228, "META 1", "1 x 1.7", 70),
    _labor("SN-6W", "Sub Nivel 6 Oeste", "Exploracion", "Enrique", 228, "META 1", "1 x 1.7", 50),
    # En el Excel la fila de SN-2 copia con fórmulas los datos de SN-1.
    _labor("SN-2", "Sub Nivel 1", "Exploracion", "Enrique", 285, "META 3", "1x1.7", 17),
]

MAESTROS = [
    "LLAPO RIVEROS Sansinio",
    "ROJAS TAMBO Nain",
    "YPARRAGUIRRE RODRIGUEZ Idan",
    "MAURICIO VASQUEZ Oscar",
    "AUX. JOSE TAPIA",
]

TAREAS = [
    {"codigo": codigo, "tarea": tarea}
    for codigo, tarea in [
        ("SS", "Sost. Split Set"),
        ("CM", "Sost. Cuadros de madera"),
        ("CB", "Sost. Cimbras"),
        ("ME", "Sost. Malla Electrosoldada"),
        ("PL", "Sost. Puntales en linea"),
        ("PS", "Sost. Puntal de seguridad"),
        ("PV", "Perforacion y Voladura"),
        ("AT", "Armado de tolva"),
        ("LC", "Limpieza de desmonte"),
        ("LM", "Limpieza de mineral"),
        ("RT", "Recarga de taladros"),
        ("PAV", "Puntal de avance"),
        ("PB", "Plasteo de bulones"),
    ]
]

MATERIALES = [{"codigo": "D", "material": "Desmonte"}, {"codigo": "M", "material": "Mineral"}]

TIPOS_PERFORACION = [
    {"codigo": "F", "tipo": "Frente"},
    {"codigo": "D", "tipo": "Desquinche"},
    {"codigo": "S", "tipo": "Sostenimiento"},
    {"codigo": "SE", "tipo": "Servicios"},
]

# Equipos de perforación que ya aparecen en la base (la columna EQUIPO no tiene lista en el Excel).
EQUIPOS_PERFORACION_SUGERIDOS = ["RNP"]


def _grupo(titulo: str, items: list[tuple[str, str]]) -> dict:
    return {"titulo": titulo, "items": [{"id": i, "label": label} for i, label in items]}


# Columnas de cantidades de la base convencional, en el orden del Excel.
INSUMOS = [
    _grupo("Aceros de perforación", [
        ("broca_36", "BROCA DE 36 mm"),
        ("broca_38", "BROCA DE 38 mm"),
        ("barreno_2", "BARRENO DE 2'"),
        ("barreno_4", "BARRENO DE 4'"),
        ("barreno_6", "BARRENO DE 6'"),
        ("barreno_8", "BARRENO DE 8'"),
    ]),
    _grupo("Voladura", [
        ("emulnor_3000", 'EMULNOR 3000 7/8" x 7"'),
        ("emulnor_5000", 'EMULNOR 5000 7/8" x 7"'),
        ("anfo", "ANFO"),
        ("mecha_rapida", "MECHA RAPIDA"),
        ("carmex_15", "CARMEX 1.5"),
        ("carmex_18", "CARMEX 1.8"),
        ("carmex_21", "CARMEX 2.1"),
    ]),
    _grupo("Sostenimiento", [
        ("puntal_5", 'PUNTAL 5" Ø'),
        ("puntal_6", 'PUNTAL 6" Ø'),
        ("puntal_7", 'PUNTAL 7" Ø'),
        ("puntal_8", 'PUNTAL 8" Ø'),
        ("tablas", "TABLAS"),
        ("escalera_4m", "ESCALERA 4M"),
        ("mini_split_set", "MINI SPLIT SET"),
        ("split_set_5", "SPLIT SET 5"),
        ("split_set_7", "SPLIT SET 7"),
        ("jack_pot_6", "JACK POT 6"),
        ("jack_pot_7", "JACK POT 7"),
        ("jack_pot_8", "JACK POT 8"),
        ("malla_electrosoldada", "MALLA ELECTROSOLDADA"),
        ("cimbra", "CIMBRA"),
    ]),
]
INSUMOS_IDS = [item["id"] for grupo in INSUMOS for item in grupo["items"]]

MAQUINAS = [
    {"codigo": "CN-AC01", "equipo": "Compresora Neumatica", "marca": "ATLAS COPCO", "modelo": "XAVS 400"},
    {"codigo": "GE-M01", "equipo": "Grupo Electrico", "marca": "MODASA", "modelo": "MP-251"},
    {"codigo": "CN-S01", "equipo": "Compresora Neumatica", "marca": "SULLAIR", "modelo": "185H"},
]

GUARDIAS_POR_CODIGO = {g["codigo"]: g for g in GUARDIAS}
LABORES_POR_CODIGO = {lab["codigo"]: lab for lab in LABORES}
TAREAS_POR_CODIGO = {t["codigo"]: t for t in TAREAS}
MATERIALES_POR_CODIGO = {m["codigo"]: m for m in MATERIALES}
TIPOS_POR_CODIGO = {t["codigo"]: t for t in TIPOS_PERFORACION}
MAQUINAS_POR_CODIGO = {m["codigo"]: m for m in MAQUINAS}
TURNOS_VALORES = {t["valor"] for t in TURNOS}


def catalogo_publico() -> dict:
    return deepcopy(
        {
            "turnos": TURNOS,
            "guardias": GUARDIAS,
            "labores": LABORES,
            "maestros": MAESTROS,
            "tareas": TAREAS,
            "materiales": MATERIALES,
            "tipos_perforacion": TIPOS_PERFORACION,
            "equipos_perforacion": EQUIPOS_PERFORACION_SUGERIDOS,
            "insumos": INSUMOS,
            "maquinas": MAQUINAS,
        }
    )
