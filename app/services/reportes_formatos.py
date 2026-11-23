"""Definición de los formatos de reporte operativo (cara y reverso).

Cada formato describe sus secciones; el mismo esquema alimenta el formulario
del frontend, la validación del servidor y el PDF impreso a medida.
"""

from __future__ import annotations

from copy import deepcopy

A4_VERTICAL = {"ancho_mm": 210, "alto_mm": 297, "etiqueta": "A4 vertical (21 × 29.7 cm)", "a4": True}
A4_HORIZONTAL = {"ancho_mm": 297, "alto_mm": 210, "etiqueta": "A4 horizontal (29.7 × 21 cm)", "a4": True}

TURNOS = ["Primer turno", "Segundo turno"]
SI_NO = ["SI", "NO"]


def campo(id_: str, label: str, tipo: str = "text", span: int = 1, **extra) -> dict:
    return {"id": id_, "label": label, "tipo": tipo, "span": span, **extra}


def col(id_: str, label: str, tipo: str = "text", ancho: float = 1.0, **extra) -> dict:
    return {"id": id_, "label": label, "tipo": tipo, "ancho": ancho, **extra}


def campos(titulo: str | None, *items: dict) -> dict:
    return {"tipo": "campos", "titulo": titulo, "campos": list(items)}


def tabla(id_: str, titulo: str | None, filas: int, columnas: list[dict], **extra) -> dict:
    return {"tipo": "tabla", "id": id_, "titulo": titulo, "filas": filas, "columnas": columnas, **extra}


def personal(id_: str, titulo: str, filas: int, *, cargo: bool = True, extra_cols: list[dict] | None = None) -> dict:
    cols = [
        col("dni", "DNI", ancho=1.6, max=12),
        col("ap_paterno", "Apellido paterno", ancho=2.4),
        col("ap_materno", "Apellido materno", ancho=2.4),
        col("nombres", "Nombres", ancho=2.6),
    ]
    if cargo:
        cols.append(col("cargo", "Cargo", ancho=1.8))
    cols += extra_cols or []
    cols.append(col("firma", "Firma", ancho=1.8, solo_impresion=True))
    return tabla(id_, titulo, filas, cols, numerar=False)


def catalogo(titulo: str, grupos: list[tuple[str, list[tuple[str, str]]]], columnas: int = 2) -> dict:
    return {
        "tipo": "catalogo",
        "titulo": titulo,
        "columnas": columnas,
        "grupos": [{"titulo": t, "items": [{"codigo": c, "descripcion": d} for c, d in items]} for t, items in grupos],
    }


DEMORAS_OPERATIVAS_BASE = [
    ("DO01", "DESPLAZ OPERADOR INI/FIN GUARDIA"),
    ("DO02", "REPARTO GUARDIA"),
    ("DO03", "CHECKLIST DE EQ (POR OPERADOR)"),
    ("DO04", "ACOMODO EQUIPO FINAL GUARDIA"),
    ("DO05", "ESPERA DE ÁREA"),
    ("DO06", "FALTA DESATE MANUAL/MECANIZADO"),
    ("DO07", "FALTA LIMPIEZA FRENTE DE TRABAJO"),
    ("DO08", "FALTA VENTILAC. FRENTE DE TRABAJO"),
    ("DO09", "LABOR INUNDADA"),
    ("DO10", "VÍA INTERRUMPIDA / TRÁNSITO"),
    ("DO11", "REUBICA LAB/CAMBIO DE ORIGEN"),
    ("DO12", "TRASLADO EQUIPO AL FRENTE"),
    ("DO13", "TRASLADO EQUIPO A OTRA ZONA"),
]
DEMORAS_NO_OPERATIVAS = [
    ("DN01", "DICTADO DE CHARLAS"),
    ("DN02", "INSPECCIÓN DE SEGURIDAD"),
    ("DN03", "LIMPIEZA DE EQUIPO"),
    ("DN04", "NECESIDADES PERSONALES"),
    ("DN05", "REFRIGERIO"),
    ("DN06", "OTRAS DEMORAS"),
]
MANTENIMIENTO = [
    ("MP01", "INSPECCIÓN DE EQUIPO (POR MANTTO)"),
    ("MP02", "MTO PREVENTIVO PROGRAMADO"),
    ("MC02", "MTO CORRECTIVO MECÁNICO"),
    ("MC03", "MTO CORRECTIVO LLANTAS"),
    ("MC04", "MTO CORRECTIVO TRANSMISIÓN"),
    ("MC05", "MTO CORRECTIVO HIDRÁULICO"),
    ("MC06", "MTO CORRECTIVO ELÉCTRICO"),
]

CATALOGO_EQUIPO_PESADO = catalogo(
    "Códigos de actividad",
    [
        ("SCOOP - TIEMPO EFECTIVO (operativo)", [
            ("OP-01", "LIMPIEZA DE MINERAL"),
            ("OP-02", "LIMPIEZA DE DESMONTE"),
            ("OP-03", "LIMPIEZA DE EVALUACIÓN"),
            ("OP-04", "LIMPIEZA DE BAJA LEY"),
            ("OP-05", "LIMPIEZA DE FINOS"),
            ("OP-06", "LIMPIEZA A CÁMARA DE ACUMULACIÓN"),
            ("OP-07", "RELLENO DE TAJO"),
            ("OP-08", "LIMPIEZA DE REBATIDO"),
        ]),
        ("SCOOP - TIEMPO EFECTIVO (servicios)", [
            ("SE-01", "CARGUÍO - MINERAL A VOLQUETE"),
            ("SE-02", "CARGUÍO - DESMONTE A VOLQUETE"),
            ("SE-03", "CARGUÍO - EVALUACIÓN A VOLQUETE"),
            ("SE-04", "CARGUÍO - BAJA LEY A VOLQUETE"),
            ("SE-05", "CARGUÍO - FINOS A VOLQUETE"),
            ("SE-06", "CARGUÍO - MINERAL A DUMPER"),
            ("SE-07", "CARGUÍO - DESMONTE A DUMPER"),
            ("SE-08", "CARGUÍO - EVALUACIÓN A DUMPER"),
            ("SE-09", "CARGUÍO - BAJA LEY A DUMPER"),
            ("SE-10", "CARGUÍO - FINOS A DUMPER"),
            ("SE-11", "RELLENO DE GALERÍA"),
            ("SE-12", "RELLENO DE CRUCERO"),
            ("SE-13", "LIMPIEZA REBOTE MAT SHOTCRETE"),
            ("SE-14", "LIMPIEZA DESMONTE LAB REHABILITACIÓN"),
            ("SE-15", "LIMPIEZA DE PARRILLA"),
            ("SE-16", "ALQUILER DE SCOOP POR SERVICIOS"),
            ("SE-18", "TRASLADOS DE EQUIPO HACIA LABOR (PAGO)"),
        ]),
        ("SCOOP - TELEHANDLER TIEMPO EFECT (generales)", [
            ("GN-03", "APOYO A OTRA EE SEPROCAL"),
            ("GN-04", "APOYO A OTRA EE CRISTOBAL"),
            ("GN-07", "APOYO A OTRA EE CONSEM"),
            ("GN-08", "APOYO A OTRA EE CORIMAYO"),
            ("GN-09", "APOYO A OTRA EE SFP"),
            ("GN-11", "APOYO A OTRA EE SAN FRANCISCO"),
            ("GN-12", "APOYO A OTRA EE MINERALIS"),
            ("208", "NO PROCEDE"),
            ("230", "OTRAS ACTIVIDADES (Describir)"),
        ]),
        ("TELEHANDLER - TIEMPO EFECTIVO", [
            ("211-A12", "SE-APOYO A RELLENO HIDRÁULICO"),
            ("214-A16", "SE-APOYO A EXPLOSIVOS - TH"),
            ("214-A18", "SE-APOYO A LEVANTE DE TUBERÍA"),
            ("213-A2", "SE-APOYO A MANTENIMIENTO-MN"),
            ("211-A13", "SE-APOYO A SUB ESTACIÓN"),
            ("211-A6", "SE-APOYO A VENTILACIÓN"),
            ("211-A5", "SE-APOYO CAUSE DE BOMBA"),
            ("214-A19", "SE-APOYO PERSONAL PASIVOS"),
            ("214-A11", "SE-LIMPIEZA DE CUNETA"),
            ("211-A7", "SE-LIMP DE MATERIALES Y EQUIPOS"),
            ("211-A1", "SE-PROLONG DE MANGA DE VENTILAC."),
            ("204-F", "SE-TRASLADO DE BOMBA"),
            ("204-A", "SE-TRASLADO DE CABLE ELÉCTRICO"),
            ("204-B", "SE-TRASLADO DE TUBERÍA - REDES"),
            ("204-I", "SE-TRASLADO DE VENTILADOR"),
            ("SE-18", "TRASLADO EQUIP HACIA LABOR (PAGO)"),
        ]),
        ("DUMPER - TIEMPO EFECTIVO (operativo)", [
            ("OP-11", "TRANSPORTE DE MINERAL"),
            ("OP-12", "TRANSPORTE DE DESMONTE"),
            ("OP-13", "TRANSPORTE DE EVALUACIÓN"),
            ("OP-14", "TRANSPORTE DE BAJA LEY"),
        ]),
        ("DUMPER - TIEMPO EFECTIVO (servicios)", [
            ("SE-17", "ALQUILER DE DUMPER POR SERVICIOS"),
            ("SE-18", "TRASLADOS DE EQUIPO A LABOR (PAGO)"),
        ]),
        ("MINICARGADOR - TIEMPO EFECTIVO", [
            ("225-A", "LIMPIEZA VIA MINICARG & TRACT"),
            ("225-B", "LIMPIEZA VIA MINICARGADOR"),
            ("213-A7", "SE - ABAST DE TOLVA PL"),
        ]),
        ("TRACTOR - TIEMPO EFECTIVO", [
            ("225-A", "LIMPIEZA VIA MINICARG & TRACT"),
            ("225-C", "LIMPIEZA VIA TRACTOR"),
            ("213-A7", "SE - ABAST DE TOLVA PL"),
        ]),
        ("DEMORAS OPERATIVAS", DEMORAS_OPERATIVAS_BASE + [("DO62", "ABASTECIMIENTO DE COMBUSTIBLE")]),
        ("DEMORAS NO OPERATIVAS", DEMORAS_NO_OPERATIVAS),
        ("ACTIVIDADES DE MANTENIMIENTO", MANTENIMIENTO),
    ],
    columnas=2,
)

CATALOGO_JUMBO = catalogo(
    "Códigos de actividad",
    [
        ("TIEMPO EFECTIVO", [
            ("PE-01", "PERFORACIÓN DE TALADROS"),
            ("PE-02", "PERCUTADO"),
            ("PE-03", "DESQUINCHE"),
            ("SO-01", "INSTALACIÓN DE PERNOS"),
        ]),
        ("DEMORAS OPERATIVAS", DEMORAS_OPERATIVAS_BASE + [
            ("DO54", "FALTA DE AGUA"),
            ("DO56", "FALTA DE ENERGÍA ELÉCTRICA"),
            ("DO57", "FALTA O BAJA PRESIÓN DE AIRE"),
            ("DO62", "ABASTECIMIENTO DE COMBUSTIBLE"),
        ]),
        ("DEMORAS NO OPERATIVAS", DEMORAS_NO_OPERATIVAS),
        ("MANTENIMIENTO", MANTENIMIENTO),
    ],
    columnas=4,
)

RETARDOS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 18, 20, 24, 32, 40, 48, 56, 72, 95,
            120, 140, 180, 220, 240, 288, 340, 360, 400]

CONDICIONES_PARE = [
    "Garganta de RB taponeada por la carga rimada.",
    "Chimenea Alimak con Alicab inoperativo.",
    "Chimenea campaneada con o sin presencia de agua.",
    "Presencia de cuñas o fallas paralelas a la excavación.",
    "Falla de loza de madera o concreto al recuperar puentes o pilares.",
    "Labor derrumbada y/o con presencia de bancos suspendidos.",
    "Pilar o puente craquelado, con rajaduras o fatigado. Con presencia de agua.",
    "Roca inestable después del tercer desatado.",
    "Altura de puente menor a 5 metros.",
    "Calidad de roca mala con filtraciones de agua.",
    "Alimak sin sistema de iniciación por chispeo eléctrico a partir de 5 mts de altura.",
    "Presencia de más de 3 tiros cortados.",
    "Presencia cercana de labores antiguas saturadas con agua.",
    "Mayor flujo y presión de agua en los taladros durante la perforación.",
    "Labor inundada.",
    "Labor sin pasaporte o incumplimiento de la secuencia de minado.",
    "Jaula de Alimak sin techo guardacabeza y barandas de protección.",
    "Sistema de comunicación Alimak inoperativo o radios handy inoperativos.",
    "Falla en los frenos o dirección del equipo.",
    "Inducción eléctrica en los equipos o maquinarias.",
    "Labor realzada con chispeo continuo de rocas.",
    'Tres condiciones de "ABC" presentes en la labor a la vez.',
]
CONDICIONES_ABC = [
    "Labor sin sostenimiento mayor a 8 horas.",
    "Incumplimiento de recomendación geomecánica.",
    "Altura de desatado mayor o igual a 5 metros.",
    "Incumplimiento del pasaporte (no contempla secuencia de minado).",
    "Labor realzada más de 2 m.",
    "Sostenimiento incompleto, craquelado, rendido, roto, caído, mal instalado.",
    "Disparos sin contar con sostenimiento al tope.",
    "Chimenea Alimak con flujo deficiente o nulo de aire.",
    "Tableros eléctricos sin línea a tierra.",
    "Presencia de fogonazos o chispeos eléctricos en el área de trabajo.",
    "Chimenea sin parrilla o malla de protección.",
    "Parrillas desoldadas o rotas.",
    "Faros, alarmas, circulinas y claxon de equipos inoperativos (quemados).",
    "Presencia de 1 a 3 tiros cortados.",
    "Paralización de bombas de agua.",
    "Temperatura de labor mayor a 30 ºC.",
    "Visibilidad deficiente por presencia de gases de combustión o polvo.",
    "Pestaña de los aros de llantas rajados y sin seguros.",
    "Distancia de conexión de labores menor o igual a 15 metros.",
]

CRITERIOS_VEO = [
    ("APLASTAMIENTO", [
        ("1", "Guardacabeza metálico sólido, no rajado, no abollado.", "A"),
    ]),
    ("CAÍDA DE PERSONAL DE ALTURA", [
        ("2", "Cuenta con estribos antideslizantes fijos, no rotos, no desoldados, no abollados y adecuados.", "M"),
    ]),
    ("CHOQUE", [
        ("3", "Claxon, circulina y alarma de retroceso automático, en funcionamiento, no rotos, no dañados, no deteriorados y visibles.", "A"),
        ("4", "Conductor u operador porta su autorización vigente para conducir u operar dicho vehículo o equipo.", "A"),
        ("5", "Cuenta con 02 conos de PVC de 71 cm de altura, con 03 cintas blancas reflectivas cada uno, no rotos, no deteriorados, no abollados y en su portaconos no desoldado.", "A"),
        ("6", 'Cuenta con numeración y cintas reflectivas en lados frontal/laterales/posterior y de advertencia "Mantenga su distancia a 15 mts", de acuerdo a estándar, no sucias, no rotas, no deterioradas y visible.', "A"),
        ("7", "Faros delanteros y posteriores en funcionamiento, con micas, no rotos, no rajados, no malogrados.", "A"),
        ("7a", "Los neumáticos tienen las cocadas adecuadas como mínimo 5 mm.", ""),
        ("7b", "El equipo cuenta con barra luminosa para su traslado por las vías principales.", ""),
        ("8", "Neumáticos con espárragos y tuercas completos y ajustados. Cuenta con seguro de pestaña.", "A"),
        ("9", "Pines y bocinas del brazo, articulación central y dirección, no rotos, no rajados, no desgastados.", "A"),
        ("10", "Realiza el chequeo de preuso (Check List o vuelta de gallo).", "A"),
    ]),
    ("CONTAMINACIÓN DE AGUA - SUELO", [
        ("11", "Cuenta con kit antiderrame de hidrocarburos según estándar, visible, con tarjeta y firma de inspección del mes correspondiente.", "M"),
        ("12", "Mangueras hidráulicas del sistema de perforación no rotas, no deterioradas, brazo hidráulico sin fugas y sin roturas.", "M"),
    ]),
    ("ELECTROCUCIÓN", [
        ("13", "Cables eléctricos de alimentación cuentan con enchufe de 03 salidas de 175 amperios y 01 a tierra de 110 amperios, sin empalmes, no pelados, no dañados, no desgastados.", "A"),
        ("14", "Colector de cable, no roto, no doblado.", "A"),
        ("15", "Cuenta con 02 portacables como mínimo, no rotos, no desoldados.", "A"),
        ("16", "Switch master señalizado, no roto, no deteriorado y adecuado para bloqueo.", "A"),
        ("17", "Vehículo o equipo cuenta con cadena puesta a tierra.", "A"),
    ]),
    ("GOLPES POR OBJETOS", [
        ("18", "Brazo, viga, perforadora y shank adapter, no chocados, no rotos, no desgastados.", "M"),
        ("19", "Chasis del equipo con uniones soldadas, no rajado, no abollado.", "M"),
        ("20", "Cilindros de levante no rajados y sin fugas.", "M"),
        ("21", "Conexiones de mangueras de agua se encuentran con bushing y abrazaderas.", "M"),
        ("22", "Cuba de Mixer cuenta con guarda, no rota, no deteriorada, no desoldada.", "A"),
        ("23", "Tienen/usan casco con barbiquejo, lámpara minera, tapón de oídos, lentes de seguridad, respirador con filtros y cartuchos, no saturados de acuerdo a la actividad, no rayados, no rotos, no deteriorados.", "M"),
        ("24", "Tienen/usan guantes de cuero/neoprene, chaleco y/o camisaco y pantalón con cintas reflectivas, zapatos y/o botas de jebe con punta de acero, de acuerdo a la actividad, no rotos, no deteriorados.", "M"),
    ]),
    ("GASEAMIENTO", [
        ("25", "Extintor PQS codificado y ubicado según estándar, de 04 kg para combi, 06 kg para camioneta y buses, 09 kg para camiones, volquetes y equipos.", "M"),
        ("26", "Extintor PQS no chocado, no dañado, con tarjeta y firma de inspección del mes correspondiente, aguja de manómetro en franja verde, precinto y pin, no rotos, fácil de retirar.", "M"),
    ]),
    ("LUMBALGIA", [
        ("27", "Asiento del equipo cuenta con amortiguación, cinturón de seguridad, no rotos, no desgastados ni descocido.", "M"),
    ]),
    ("VOLCADURA", [
        ("28", 'Cuentan con 02 cuñas de poliuretano para vehículos livianos de 7"x6"x8.25", vehículos y equipos pesados de 8"x8"x11", no rotas, no deterioradas, en su porta cuñas no desoldado.', "A"),
        ("29", "Frenos de servicio y parqueo, regulados, no malogrados, no invertidos.", "A"),
        ("30", "Gatas hidráulicas de fijación no chocadas y sin fugas.", "A"),
    ]),
]

FALLAS_CICLO = [
    "Acceso a labor", "Tráfico de equipos", "Falta de personal",
    "Bomba inoperativa", "Ventilación defectuosa", "Falta supervisión",
    "Condición sub estándar", "Falta de aire", "Labor lejana",
    "Equipos inoperativos", "Falta de agua", "Falta desatado",
    "Espera relleno hidráulico", "Falta de energía", "Labor inundada",
    "Material defectuoso", "Falta de equipos", "Espera del equipo",
    "No hay material", "Falta de madera", "Falta de percutado",
    "Terreno incompetente", "Falta de herramientas",
]


FORMATOS: list[dict] = [
    {
        "id": "rpe",
        "codigo": "RPE",
        "titulo": "Reporte de Equipo Pesado Mina",
        "prefijo": "RPE 23-",
        "digitos": 6,
        "inicio": 5001,
        "papel": {"ancho_mm": 230, "alto_mm": 296, "etiqueta": "23 × 29.6 cm", "a4": False},
        "material": "Autocopiativo original + 1 copia · Talonario de 100 juegos",
        "resumen": {"equipo": "codigo_equipo", "responsable": ("personal", ["nombres", "ap_paterno"])},
        "cara": [
            campos(
                "Datos generales",
                campo("fecha", "Fecha", "date", requerido=True, auto="hoy"),
                campo("turno", "Turno", "radio", opciones=["Primero", "Segundo"]),
                campo("empresa", "Empresa especializada", span=2, recordar=True),
                campo("mina", "Mina", recordar=True),
                campo("zona", "Zona", recordar=True),
                campo("proyecto", "Proyecto", recordar=True),
                campo("eq_operativo", "¿EQ queda operativo?", "radio", opciones=SI_NO),
                campo("codigo_equipo", "Código equipo"),
                campo("tipo_equipo", "Tipo de equipo", "radio", span=2,
                      opciones=["Scoop", "Dumper", "Telehandler", "Minicargador", "Otro"]),
                campo("otro_equipo", "Otro equipo (especificar)"),
            ),
            personal("personal", "Operadores", 2),
            campos(
                None,
                campo("orden_trabajo", "Orden de trabajo", "textarea", span=3, filas=4),
                campo("supervisor", "Supervisor / capataz (nombres y apellidos)", span=2),
                campo("supervisor_dni", "DNI supervisor", max=12),
            ),
            tabla(
                "detalle", "Detalle de actividades", 24,
                [
                    col("hora_inicial", "Inicial", "time", 1.6, grupo="HORAS"),
                    col("hora_final", "Final", "time", 1.6, grupo="HORAS"),
                    col("labor_origen", "Labor de origen", ancho=2.4),
                    col("labor_final", "Labor final", ancho=2.4),
                    col("min", "MIN", "number", 0.8, grupo="N° DE VIAJES OPERATIVOS", total=True),
                    col("desm", "DESM", "number", 0.8, grupo="N° DE VIAJES OPERATIVOS", total=True),
                    col("eval", "EVAL", "number", 0.8, grupo="N° DE VIAJES OPERATIVOS", total=True),
                    col("baja_ley", "BAJA LEY", "number", 0.8, grupo="N° DE VIAJES OPERATIVOS", total=True),
                    col("finos", "FINOS", "number", 0.8, grupo="N° DE VIAJES OPERATIVOS", total=True),
                    col("serv", "SERV", "number", 0.8, grupo="N° DE VIAJES OPERATIVOS", total=True),
                    col("codigo_act", "Código act.", "codigo", 1.8),
                    col("horometro_inicial", "Inicial", "number", 2.1, grupo="HORÓMETRO"),
                    col("horometro_final", "Final", "number", 2.1, grupo="HORÓMETRO"),
                    col("dsc", "DSC (-%)", "number", 1.9),
                ],
                ancho_item=0.8,
                fila_alto_mm=8,
            ),
            campos(
                None,
                campo("revision_cmh", "Revisión de CMH (nombres, apellidos y observaciones)", span=2),
                campo("revision_dni", "DNI", max=12),
            ),
        ],
        "reverso": [CATALOGO_EQUIPO_PESADO],
    },
    {
        "id": "rpeq18",
        "codigo": "RPEQ18",
        "titulo": "Reporte de Equipos Pesados por Frente y Turno",
        "prefijo": "RPEQ18-",
        "digitos": 9,
        "inicio": 1,
        "papel": A4_VERTICAL,
        "material": "Sin medida establecida · se imprime en A4",
        "resumen": {"equipo": "codigo_equipo", "responsable": ("personal", ["nombres", "ap_paterno"])},
        "cara": [
            campos(
                "Datos generales",
                campo("fecha", "Fecha", "date", requerido=True, auto="hoy"),
                campo("contrata", "Contrata especializada", span=2, recordar=True),
                campo("zona", "Zona", recordar=True),
                campo("mina", "Mina", recordar=True),
                campo("turno", "Turno", "radio", opciones=TURNOS),
                campo("hora_inicio", "Horario de operaciones · inicio", "time"),
                campo("hora_fin", "Horario de operaciones · fin", "time"),
            ),
            personal("personal", "Operadores", 2),
            campos(
                "Equipo",
                campo("tipo_equipo", "Tipo de equipo", "radio", opciones=["Scoop", "Dumper"]),
                campo("codigo_equipo", "Código del equipo"),
                campo("combustible", "Combustible (gal)", "number"),
                campo("horometro_inicial", "Horómetro inicial", "number"),
                campo("horometro_final", "Horómetro final", "number"),
                campo("aprobacion", "Firma aprobación (nombre)"),
                campo("orden_trabajo", "Orden de trabajo", "textarea", span=3, filas=4),
            ),
            tabla(
                "detalle", "Detalle por frente", 17,
                [
                    col("labor_origen", "Labor de origen", ancho=2.2),
                    col("labor_final", "Labor final", ancho=2.2),
                    col("min", "MIN", "number", 0.8, grupo="N° DE VIAJES OPERATIVOS", total=True),
                    col("desm", "DESM", "number", 0.8, grupo="N° DE VIAJES OPERATIVOS", total=True),
                    col("eval", "EVAL", "number", 0.8, grupo="N° DE VIAJES OPERATIVOS", total=True),
                    col("baja_ley", "BAJA LEY", "number", 0.9, grupo="N° DE VIAJES OPERATIVOS", total=True),
                    col("finos", "FINOS", "number", 0.8, grupo="N° DE VIAJES OPERATIVOS", total=True),
                    col("serv", "SERV", "number", 0.8, grupo="N° DE VIAJES OPERATIVOS", total=True),
                    col("codigo", "Código", "codigo", 1.4),
                    col("horometro_inicial", "Horómetro inicial", "number", 1.6),
                    col("horometro_final", "Horómetro final", "number", 1.6),
                    col("demora_inicial", "Hora inicial", "time", 1.2, grupo="HRS X DEMORA"),
                    col("demora_final", "Hora final", "time", 1.2, grupo="HRS X DEMORA"),
                ],
                fila_alto_mm=8,
            ),
        ],
        "reverso": [CATALOGO_EQUIPO_PESADO],
    },
    {
        "id": "rpcam",
        "codigo": "RPCAM23",
        "titulo": "Reporte de Servicios Camioneta",
        "prefijo": "RPCAM23-",
        "digitos": 6,
        "inicio": 12001,
        "papel": {"ancho_mm": 230, "alto_mm": 255, "etiqueta": "23 × 25.5 cm", "a4": False},
        "material": "Autocopiativo original + 1 copia · Block de 100 juegos",
        "resumen": {"equipo": "codigo_equipo", "responsable": ("personal", ["nombres", "ap_paterno"])},
        "cara": [
            campos(
                "Datos generales",
                campo("fecha", "Fecha", "date", requerido=True, auto="hoy"),
                campo("contrata", "Contrata", span=2, recordar=True),
                campo("actividad", "Actividad"),
                campo("area_transporte", "Área de transporte", recordar=True),
                campo("proyecto", "Proyecto", recordar=True),
                campo("hora_inicio", "Hora inicio de operaciones", "time"),
                campo("hora_fin", "Hora término de operaciones", "time"),
                campo("turno", "Turno", "radio", opciones=TURNOS),
                campo("km_inicio", "Kilometraje inicio", "number"),
                campo("km_final", "Kilometraje final", "number"),
            ),
            personal("personal", "Personal operador de servicio", 1, cargo=False),
            campos(
                None,
                campo("orden_trabajo", "Orden de trabajo", "textarea", span=2, filas=4),
                campo("grafico", "Gráfico / croquis (descripción)", "textarea", filas=4),
                campo("codigo_equipo", "Código de equipo"),
                campo("centro_costos", "Centro de costos", recordar=True),
                campo("km_abastecimiento", "Kilometraje de abast.", "number"),
                campo("petroleo_gln", "Petróleo (GLN)", "number"),
            ),
            tabla(
                "traslados", "Traslado personal y otros", 20,
                [
                    col("origen", "Traslado - origen", ancho=3.2, grupo="TRASLADO PERSONAL Y OTROS"),
                    col("destino", "Destino de traslado", ancho=3.2, grupo="TRASLADO PERSONAL Y OTROS"),
                    col("km_inicial", "Inicial", "number", 1.4, grupo="KILOMETRAJE"),
                    col("km_final", "Final", "number", 1.4, grupo="KILOMETRAJE"),
                    col("hora_inicio", "Inicio", "time", 1.4, grupo="HORAS NORMALES"),
                    col("hora_final", "Final", "time", 1.4, grupo="HORAS NORMALES"),
                    col("obs", "Obs.", ancho=1.4),
                ],
                ancho_item=0.7,
                fila_alto_mm=7,
            ),
        ],
        "reverso": None,
    },
    {
        "id": "roft",
        "codigo": "ROFT23",
        "titulo": "Reporte de Operaciones por Labor y Turno",
        "prefijo": "ROFT23-",
        "digitos": 6,
        "inicio": 30001,
        "papel": {"ancho_mm": 220, "alto_mm": 260, "etiqueta": "22 × 26 cm", "a4": False},
        "material": "Bond de 75 g · Block de 100 unidades",
        "resumen": {"equipo": "labor", "responsable": ("personal", ["nombres", "ap_paterno"])},
        "cara": [
            campos(
                "Datos generales",
                campo("fecha", "Fecha", "date", requerido=True, auto="hoy"),
                campo("turno", "Turno", "radio", opciones=TURNOS),
                campo("contrata", "Contrata especializada", recordar=True),
                campo("labor", "Labor minera trabajada", span=3),
            ),
            tabla(
                "personal", "Ciclo minado y personal en la labor", 8,
                [
                    col("rd", "R/D", "check", 0.6, grupo="CICLO MINADO"),
                    col("limp", "LIMP", "check", 0.6, grupo="CICLO MINADO"),
                    col("sost", "SOST", "check", 0.6, grupo="CICLO MINADO"),
                    col("perf", "PERF", "check", 0.6, grupo="CICLO MINADO"),
                    col("cd", "C/D", "check", 0.6, grupo="CICLO MINADO"),
                    col("dni", "DNI", ancho=1.2, grupo="PERSONAL EN LA LABOR", max=12),
                    col("ap_paterno", "Apellido paterno", ancho=1.8, grupo="PERSONAL EN LA LABOR"),
                    col("ap_materno", "Apellido materno", ancho=1.8, grupo="PERSONAL EN LA LABOR"),
                    col("nombres", "Nombres", ancho=1.6, grupo="PERSONAL EN LA LABOR"),
                    col("cargo", "Cargo", ancho=1.5, grupo="PERSONAL EN LA LABOR"),
                    col("firma", "Firma", ancho=1.5, grupo="PERSONAL EN LA LABOR", solo_impresion=True),
                ],
                numerar=False,
                fila_alto_mm=7,
            ),
            campos(
                None,
                campo("capataz", "Capataz / supervisor", span=3),
                campo("orden_trabajo", "Orden de trabajo e instrucciones", "textarea", span=2, filas=6),
                campo("grafico", "Gráfico de la labor (descripción)", "textarea", filas=6),
            ),
            tabla(
                "perforacion", "Perforación", 2,
                [
                    col("perforadora", "Perforadora · código", ancho=1.6),
                    col("inicio", "Inicio", "time", 0.9, grupo="TIEMPO EN OPERACIÓN"),
                    col("fin", "Fin", "time", 0.9, grupo="TIEMPO EN OPERACIÓN"),
                    col("ancho", "Ancho de labor (m)", "number", 1.0),
                    col("alto", "Alto de labor (m)", "number", 1.0),
                    col("taladros", "N° de taladros", "number", 1.1),
                    col("longitud", "Longitud taladros (pies)", "number", 1.1),
                    col("disparos", "N° de disparos", "number", 1.0),
                    col("cargados", "N° taladros cargados", "number", 1.1),
                    col("avance", "Avance (mts)", "number", 1.0),
                    col("tiro_cortado", "Tiro cortado", "select", 1.0, opciones=SI_NO),
                    col("desquinche", "Desquinche", "select", 1.0, opciones=SI_NO),
                ],
                numerar=False,
                fila_alto_mm=8,
            ),
        ],
        "reverso": [
            campos(
                "Fallas que ocasionan incumplimiento del ciclo",
                campo("fallas", "Marque las fallas presentadas", "checks", span=3, opciones=FALLAS_CICLO),
            ),
            tabla(
                "accesorios", "Accesorios", 10,
                [col("descripcion", "Accesorio", ancho=3.5), col("cant", "Cant.", "number", 1)],
                numerar=False,
                prefill={"descripcion": [
                    "Cordón detonante 5P (Mts.)", "Igniter Cord (Mts.)", "Igniter Cord 2.4m",
                    "Fulminante eléctrico - Unid", "Exsanel 2.1m", "Exsanel 3.0m", "Exsanel 4.8m",
                ]},
                lado_a_lado="explosivos",
            ),
            tabla(
                "explosivos", "Explosivos", 10,
                [col("descripcion", "Explosivo", ancho=3.5), col("cant", "Cant.", "number", 1)],
                numerar=False,
                prefill={"descripcion": [
                    'EXADIT 45 7/8" x 7"', 'EXSABLOCK 7/8" x 7"', 'EXSABLOCK 1 1/8" x 8"',
                    'SEMEXA 45% 1" x 7"', 'SEMEXA 45% 1 1/8" x 12"', 'EMULNOR 1000 1" x 7"',
                    'EMULNOR 3000 1" x 7"',
                ]},
            ),
            tabla(
                "retardos", "N° por cantidad (retardos)", 1,
                [col(f"r{n}", str(n), "number", 1) for n in RETARDOS],
                numerar=False,
                etiquetas_filas=["N°"],
                fila_alto_mm=7,
            ),
            tabla(
                "sost_convencional", "Sostenimiento convencional", 10,
                [col("unid", "Unid.", ancho=0.7), col("descripcion", "Descripción", ancho=3.3),
                 col("cantidad", "Cantidad", "number", 1)],
                numerar=False,
                prefill={
                    "unid": ["UND"] * 8,
                    "descripcion": ["MARCHAVANTES", "CUADRO COMPLETO", "ENCOSTILLADO / ENTABLADO", "CUADRO COJO",
                                    "PUNTALES DE SEGURIDAD", "SOLERAS", "INSTALACIÓN DE DESCANSOS",
                                    "VUELTAS DE ENCRIBADO"],
                },
                lado_a_lado="sost_mecanizado",
            ),
            tabla(
                "sost_mecanizado", "Sostenimiento mecanizado", 10,
                [col("unid", "Unid.", ancho=0.7), col("descripcion", "Descripción", ancho=3.3),
                 col("cantidad", "Cantidad", "number", 1)],
                numerar=False,
                prefill={
                    "unid": ["UND", "m2", "UND", "m2", "m2", "m3", "m3", "UND", "UND"],
                    "descripcion": ["PERNOS HYDRABOLT / HELICOIDAL", "MALLA ELECTROSOLDADA",
                                    "PERNO ANCLAJE X-PANDABOLT 2.1X29 M", 'SHOTCRETE VÍA SECA e= 1" / 2"',
                                    'SHOTCRETE VÍA SECA e= 3"', 'SHOTCRETE VÍA HÚMEDA e=2"',
                                    'SHOTCRETE VÍA HÚMEDA e=3"', "CIMBRAS", 'SPLIT SET DE __"'],
                },
            ),
            tabla(
                "materiales", "Otros materiales", 7,
                [col("unid", "Unid.", ancho=0.8), col("descripcion", "Material", ancho=3),
                 col("cantidad", "Cantidad", "number", 1)],
                numerar=False,
                prefill={
                    "unid": ["UND", "Bolsas", "Litros", "Unid.", "UND", "m³", "Unid."],
                    "descripcion": ["Cembol", "Cemento", "Aditivo acelerante", "Bolsa Cresk para cimbras",
                                    "Resina", "Arena", "Tablas para cimbras"],
                },
            ),
            tabla(
                "equipos_limpieza", "Horómetro, EQ servicios y equipos utilizados en la labor para limpieza (código del equipo)", 2,
                [
                    col("horometro_inicio", "Inicio", "number", 1, grupo="HORÓMETRO"),
                    col("horometro_final", "Final", "number", 1, grupo="HORÓMETRO"),
                    col("bomba", "Bomba", ancho=1, grupo="EQ SERVICIOS"),
                    col("servicio_otro", "Otro", ancho=1, grupo="EQ SERVICIOS"),
                    col("winche", "Winche (E/N)", ancho=1),
                    col("ventilador", "Ventilador", ancho=1),
                    col("bomba_sumergible", "Bomba sumergible", ancho=1),
                    col("bomba_hydrabolt", "Bomba Hydrabolt", ancho=1),
                    col("redesatado", "Redesatado", ancho=1),
                    col("limpieza_pulso", "Limpieza a pulso", ancho=1),
                    col("limpieza_finos", "Limpieza finos", ancho=1),
                    col("pallaqueo", "Pallaqueo", ancho=1),
                    col("prep_relleno", "Prep. relleno (tarea)", ancho=1),
                ],
                numerar=False,
                fila_alto_mm=8,
            ),
            campos(
                None,
                campo("ingeniero", "Ingeniero responsable (este reporte no será válido sin su firma)", span=3),
            ),
        ],
    },
    {
        "id": "rju",
        "codigo": "RJU",
        "titulo": "Reporte de Jumbo",
        "prefijo": "RJU 23-",
        "digitos": 6,
        "inicio": 5001,
        "papel": {"ancho_mm": 297, "alto_mm": 230, "etiqueta": "29.7 × 23 cm (horizontal)", "a4": False},
        "material": "Autocopiativo original + 1 copia · Talonario de 100 juegos",
        "resumen": {"equipo": "codigo_equipo", "responsable": ("personal", ["nombres", "ap_paterno"])},
        "cara": [
            campos(
                "Datos generales",
                campo("fecha", "Fecha", "date", requerido=True, auto="hoy"),
                campo("turno", "Turno", "radio", opciones=TURNOS),
                campo("codigo_equipo", "Código de equipo"),
                campo("empresa", "Empresa especializada", recordar=True),
                campo("mina", "Mina", recordar=True),
                campo("zona", "Zona", recordar=True),
                campo("proyecto", "Proyecto", recordar=True),
                campo("combustible", "Combustible (gal)", "number"),
                campo("revision_cmh", "Revisión CMH (nombres y apellidos)"),
                campo("revision_dni", "DNI revisión CMH", max=12),
                campo("supervisor", "Firma del supervisor (nombre)", span=2),
            ),
            personal(
                "personal", "Personal en la labor", 2, cargo=False,
                extra_cols=[col("categoria", "Categoría", "select", 1.4, opciones=["(M) Maestro", "(A) Ayudante"])],
            ),
            tabla(
                "detalle", "Detalle de actividades", 18,
                [
                    col("hora_inicial", "Hora inicial (24h)", "time", 1.1),
                    col("hora_final", "Hora final (24h)", "time", 1.1),
                    col("codigo_act", "Código de actividad", "codigo", 1.2),
                    col("labor_inicial", "Labor inicial", ancho=1.3),
                    col("labor_final", "Labor final", ancho=1.3),
                    col("taladros_perf", "Taladros perfor.", "number", 0.9, grupo="PERFORACIÓN (FRENTE)", total=True),
                    col("long_taladros", "Long. taladros (pies)", "number", 0.9, grupo="PERFORACIÓN (FRENTE)"),
                    col("taladros_cargados", "Taladros cargados", "number", 0.9, grupo="PERFORACIÓN (FRENTE)", total=True),
                    col("taladros_rimados", "Taladros rimados", "number", 0.9, grupo="PERFORACIÓN (FRENTE)", total=True),
                    col("pernos", "Pernos instalados", "number", 0.9, grupo="SOSTENIMIENTO", total=True),
                    col("long_pernos", "Long. pernos (pies)", "number", 0.9, grupo="SOSTENIMIENTO"),
                    col("tipo_pernos", "Tipo pernos (Sw, Ss, He)", ancho=0.9, grupo="SOSTENIMIENTO"),
                    col("malla", "Malla electr. (m²)", "number", 0.9, grupo="SOSTENIMIENTO", total=True),
                    col("acero_broca", "Acero broca", ancho=0.9),
                    col("h_elec_ini", "Eléctrico ini.", "number", 1, grupo="HORÓMETROS"),
                    col("h_elec_fin", "Eléctrico fin.", "number", 1, grupo="HORÓMETROS"),
                    col("h_diesel_ini", "Diésel ini.", "number", 1, grupo="HORÓMETROS"),
                    col("h_diesel_fin", "Diésel fin.", "number", 1, grupo="HORÓMETROS"),
                    col("h_perc_ini", "Percusión ini.", "number", 1, grupo="HORÓMETROS"),
                    col("h_perc_fin", "Percusión fin.", "number", 1, grupo="HORÓMETROS"),
                    col("observacion", "Observación", ancho=2.2),
                ],
                ancho_item=0.5,
                fila_alto_mm=6.5,
            ),
            campos(None, campo("orden_trabajo", "Orden de trabajo", "textarea", span=3, filas=3)),
        ],
        "reverso": [CATALOGO_JUMBO],
    },
    {
        "id": "rpvol",
        "codigo": "RPVOL26",
        "titulo": "Reporte de Servicio de Volquetes",
        "prefijo": "RPVOL26-",
        "digitos": 6,
        "inicio": 1,
        "papel": A4_HORIZONTAL,
        "material": "Sin medida establecida · se imprime en A4",
        "resumen": {"equipo": "codigo_equipo", "responsable": ("campos", ["nombres", "ap_paterno"])},
        "cara": [
            campos(
                "Datos del servicio",
                campo("fecha", "Fecha", "date", requerido=True, auto="hoy"),
                campo("contrata", "Contrata", recordar=True),
                campo("turno", "Turno", "radio", opciones=["Día", "Noche"]),
                campo("horometro_inicial", "Horómetro inicial", "number"),
                campo("horometro_final", "Horómetro final", "number"),
                campo("hora_inicio", "Hora inicio de operaciones", "time"),
                campo("km_inicial", "Kilometraje inicial", "number"),
                campo("km_final", "Kilometraje final", "number"),
                campo("hora_fin", "Hora término de operaciones", "time"),
                campo("codigo_equipo", "Código de equipo"),
                campo("hr_abastecimiento", "Hr. abastecimiento", "time"),
                campo("petroleo_gln", "Petróleo (gln)", "number"),
                campo("orden_trabajo", "N° orden de trabajo"),
                campo("centro_costo", "Centro de costo", recordar=True),
            ),
            campos(
                "Operador y supervisor",
                campo("dni_operador", "DNI operador", max=12),
                campo("ap_paterno", "Apellido paterno"),
                campo("ap_materno", "Apellido materno"),
                campo("nombres", "Nombres"),
                campo("supervisor", "Nombre del supervisor", span=2),
            ),
            tabla(
                "viajes", "Viajes", 20,
                [
                    col("material", "Material o carga", ancho=1.8),
                    col("codigo_ruta", "Código / ruta", ancho=1.2),
                    col("ruta", "Ruta origen - destino", ancho=2.4),
                    col("n_scoop", "N° Scoop", ancho=0.9),
                    col("codigo_viaje", "Código de viaje", ancho=1.1),
                    col("hr_inicial", "Hr. inicial", "time", 1),
                    col("hr_final", "Hr. final", "time", 1),
                    col("duracion", "Duración (h:mm)", "calc", 1,
                        calc={"tipo": "duracion", "desde": "hr_inicial", "hasta": "hr_final"}, total=True),
                    col("horometro_inicial", "Horómetro inicial", "number", 1.1),
                    col("horometro_final", "Horómetro final", "number", 1.1),
                    col("horas_horometro", "Horas horómetro", "calc", 1,
                        calc={"tipo": "resta", "a": "horometro_final", "b": "horometro_inicial"}, total=True),
                    col("centro_costo", "Centro de costo", ancho=1.1),
                    col("vb_vigilante", "Vº Bº vigilante", ancho=1.2, solo_impresion=True),
                ],
                fila_alto_mm=6.5,
                contar_filas="Viajes",
            ),
        ],
        "reverso": None,
    },
    {
        "id": "veo",
        "codigo": "VEO",
        "titulo": "Verificación de Estándares Operativos - VEO · Equipos Trackless",
        "prefijo": "VEO-",
        "digitos": 6,
        "inicio": 1,
        "papel": A4_VERTICAL,
        "material": "Formato 3646JV · se imprime en A4",
        "resumen": {"equipo": "codigo_equipo", "responsable": ("campos", ["evaluador_nombre"])},
        "cara": [
            campos(
                "1. Labor / lugar de trabajo",
                campo("labor", "Labor / lugar de trabajo", span=2),
                campo("fecha", "Fecha", "date", requerido=True, auto="hoy"),
                campo("codigo_equipo", "Código de equipo"),
            ),
            campos(
                "2. Medición de parámetros físico - químicos en la labor",
                campo("hora", "Hora", "time"),
                campo("evaluador_dni", "DNI evaluador", max=12),
                campo("evaluador_nombre", "Nombre y apellidos del evaluador"),
                campo("evaluador_cargo", "Cargo evaluador"),
                campo("o2", "Oxígeno O2 (%)", "number", limite={"min": 19.5, "max": 22.5, "texto": "19.5% < O2 < 22.5"}),
                campo("co", "CO (ppm)", "number", limite={"max": 25, "texto": "Menor a 25 PPM"}),
                campo("co2", "CO2 (ppm)", "number", limite={"max": 5000, "texto": "Menor a 5000 PPM"}),
                campo("no2", "NO2 (ppm)", "number", limite={"max": 5, "texto": "Menor a 5 PPM"}),
                campo("estres_termico", "Estrés térmico (ºC)", "number", limite={"max": 30, "texto": "Menor a 30 ºC"}),
                campo("velocidad_aire", "Velocidad de aire (m/s)", "number", limite={"min": 20, "max": 250, "texto": "20 < VA < 250"}),
                campo("ruido", "Ruido (dB)", "number", limite={"max": 82, "texto": "Menor a 82"}),
            ),
            campos(
                "3. Información del trabajador y supervisor",
                campo("comunicado", "¿Se le comunicó los resultados de la medición de gases antes de iniciar sus actividades?",
                      "radio", span=3, opciones=SI_NO),
            ),
            tabla(
                "trabajadores", "Trabajadores", 5,
                [col("dni", "DNI", ancho=1.2, max=12), col("nombre", "Nombre y apellidos", ancho=3),
                 col("cargo", "Cargo", ancho=1.6), col("hora", "Hora", "time", 1),
                 col("firma", "Firma", ancho=1.5, solo_impresion=True)],
            ),
            tabla(
                "supervisores", "Supervisores", 3,
                [col("dni", "DNI", ancho=1.2, max=12), col("nombre", "Nombre y apellidos", ancho=3),
                 col("cargo", "Cargo", ancho=1.6), col("hora", "Hora", "time", 1),
                 col("firma", "Firma", ancho=1.5, solo_impresion=True)],
            ),
            tabla(
                "evaluacion", "4. Evaluación VDO de la labor (marque los criterios PARE / ABC presentes)", 4,
                [
                    col("pare", "Condición PARE (1-22)", "multi", 4, opciones=[str(n) for n in range(1, 23)]),
                    col("abc", "Condición ABC (23-41)", "multi", 4, opciones=[str(n) for n in range(23, 42)]),
                    col("estado", "Estado", "select", 1.3, opciones=["Normal", "ABC", "PARE"]),
                ],
                numerar=False,
                etiquetas_filas=["T1", "SUP. 1", "SUP. 2", "SUP. 3"],
                fila_alto_mm=7,
            ),
            {
                "tipo": "lista",
                "titulo": "Condiciones PARE y ABC",
                "nota": "Si hay condiciones ABC y/o PARE: retire al personal de la labor, bloquee el acceso y reporte al Centro de Control (Anexo 6).",
                "grupos": [
                    {"titulo": "CONDICIÓN PARE", "items": [{"codigo": str(i + 1), "descripcion": t} for i, t in enumerate(CONDICIONES_PARE)]},
                    {"titulo": "CONDICIÓN ABC", "items": [{"codigo": str(i + 23), "descripcion": t} for i, t in enumerate(CONDICIONES_ABC)]},
                ],
            },
        ],
        "reverso": [
            {
                "tipo": "checklist",
                "id": "criterios",
                "titulo": "Requerimientos / criterios operacionales",
                "nota": 'Marque para cada criterio si es C: Conforme, NC: No Conforme o NA: No Aplica. RB: riesgo (A alto, M medio).',
                "evaluadores": [{"id": "t1", "label": "T1"}, {"id": "sup1", "label": "SUP. 01"},
                                {"id": "sup2", "label": "SUP. 02"}, {"id": "sup3", "label": "SUP. 03"}],
                "opciones": ["C", "NC", "NA"],
                "grupos": [
                    {"titulo": g, "items": [{"id": i, "texto": t, "rb": rb} for i, t, rb in items]}
                    for g, items in CRITERIOS_VEO
                ],
            }
        ],
    },
]

FORMATOS_POR_ID = {f["id"]: f for f in FORMATOS}


def secciones(formato: dict):
    for sec in formato.get("cara") or []:
        yield sec
    for sec in formato.get("reverso") or []:
        yield sec


def formatos_publicos() -> list[dict]:
    return deepcopy(FORMATOS)


def numero_display(formato: dict, numero: int) -> str:
    return f"{formato['prefijo']}{int(numero):0{formato['digitos']}d}"
