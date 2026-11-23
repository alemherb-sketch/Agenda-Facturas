"""Reportes operativos: correlativo, limpieza de datos, lista, duplicado y PDF a medida."""
import os
import sys
import tempfile

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)
_tmp = tempfile.mkdtemp(prefix="agenda-reportes-")
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/"))
os.environ.setdefault("SECRET_KEY", "clave-solo-para-tests")
os.environ.setdefault("UPLOAD_DIR", os.path.join(_tmp, "uploads"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def _auth(client, email):
    res = client.post(
        "/api/auth/registro",
        json={"nombre": "Reportes Test", "email": email, "password": "secreto8"},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_formatos_y_correlativo():
    client = TestClient(app)
    h = _auth(client, "rep1@negocio.pe")
    formatos = client.get("/api/reportes/formatos", headers=h).json()
    ids = {f["id"] for f in formatos}
    assert ids == {"rpe", "rpeq18", "rpcam", "roft", "rju", "rpvol", "veo"}
    papel = {f["id"]: (f["papel"]["ancho_mm"], f["papel"]["alto_mm"]) for f in formatos}
    assert papel["rpe"] == (230, 296)
    assert papel["rju"] == (297, 230)
    assert papel["rpeq18"] == (210, 297)

    sig = client.get("/api/reportes/siguiente?formato=rpe", headers=h).json()
    assert sig == {"numero": 5001, "numero_display": "RPE 23-005001"}

    res = client.post(
        "/api/reportes",
        headers=h,
        json={
            "formato": "rpe",
            "datos": {
                "fecha": "2026-11-20",
                "turno": "Primero",
                "codigo_equipo": "SC-14",
                "tipo_equipo": "Volquete",
                "campo_inventado": "x",
                "personal": [{"nombres": "Juan", "ap_paterno": "Quispe", "firma": "no se guarda"}],
                "detalle": [{"min": "6", "hora_inicial": "25:00", "codigo_act": "OP-01"}, {}, {}],
            },
        },
    )
    assert res.status_code == 201, res.text
    rep = res.json()
    assert rep["numero_display"] == "RPE 23-005001"
    assert rep["equipo"] == "SC-14"
    assert rep["responsable"] == "Juan Quispe"
    assert rep["turno"] == "Primero"
    datos = rep["datos"]
    assert "tipo_equipo" not in datos and "campo_inventado" not in datos
    assert datos["personal"] == [{"nombres": "Juan", "ap_paterno": "Quispe"}]
    assert datos["detalle"] == [{"min": 6.0, "codigo_act": "OP-01"}]

    assert client.get("/api/reportes/siguiente?formato=rpe", headers=h).json()["numero"] == 5002
    dup_num = client.post(
        "/api/reportes", headers=h, json={"formato": "rpe", "numero": 5001, "datos": {"fecha": "2026-11-21"}}
    )
    assert dup_num.status_code == 400
    sin_fecha = client.post("/api/reportes", headers=h, json={"formato": "rpe", "datos": {}})
    assert sin_fecha.status_code == 400


def test_lista_duplicar_pdf_y_eliminar():
    client = TestClient(app)
    h = _auth(client, "rep2@negocio.pe")
    otro = _auth(client, "rep3@negocio.pe")
    creado = client.post(
        "/api/reportes",
        headers=h,
        json={
            "formato": "rpvol",
            "datos": {
                "fecha": "2026-11-22",
                "nombres": "Luis",
                "ap_paterno": "Ramos",
                "codigo_equipo": "VQ-03",
                "viajes": [{"hr_inicial": "23:20", "hr_final": "00:45", "horometro_inicial": 100, "horometro_final": 101.5}],
            },
        },
    ).json()

    lista = client.get("/api/reportes?formato=rpvol&q=VQ-03", headers=h).json()
    assert [r["id"] for r in lista] == [creado["id"]]
    assert lista[0]["datos"] is None
    assert client.get("/api/reportes/conteo", headers=h).json() == {"rpvol": 1}
    assert client.get(f"/api/reportes/{creado['id']}", headers=otro).status_code == 404

    copia = client.post(f"/api/reportes/{creado['id']}/duplicar", headers=h).json()
    assert copia["numero"] == creado["numero"] + 1
    assert copia["datos"]["viajes"] == creado["datos"]["viajes"]

    pdf = client.get(f"/api/reportes/{creado['id']}/pdf", headers=h)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert 'filename="RPVOL26-000001.pdf"' in pdf.headers["content-disposition"]

    assert client.delete(f"/api/reportes/{copia['id']}", headers=h).json() == {"ok": True}
    assert client.get("/api/reportes/conteo", headers=h).json() == {"rpvol": 1}


def test_pdf_respeta_medidas_de_cada_formato():
    from app.services.reportes_formatos import FORMATOS, numero_display
    from app.services.reportes_pdf import generar_pdf_reporte

    for formato in FORMATOS:
        pdf = generar_pdf_reporte(formato, numero_display(formato, formato["inicio"]), {"fecha": "2026-11-23"})
        caja = pdf.split(b"/MediaBox")[1].split(b"]")[0].strip(b" [").split()
        ancho_mm = float(caja[2]) / 72 * 25.4
        alto_mm = float(caja[3]) / 72 * 25.4
        assert round(ancho_mm) == formato["papel"]["ancho_mm"], formato["id"]
        assert round(alto_mm) == formato["papel"]["alto_mm"], formato["id"]
        paginas = pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages")
        esperadas = 2 if formato.get("reverso") else 1
        assert paginas == esperadas, (formato["id"], paginas)
