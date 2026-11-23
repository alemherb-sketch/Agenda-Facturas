"""Ventas y compras ligadas a la caja principal."""
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


def test_venta_y_compra_mueven_la_caja_elegida():
    client = _cliente()
    headers = _auth(client, "movimientos@negocio.pe")
    principal = _caja(client, headers, "Caja principal", principal=True, apertura=20)
    otra = _caja(client, headers, "Yape", principal=False)

    venta = _doc(client, headers, caja_id=principal["id"], numero="1", operacion="venta")
    assert venta["operacion"] == "venta"
    assert venta["caja_id"] == principal["id"]
    assert venta["caja_nombre"] == "Caja principal"
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
    assert compra["operacion"] == "compra"
    assert float(compra["total"]) == 80

    movs = client.get("/api/cajas/movimientos", headers=headers).json()
    assert len(movs) == 2
    por_comp = {m["comprobante_id"]: m for m in movs}
    assert por_comp[venta["id"]]["tipo"] == "ingreso"
    assert float(por_comp[venta["id"]]["monto"]) == 150
    assert por_comp[compra["id"]]["tipo"] == "egreso"
    assert float(por_comp[compra["id"]]["monto"]) == 80

    cajas = client.get("/api/cajas", headers=headers).json()
    caja = next(c for c in cajas if c["id"] == principal["id"])
    assert float(caja["total_ingresos"]) == 150
    assert float(caja["total_egresos"]) == 80
    assert float(caja["saldo"]) == 90  # 20 de apertura + 150 - 80

    cambiada = client.put(
        f"/api/comprobantes/{venta['id']}",
        headers=headers,
        json={"caja_id": otra["id"], "operacion": "venta"},
    )
    assert cambiada.status_code == 200, cambiada.text
    movs = client.get("/api/cajas/movimientos", headers=headers).json()
    venta_mov = next(m for m in movs if m["comprobante_id"] == venta["id"])
    assert venta_mov["caja_id"] == otra["id"]

    nota = _doc(
        client,
        headers,
        tipo="nota_credito",
        serie="FC01",
        numero="3",
        operacion="venta",
        caja_id=principal["id"],
        items=[{"descripcion": "Devolución", "cantidad": 1, "precio_unitario": 30, "aplica_igv": False}],
    )
    movs = client.get("/api/cajas/movimientos", headers=headers).json()
    nota_mov = next(m for m in movs if m["comprobante_id"] == nota["id"])
    assert nota_mov["tipo"] == "egreso"

    cotizacion = _doc(
        client,
        headers,
        tipo="cotizacion",
        serie="CT01",
        numero="4",
        caja_id=principal["id"],
    )
    movs = client.get("/api/cajas/movimientos", headers=headers).json()
    assert all(m["comprobante_id"] != cotizacion["id"] for m in movs)

    anulado = client.patch(
        f"/api/comprobantes/{compra['id']}/estado?estado=anulado",
        headers=headers,
    )
    assert anulado.status_code == 200, anulado.text
    movs = client.get("/api/cajas/movimientos", headers=headers).json()
    assert all(m["comprobante_id"] != compra["id"] for m in movs)

    borrado = client.delete(f"/api/cajas/movimientos/{venta_mov['id']}", headers=headers)
    assert borrado.status_code == 200, borrado.text
    doc = client.get(f"/api/comprobantes/{venta['id']}", headers=headers).json()
    assert doc["caja_id"] is None

    dash = client.get("/api/cajas/dashboard?fecha_desde=2026-11-01&fecha_hasta=2026-11-30", headers=headers)
    assert dash.status_code == 200, dash.text
    cuerpo = dash.json()
    assert float(cuerpo["total_egresos"]) >= 30


def test_filtra_comprobantes_por_operacion_y_caja():
    client = _cliente()
    headers = _auth(client, "filtros@negocio.pe")
    principal = _caja(client, headers, "Caja principal", principal=True)
    yape = _caja(client, headers, "Yape")
    _doc(client, headers, caja_id=principal["id"], numero="1", operacion="venta", cliente_nombre="Cliente A")
    _doc(client, headers, caja_id=principal["id"], numero="2", operacion="compra", cliente_nombre="Proveedor B")
    _doc(client, headers, caja_id=yape["id"], numero="3", operacion="venta", cliente_nombre="Cliente C")

    ingresos = client.get(
        f"/api/comprobantes?operacion=ingreso&caja_id={principal['id']}", headers=headers
    ).json()
    assert [d["numero"] for d in ingresos] == ["1"]

    egresos = client.get("/api/comprobantes?operacion=egreso", headers=headers).json()
    assert [d["numero"] for d in egresos] == ["2"]

    en_yape = client.get(f"/api/comprobantes?caja_id={yape['id']}", headers=headers).json()
    assert [d["numero"] for d in en_yape] == ["3"]
    assert en_yape[0]["caja_nombre"] == "Yape"

    invalido = client.get("/api/comprobantes?operacion=otro", headers=headers)
    assert invalido.status_code == 400
