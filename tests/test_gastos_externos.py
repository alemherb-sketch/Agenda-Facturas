"""Gastos externos: tipos, totales y que cada usuario solo ve los suyos."""
import os
import sys
import tempfile

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)
_tmp = tempfile.mkdtemp(prefix="agenda-gastos-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
os.environ["SECRET_KEY"] = "clave-solo-para-tests"
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def _auth(client, email):
    res = client.post(
        "/api/auth/registro",
        json={"nombre": "Gastos Test", "email": email, "password": "secreto8"},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_tipos_total_y_aislamiento():
    client = TestClient(app)
    h = _auth(client, "gasto1@negocio.pe")
    otro = _auth(client, "gasto2@negocio.pe")

    meta = client.get("/api/meta").json()
    assert "Peaje" in meta["tipos_gasto_externo"]
    assert "Alimentación" in meta["tipos_gasto_externo"]

    peaje = client.post(
        "/api/gastos-externos",
        headers=h,
        json={
            "tipo": "peaje",
            "concepto": "Peaje Carretera Central",
            "monto": 18.5,
            "fecha": "2026-11-20",
            "proveedor": "Rutas de Lima",
            "comprobante": "B001-22",
            "metodo_pago": "efectivo",
        },
    )
    assert peaje.status_code == 201, peaje.text
    assert peaje.json()["tipo"] == "Peaje"
    assert peaje.json()["monto"] == "18.50"

    propio = client.post(
        "/api/gastos-externos",
        headers=h,
        json={
            "tipo": "Guardianía",
            "concepto": "Turno noche",
            "monto": 80,
            "fecha": "2026-11-21",
            "metodo_pago": "yape",
        },
    )
    assert propio.status_code == 201, propio.text
    assert propio.json()["tipo"] == "Guardianía"

    cero = client.post(
        "/api/gastos-externos",
        headers=h,
        json={"tipo": "Otros", "concepto": "Nada", "monto": 0, "fecha": "2026-11-21"},
    )
    assert cero.status_code == 422

    resumen = client.get("/api/gastos-externos/resumen", headers=h).json()
    assert resumen["cantidad"] == 2
    assert resumen["total"] == "98.50"
    assert resumen["por_tipo"][0]["tipo"] == "Guardianía"
    assert "Guardianía" in resumen["tipos"]
    assert client.get("/api/gastos-externos/resumen", headers=otro).json()["cantidad"] == 0

    solo_peaje = client.get("/api/gastos-externos?tipo=peaje", headers=h).json()
    assert [g["concepto"] for g in solo_peaje] == ["Peaje Carretera Central"]

    editado = client.put(
        f"/api/gastos-externos/{peaje.json()['id']}",
        headers=h,
        json={"monto": 20, "notas": "Ida y vuelta"},
    )
    assert editado.status_code == 200, editado.text
    assert editado.json()["monto"] == "20.00"
    assert editado.json()["tipo"] == "Peaje"

    assert client.delete(f"/api/gastos-externos/{propio.json()['id']}", headers=otro).status_code == 404
    assert client.delete(f"/api/gastos-externos/{propio.json()['id']}", headers=h).json() == {"ok": True}
    assert client.get("/api/gastos-externos/resumen", headers=h).json()["cantidad"] == 1
