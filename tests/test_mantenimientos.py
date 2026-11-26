"""Reporte de mantenimiento: plan de cada hoja PDF, registros por PM y que cada usuario solo ve los suyos."""
import os
import sys
import tempfile

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)
_tmp = tempfile.mkdtemp(prefix="agenda-mant-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
os.environ["SECRET_KEY"] = "clave-solo-para-tests"
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.mantenimiento_planes import EQUIPOS_POR_ID, partes_programadas, proximo  # noqa: E402


def _auth(client, email):
    res = client.post(
        "/api/auth/registro",
        json={"nombre": "Mantenimiento Test", "email": email, "password": "secreto8"},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _programados(equipo, horas):
    """Repuestos que la hoja marca para esa columna, como los envía el formulario."""
    return [
        {"numero_parte": r["numero_parte"], "descripcion": r["descripcion"], "cantidad": r["cantidad"]}
        for r in equipo["repuestos"]
        if horas in r["horas"]
    ]


def test_plan_de_cada_hoja():
    client = TestClient(app)
    h = _auth(client, "plan@equipos.pe")
    catalogo = client.get("/api/mantenimientos/equipos", headers=h).json()
    equipos = {e["id"]: e for e in catalogo["equipos"]}
    assert set(equipos) == {"950L", "962H", "330DL", "330D2L", "420F2"}
    assert {e["id"]: len(e["repuestos"]) for e in catalogo["equipos"]} == {
        "950L": 27, "962H": 20, "330DL": 20, "330D2L": 20, "420F2": 19,
    }
    assert [l["pm"] for l in catalogo["leyenda"]] == ["PM1", "PM2", "PM3", "PM4", "PM3000"]

    # Ciclo de 2000 h con PM4 al final; el 950L va hasta 3000 h y cierra con el PM3000
    assert [f["pm"] for f in equipos["962H"]["frecuencias"]] == [
        "PM1", "PM2", "PM1", "PM3", "PM1", "PM2", "PM1", "PM4",
    ]
    assert equipos["950L"]["ciclo_horas"] == 3000
    assert equipos["950L"]["frecuencias"][7] == {"horas": 2000, "pm": "PM3"}
    assert equipos["950L"]["frecuencias"][-1] == {"horas": 3000, "pm": "PM3000"}

    # Datos de placa tal como están en las hojas
    assert equipos["962H"]["serie"] == "N4A00325" and equipos["962H"]["motor_serie"] == "C7C02357"
    assert equipos["420F2"]["motor_modelo"] == "3054C - C4.4" and equipos["420F2"]["anio"] == 2016
    assert equipos["330DL"]["anio"] == 2005 and equipos["330D2L"]["serie"] == "RCK00279"

    # Las X de cada hoja
    e962 = EQUIPOS_POR_ID["962H"]
    assert len(partes_programadas(e962, 250)) == 7
    assert partes_programadas(e962, 1250) == {"1R-1807", "1R-0762", "326-1644", "2040TN", "245-6375"}
    assert len(partes_programadas(e962, 2000)) == 19  # todo menos el sello 220-8678, que no tiene X
    assert "1G-8878" in partes_programadas(e962, 1000)
    e950 = EQUIPOS_POR_ID["950L"]
    assert len(partes_programadas(e950, 1000)) == 21
    assert len(partes_programadas(e950, 2000)) == 26
    assert len(partes_programadas(e950, 3000)) == 27
    assert "309-6931" not in partes_programadas(e950, 2000)
    assert len(partes_programadas(EQUIPOS_POR_ID["330DL"], 500)) == 12
    assert len(partes_programadas(EQUIPOS_POR_ID["420F2"], 1000)) == 10

    # Lo que sigue en el ciclo, con el horómetro estimado
    assert proximo(e962, 2000, 9000) == {"pm": "PM1", "frecuencia_horas": 250, "horometro": 9250.0}
    assert proximo(e950, 2750, None) == {"pm": "PM3000", "frecuencia_horas": 3000, "horometro": None}
    assert proximo(e950, 3000, 6000.5)["pm"] == "PM1"


def test_registrar_listar_editar_y_eliminar():
    client = TestClient(app)
    h = _auth(client, "taller@equipos.pe")
    otro = _auth(client, "otro@equipos.pe")
    e962 = EQUIPOS_POR_ID["962H"]

    repuestos = _programados(e962, 1000) + [
        {"numero_parte": " 220-8678 ", "descripcion": "SELLO FILTRO SEPARADOR COMBUSTIBLE", "cantidad": 1},
        {"numero_parte": None, "descripcion": "  Grasa   multiproposito ", "cantidad": 0.5},
    ]
    res = client.post(
        "/api/mantenimientos",
        headers=h,
        json={
            "equipo": "962h",
            "frecuencia_horas": 1000,
            "fecha": "2026-11-20",
            "horometro": 9000.04,
            "responsable": "  Juan   Pérez ",
            "observaciones": "Fuga leve en manguera\r\n\r\nRevisar en el próximo PM  ",
            "repuestos": repuestos,
        },
    )
    assert res.status_code == 201, res.text
    pm3 = res.json()
    assert pm3["pm"] == "PM3" and pm3["pm_label"] == "Mantenimiento Preventivo Nivel 3"
    assert pm3["equipo"] == "962H" and pm3["equipo_tipo"] == "CARGADOR FRONTAL"
    assert pm3["serie"] == "N4A00325" and pm3["anio"] == 2006
    assert pm3["horometro"] == "9000.0"
    assert pm3["responsable"] == "Juan Pérez"
    assert pm3["observaciones"] == "Fuga leve en manguera\n\nRevisar en el próximo PM"
    assert [r["item"] for r in pm3["repuestos"]] == list(range(1, 12))
    assert sum(r["programado"] for r in pm3["repuestos"]) == 9
    extra = pm3["repuestos"][-2:]
    assert extra[0]["numero_parte"] == "220-8678" and extra[0]["programado"] is False
    assert extra[1] == {
        "item": 11, "numero_parte": None, "descripcion": "Grasa multiproposito", "cantidad": "0.50", "programado": False,
    }

    # Frecuencia que el equipo no tiene y equipo que no está en el catálogo
    malo = client.post(
        "/api/mantenimientos",
        headers=h,
        json={"equipo": "962H", "frecuencia_horas": 2250, "fecha": "2026-11-20", "repuestos": []},
    )
    assert malo.status_code == 400
    assert "2250" in malo.json()["detail"]
    assert client.post(
        "/api/mantenimientos",
        headers=h,
        json={"equipo": "D6T", "frecuencia_horas": 250, "fecha": "2026-11-20"},
    ).status_code == 400
    assert client.post(
        "/api/mantenimientos",
        headers=h,
        json={
            "equipo": "962H",
            "frecuencia_horas": 250,
            "fecha": "2026-11-20",
            "repuestos": [{"numero_parte": "1R-1807", "descripcion": "FILTRO", "cantidad": 0}],
        },
    ).status_code == 422

    e950 = EQUIPOS_POR_ID["950L"]
    res = client.post(
        "/api/mantenimientos",
        headers=h,
        json={
            "equipo": "950L",
            "frecuencia_horas": 3000,
            "fecha": "2026-11-22",
            "repuestos": _programados(e950, 3000),
        },
    )
    assert res.status_code == 201, res.text
    general = res.json()
    assert general["pm"] == "PM3000" and len(general["repuestos"]) == 27
    assert all(r["programado"] for r in general["repuestos"])

    # Lista con filtros; cada usuario ve solo lo suyo
    todos = client.get("/api/mantenimientos", headers=h).json()
    assert [m["id"] for m in todos] == [general["id"], pm3["id"]]
    assert client.get("/api/mantenimientos", headers=otro).json() == []
    assert [m["id"] for m in client.get("/api/mantenimientos?equipo=962h", headers=h).json()] == [pm3["id"]]
    assert [m["id"] for m in client.get("/api/mantenimientos?pm=PM3000", headers=h).json()] == [general["id"]]
    assert [m["id"] for m in client.get("/api/mantenimientos?q=220-8678", headers=h).json()] == [pm3["id"]]
    assert [m["id"] for m in client.get("/api/mantenimientos?q=juan", headers=h).json()] == [pm3["id"]]
    assert [m["id"] for m in client.get("/api/mantenimientos?fecha_desde=2026-11-21", headers=h).json()] == [
        general["id"]
    ]
    assert client.get(
        "/api/mantenimientos?fecha_desde=2026-11-23&fecha_hasta=2026-11-01", headers=h
    ).status_code == 400

    # Resumen por equipo: último PM y el que sigue en el ciclo
    resumen = client.get("/api/mantenimientos/resumen", headers=h).json()
    assert resumen["962H"]["cantidad"] == 1
    assert resumen["962H"]["ultimo"]["pm"] == "PM3"
    assert resumen["962H"]["proximo"] == {"pm": "PM1", "frecuencia_horas": 1250, "horometro": 9250.0}
    assert resumen["950L"]["proximo"] == {"pm": "PM1", "frecuencia_horas": 250, "horometro": None}
    assert client.get("/api/mantenimientos/resumen", headers=otro).json() == {}

    # Editar: cambia el PM y los repuestos se reemplazan
    editado = client.put(
        f"/api/mantenimientos/{pm3['id']}",
        headers=h,
        json={
            "equipo": "962H",
            "frecuencia_horas": 1250,
            "fecha": "2026-11-20",
            "horometro": 9250,
            "repuestos": _programados(e962, 1250),
        },
    )
    assert editado.status_code == 200, editado.text
    assert editado.json()["pm"] == "PM1" and editado.json()["frecuencia_horas"] == 1250
    assert len(editado.json()["repuestos"]) == 5
    assert editado.json()["responsable"] is None
    assert client.get(f"/api/mantenimientos/{pm3['id']}", headers=h).json()["horometro"] == "9250.0"
    assert client.put(
        f"/api/mantenimientos/{pm3['id']}",
        headers=otro,
        json={"equipo": "962H", "frecuencia_horas": 250, "fecha": "2026-11-20"},
    ).status_code == 404

    # Eliminar
    assert client.delete(f"/api/mantenimientos/{pm3['id']}", headers=otro).status_code == 404
    assert client.delete(f"/api/mantenimientos/{pm3['id']}", headers=h).json() == {"ok": True}
    assert client.get(f"/api/mantenimientos/{pm3['id']}", headers=h).status_code == 404
    assert [m["id"] for m in client.get("/api/mantenimientos", headers=h).json()] == [general["id"]]
