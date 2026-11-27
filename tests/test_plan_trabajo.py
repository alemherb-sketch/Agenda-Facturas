"""Plan trabajo: listas de la hoja DATOS, labores convencionales y uso de equipos por usuario."""
import os
import sys
import tempfile

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)
_tmp = tempfile.mkdtemp(prefix="agenda-plan-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
os.environ["SECRET_KEY"] = "clave-solo-para-tests"
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

BASE = "/api/plan-trabajo"


def _auth(client, email):
    res = client.post(
        "/api/auth/registro",
        json={"nombre": "Plan Test", "email": email, "password": "secreto8"},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _labor(**extra):
    """Primera fila de la base convencional del Excel (1 de junio, SN-3E, perforación y voladura)."""
    datos = {
        "fecha": "2026-06-01",
        "turno": "Dia",
        "guardia": "G-1",
        "labor_codigo": "SN-3E",
        "maestro": "LLAPO RIVEROS Sansinio",
        "tarea_codigo": "PV",
        "material_codigo": "D",
        "tipo_codigo": "F",
        "equipo_perforacion": "RNP",
        "numero_maquina": "05",
        "taladros_perforados": 17,
        "longitud_perforacion": 4,
        "taladros_disparados": 14,
        "insumos": {"emulnor_3000": 19, "anfo": 10, "mecha_rapida": 2, "carmex_18": 14, "broca_36": 0},
        "avance_ml": 1,
    }
    datos.update(extra)
    return datos


def test_catalogo_de_la_hoja_datos():
    client = TestClient(app)
    h = _auth(client, "datos@mina.pe")
    cat = client.get(f"{BASE}/catalogo", headers=h).json()
    assert [t["valor"] for t in cat["turnos"]] == ["Dia", "Noche"]
    assert [g["codigo"] for g in cat["guardias"]] == ["G-1", "G-2", "G-3"]
    assert len(cat["labores"]) == 19
    sn3e = cat["labores"][0]
    assert sn3e == {
        "codigo": "SN-3E", "labor": "Sub Nivel 3 Este", "fase": "Exploracion", "unidad": "Enrique",
        "nivel": 270, "meta": "META 1", "seccion": "1 x 1.7", "programa_m": 30,
    }
    assert {lab["codigo"] for lab in cat["labores"]} >= {"ST", "GL-195", "PQE-1", "SNE-1O", "SN-2"}
    assert len(cat["tareas"]) == 13 and cat["tareas"][0] == {"codigo": "SS", "tarea": "Sost. Split Set"}
    assert len(cat["maestros"]) == 5
    assert [t["codigo"] for t in cat["tipos_perforacion"]] == ["F", "D", "S", "SE"]
    assert [m["codigo"] for m in cat["materiales"]] == ["D", "M"]
    assert [len(g["items"]) for g in cat["insumos"]] == [6, 7, 14]
    assert [m["codigo"] for m in cat["maquinas"]] == ["CN-AC01", "GE-M01", "CN-S01"]


def test_labores_convencionales():
    client = TestClient(app)
    h = _auth(client, "labor@mina.pe")
    otro = _auth(client, "otro-labor@mina.pe")

    res = client.post(f"{BASE}/convencional", headers=h, json=_labor())
    assert res.status_code == 201, res.text
    uno = res.json()
    # Lo que el Excel trae con BUSCARV a partir de los códigos
    assert uno["labor"] == "Sub Nivel 3 Este" and uno["seccion"] == "1 x 1.7" and uno["nivel"] == 270
    assert uno["fase"] == "Exploracion" and uno["meta"] == "META 1" and uno["unidad"] == "Enrique"
    assert uno["jefe_guardia"] == "ING. EGUIL RHONI DIAZ DIAZ"
    assert uno["tarea"] == "Perforacion y Voladura"
    assert uno["material"] == "Desmonte" and uno["tipo_perforacion"] == "Frente"
    assert uno["pies_perforados"] == "68.00"  # N° tal. perf. × long. perf.
    assert uno["insumos"] == {"emulnor_3000": "19.00", "anfo": "10.00", "mecha_rapida": "2.00", "carmex_18": "14.00"}

    # Códigos en minúscula se aceptan; la tarea SS sí trae su nombre
    dos = client.post(
        f"{BASE}/convencional",
        headers=h,
        json=_labor(
            fecha="2026-06-03", turno="noche", guardia="g-2", labor_codigo="st", tarea_codigo="ss",
            maestro="rojas tambo nain", material_codigo="m", tipo_codigo="d", insumos={}, avance_ml=0.8,
            tn_oxidos=2.5, tn_sulfuros=1,
        ),
    )
    assert dos.status_code == 201, dos.text
    d = dos.json()
    assert (d["turno"], d["guardia"], d["labor"], d["tarea"]) == ("Noche", "G-2", "Estocada", "Sost. Split Set")
    assert (d["maestro"], d["material"], d["tipo_perforacion"]) == ("ROJAS TAMBO Nain", "Mineral", "Desquinche")

    # Opciones que no están en la hoja DATOS
    assert client.post(f"{BASE}/convencional", headers=h, json=_labor(labor_codigo="XX-9")).status_code == 400
    assert client.post(f"{BASE}/convencional", headers=h, json=_labor(maestro="Otro")).status_code == 400
    assert client.post(f"{BASE}/convencional", headers=h, json=_labor(turno="Tarde")).status_code == 400
    assert client.post(f"{BASE}/convencional", headers=h, json=_labor(insumos={"dinamita": 3})).status_code == 400
    assert client.post(f"{BASE}/convencional", headers=h, json=_labor(insumos={"anfo": -1})).status_code == 400
    assert client.post(f"{BASE}/convencional", headers=h, json=_labor(taladros_perforados=-2)).status_code == 422

    lista = client.get(f"{BASE}/convencional", headers=h).json()
    assert [r["id"] for r in lista["registros"]] == [d["id"], uno["id"]]
    assert lista["cantidad"] == 2
    assert lista["pies_perforados"] == "136.00"
    assert lista["taladros_disparados"] == 28
    assert lista["avance_ml"] == "1.80"
    assert lista["toneladas"] == "3.50"
    assert client.get(f"{BASE}/convencional", headers=otro).json()["cantidad"] == 0
    assert client.get(f"{BASE}/convencional?labor=sn-3e", headers=h).json()["cantidad"] == 1
    assert client.get(f"{BASE}/convencional?tarea=SS&turno=Noche", headers=h).json()["cantidad"] == 1
    assert client.get(f"{BASE}/convencional?guardia=G-1", headers=h).json()["cantidad"] == 1
    assert client.get(f"{BASE}/convencional?maestro=LLAPO RIVEROS Sansinio", headers=h).json()["cantidad"] == 1
    assert client.get(f"{BASE}/convencional?fecha_desde=2026-06-02", headers=h).json()["cantidad"] == 1
    assert client.get(f"{BASE}/convencional?fecha_desde=2026-06-05&fecha_hasta=2026-06-01", headers=h).status_code == 400

    # Editar recalcula pies perforados y reemplaza los insumos
    edit = client.put(
        f"{BASE}/convencional/{uno['id']}",
        headers=h,
        json=_labor(taladros_perforados=18, insumos={"split_set_5": 6}),
    )
    assert edit.status_code == 200, edit.text
    assert edit.json()["pies_perforados"] == "72.00" and edit.json()["insumos"] == {"split_set_5": "6.00"}
    assert client.get(f"{BASE}/convencional/{uno['id']}", headers=otro).status_code == 404
    assert client.put(f"{BASE}/convencional/{uno['id']}", headers=otro, json=_labor()).status_code == 404

    assert client.delete(f"{BASE}/convencional/{uno['id']}", headers=otro).status_code == 404
    assert client.delete(f"{BASE}/convencional/{uno['id']}", headers=h).json() == {"ok": True}
    assert client.get(f"{BASE}/convencional", headers=h).json()["cantidad"] == 1


def test_uso_de_equipos():
    client = TestClient(app)
    h = _auth(client, "equipos@mina.pe")
    otro = _auth(client, "otro-equipos@mina.pe")

    dia = client.post(
        f"{BASE}/equipos",
        headers=h,
        json={"fecha": "2026-09-01", "turno": "Dia", "maquina_codigo": "cn-ac01",
              "horometro_inicial": 2.5, "horometro_final": 4.6, "petroleo_gl": 6},
    )
    assert dia.status_code == 201, dia.text
    e = dia.json()
    assert (e["maquina_codigo"], e["equipo"], e["marca"], e["modelo"]) == (
        "CN-AC01", "Compresora Neumatica", "ATLAS COPCO", "XAVS 400",
    )
    assert e["horas_trabajadas"] == "2.10"

    noche = client.post(
        f"{BASE}/equipos",
        headers=h,
        json={"fecha": "2026-09-01", "turno": "Noche", "maquina_codigo": "CN-AC01",
              "horometro_inicial": 4.6, "horometro_final": 6.7, "petroleo_gl": 5},
    )
    assert noche.status_code == 201, noche.text
    grupo = client.post(
        f"{BASE}/equipos",
        headers=h,
        json={"fecha": "2026-09-02", "turno": "Dia", "maquina_codigo": "GE-M01", "horometro_inicial": 100},
    )
    assert grupo.status_code == 201 and grupo.json()["horas_trabajadas"] is None

    # El horómetro final no puede ser menor; máquina fuera de la lista
    assert client.post(
        f"{BASE}/equipos",
        headers=h,
        json={"fecha": "2026-09-02", "turno": "Dia", "maquina_codigo": "CN-S01",
              "horometro_inicial": 10, "horometro_final": 9},
    ).status_code == 400
    assert client.post(
        f"{BASE}/equipos", headers=h, json={"fecha": "2026-09-02", "turno": "Dia", "maquina_codigo": "ZZ-1"}
    ).status_code == 400

    lista = client.get(f"{BASE}/equipos", headers=h).json()
    assert [r["id"] for r in lista["registros"]] == [grupo.json()["id"], noche.json()["id"], e["id"]]
    assert lista["cantidad"] == 3
    assert lista["horas_trabajadas"] == "4.20" and lista["petroleo_gl"] == "11.00"
    assert client.get(f"{BASE}/equipos?maquina=CN-AC01&turno=Noche", headers=h).json()["cantidad"] == 1
    assert client.get(f"{BASE}/equipos", headers=otro).json()["cantidad"] == 0

    # El último horómetro final de cada máquina es el inicial del siguiente turno
    assert client.get(f"{BASE}/equipos/ultimos", headers=h).json() == {"CN-AC01": 6.7}
    assert client.get(f"{BASE}/equipos/ultimos", headers=otro).json() == {}

    edit = client.put(
        f"{BASE}/equipos/{grupo.json()['id']}",
        headers=h,
        json={"fecha": "2026-09-02", "turno": "Dia", "maquina_codigo": "GE-M01",
              "horometro_inicial": 100, "horometro_final": 108.5, "petroleo_gl": 12.5},
    )
    assert edit.status_code == 200 and edit.json()["horas_trabajadas"] == "8.50"
    assert client.get(f"{BASE}/equipos/ultimos", headers=h).json() == {"CN-AC01": 6.7, "GE-M01": 108.5}
    assert client.put(
        f"{BASE}/equipos/{e['id']}",
        headers=otro,
        json={"fecha": "2026-09-01", "turno": "Dia", "maquina_codigo": "CN-AC01"},
    ).status_code == 404

    assert client.delete(f"{BASE}/equipos/{e['id']}", headers=otro).status_code == 404
    assert client.delete(f"{BASE}/equipos/{e['id']}", headers=h).json() == {"ok": True}
    assert client.get(f"{BASE}/equipos", headers=h).json()["cantidad"] == 2
