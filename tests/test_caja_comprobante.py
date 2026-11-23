"""Los comprobantes son egresos y no se vinculan a ninguna caja."""
import os
import sys
import tempfile

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)
_tmp = tempfile.mkdtemp(prefix="agenda-caja-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
os.environ["SECRET_KEY"] = "clave-solo-para-tests"
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def _cliente():
    return TestClient(app)


def _auth(client, email="caja@negocio.pe"):
    res = client.post(
        "/api/auth/registro",
        json={"nombre": "Caja Test", "email": email, "password": "secreto8"},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _caja(client, headers, nombre, principal=False, apertura=0):
    res = client.post(
        "/api/cajas",
        headers=headers,
        json={
            "nombre": nombre,
            "monto_apertura": apertura,
            "es_principal": principal,
            "fecha_apertura": "2026-11-01",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _doc(client, headers, **extra):
    body = {
        "tipo": "nota_venta",
        "serie": "NV01",
        "numero": "10",
        "fecha_emision": "2026-11-02",
        "estado": "emitido",
        "cliente_nombre": "Cliente Sur",
        "operacion": "venta",
        "items": [
            {"descripcion": "Flete", "cantidad": 1, "precio_unitario": 150, "aplica_igv": False}
        ],
    }
    body.update(extra)
    res = client.post("/api/comprobantes", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()


def test_una_sola_caja_principal():
    client = _cliente()
    headers = _auth(client, "principal@negocio.pe")
    primera = _caja(client, headers, "Caja chica", principal=True)
    segunda = _caja(client, headers, "Caja banco", principal=True)
    lista = client.get("/api/cajas", headers=headers).json()
    por_id = {c["id"]: c for c in lista}
    assert por_id[primera["id"]]["es_principal"] is False
    assert por_id[segunda["id"]]["es_principal"] is True
    assert lista[0]["id"] == segunda["id"]


def test_comprobante_no_mueve_la_caja_y_el_dashboard_resta_egresos():
    client = _cliente()
    headers = _auth(client, "movimientos@negocio.pe")
    principal = _caja(client, headers, "Caja principal", principal=True, apertura=20)
    otra = _caja(client, headers, "Yape", principal=False)

    venta = _doc(client, headers, caja_id=principal["id"], numero="1", operacion="venta")
    assert venta["caja_id"] is None
    assert venta["caja_nombre"] is None
    assert float(venta["total"]) == 150

    compra = _doc(
        client,
        headers,
        caja_id=principal["id"],
        numero="2",
        operacion="compra",
        cliente_nombre="Proveedor Norte",
        items=[{"descripcion": "Repuesto", "cantidad": 2, "precio_unitario": 40, "aplica_igv": False}],
    )
    assert compra["caja_id"] is None
    assert float(compra["total"]) == 80

    manual = client.post(
        "/api/cajas/movimientos",
        headers=headers,
        json={
            "caja_id": principal["id"],
            "tipo": "ingreso",
            "monto": 50,
            "concepto": "Aporte manual",
            "fecha": "2026-11-03",
        },
    )
    assert manual.status_code == 201, manual.text

    movs = client.get("/api/cajas/movimientos", headers=headers).json()
    assert len(movs) == 1
    assert movs[0]["comprobante_id"] is None
    assert float(movs[0]["monto"]) == 50

    cajas = client.get("/api/cajas", headers=headers).json()
    caja = next(c for c in cajas if c["id"] == principal["id"])
    assert float(caja["saldo"]) == 70  # 20 de apertura + 50 manual

    panel = client.get("/api/dashboard", headers=headers)
    assert panel.status_code == 200, panel.text
    assert float(panel.json()["total_egresos_comprobantes"]) == 230

    cambiada = client.put(
        f"/api/comprobantes/{venta['id']}",
        headers=headers,
        json={"caja_id": otra["id"], "operacion": "compra"},
    )
    assert cambiada.status_code == 200, cambiada.text
    assert cambiada.json()["caja_id"] is None
    assert cambiada.json()["operacion"] == "venta"
    movs = client.get("/api/cajas/movimientos", headers=headers).json()
    assert len(movs) == 1
    assert movs[0]["comprobante_id"] is None

    anulado = client.patch(
        f"/api/comprobantes/{compra['id']}/estado?estado=anulado",
        headers=headers,
    )
    assert anulado.status_code == 200, anulado.text
    assert anulado.json()["caja_id"] is None
    panel = client.get("/api/dashboard", headers=headers).json()
    assert float(panel["total_egresos_comprobantes"]) == 150


def test_desvincular_quita_el_movimiento_ligado_y_conserva_el_manual():
    from datetime import date

    from app.database import SessionLocal
    from app.models import Comprobante, MovimientoCaja, TipoMovimientoCaja
    from app.services.caja_comprobante import desvincular_comprobantes_de_cajas

    client = _cliente()
    headers = _auth(client, "limpieza@negocio.pe")
    principal = _caja(client, headers, "Caja principal", principal=True, apertura=10)
    doc = _doc(client, headers, numero="9")
    manual = client.post(
        "/api/cajas/movimientos",
        headers=headers,
        json={
            "caja_id": principal["id"],
            "tipo": "egreso",
            "monto": 4,
            "concepto": "Salida manual",
            "fecha": "2026-11-04",
        },
    )
    assert manual.status_code == 201, manual.text

    db = SessionLocal()
    try:
        guardado = db.get(Comprobante, doc["id"])
        guardado.caja_id = principal["id"]
        db.add(
            MovimientoCaja(
                usuario_id=guardado.usuario_id,
                caja_id=principal["id"],
                comprobante_id=guardado.id,
                tipo=TipoMovimientoCaja.INGRESO,
                monto=guardado.total,
                concepto="Venta antigua",
                fecha=date(2026, 11, 2),
            )
        )
        db.commit()
        desvincular_comprobantes_de_cajas(db)
    finally:
        db.close()

    revisado = client.get(f"/api/comprobantes/{doc['id']}", headers=headers).json()
    assert revisado["caja_id"] is None
    movs = client.get("/api/cajas/movimientos", headers=headers).json()
    assert len(movs) == 1
    assert movs[0]["concepto"] == "Salida manual"
    caja = next(c for c in client.get("/api/cajas", headers=headers).json() if c["id"] == principal["id"])
    assert float(caja["saldo"]) == 6  # 10 de apertura − 4 manual


def test_filtra_comprobantes_por_operacion_sin_vincular_caja():
    client = _cliente()
    headers = _auth(client, "filtros@negocio.pe")
    principal = _caja(client, headers, "Caja principal", principal=True)
    yape = _caja(client, headers, "Yape")
    primero = _doc(client, headers, caja_id=principal["id"], numero="1", operacion="venta", cliente_nombre="Cliente A")
    _doc(client, headers, caja_id=principal["id"], numero="2", operacion="compra", cliente_nombre="Proveedor B")
    tercero = _doc(client, headers, caja_id=yape["id"], numero="3", operacion="venta", cliente_nombre="Cliente C")
    assert primero["caja_id"] is None
    assert tercero["caja_nombre"] is None

    ingresos = client.get("/api/comprobantes?operacion=ingreso", headers=headers).json()
    assert sorted(d["numero"] for d in ingresos) == ["1", "3"]

    egresos = client.get("/api/comprobantes?operacion=egreso", headers=headers).json()
    assert [d["numero"] for d in egresos] == ["2"]

    en_yape = client.get(f"/api/comprobantes?caja_id={yape['id']}", headers=headers).json()
    assert en_yape == []

    invalido = client.get("/api/comprobantes?operacion=otro", headers=headers)
    assert invalido.status_code == 400

    panel = client.get("/api/dashboard", headers=headers).json()
    assert float(panel["total_egresos_comprobantes"]) == 450
