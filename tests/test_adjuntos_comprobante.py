"""Adjuntos de un comprobante: ver, agregar y reemplazar el archivo."""
import os
import sys
import tempfile

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)
_tmp = tempfile.mkdtemp(prefix="agenda-adjuntos-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
os.environ["SECRET_KEY"] = "clave-solo-para-tests"
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def _auth(client, email):
    res = client.post(
        "/api/auth/registro",
        json={"nombre": "Adjuntos Test", "email": email, "password": "secreto8"},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _crear_ticket(client, headers):
    res = client.post(
        "/api/comprobantes",
        headers=headers,
        json={
            "tipo": "ticket",
            "serie": "T001",
            "numero": "099",
            "fecha_emision": "2026-11-24",
            "cliente_nombre": "CARLOS BRANDER CRUZ AGUILAR",
            "cliente_documento": "44643253",
            "zona": "Otros",
            "motivo": "Pago de correos",
            "items": [
                {
                    "descripcion": "Pago de correos corporativos",
                    "cantidad": 1,
                    "precio_unitario": 533,
                    "aplica_igv": False,
                }
            ],
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_agregar_ver_y_reemplazar_adjunto():
    client = TestClient(app)
    headers = _auth(client, "adjuntos1@negocio.pe")
    otro = _auth(client, "adjuntos2@negocio.pe")
    doc = _crear_ticket(client, headers)
    assert doc["adjuntos"] == []

    subido = client.post(
        f"/api/comprobantes/{doc['id']}/adjuntos",
        headers=headers,
        files=[
            ("archivos", ("voucher.pdf", b"%PDF-1.4 voucher", "application/pdf")),
            ("archivos", ("foto.png", b"\x89PNG\r\n\x1a\nimagen", "image/png")),
        ],
    )
    assert subido.status_code == 200, subido.text
    nombres = {a["nombre"] for a in subido.json()["adjuntos"]}
    assert nombres == {"voucher.pdf", "foto.png"}
    pdf = next(a for a in subido.json()["adjuntos"] if a["nombre"] == "voucher.pdf")
    imagen = next(a for a in subido.json()["adjuntos"] if a["nombre"] == "foto.png")
    assert pdf["tipo_icono"] == "pdf"
    assert imagen["es_imagen"] is True

    ver = client.get(f"/api/adjuntos/{pdf['id']}", headers=headers)
    assert ver.status_code == 200
    assert ver.content == b"%PDF-1.4 voucher"

    cambio = client.post(
        f"/api/adjuntos/{pdf['id']}/reemplazar",
        headers=headers,
        files={"archivo": ("voucher-nuevo.pdf", b"%PDF-1.4 nuevo", "application/pdf")},
    )
    assert cambio.status_code == 200, cambio.text
    assert cambio.json()["id"] == pdf["id"]
    assert cambio.json()["nombre"] == "voucher-nuevo.pdf"

    ver_nuevo = client.get(f"/api/adjuntos/{pdf['id']}", headers=headers)
    assert ver_nuevo.content == b"%PDF-1.4 nuevo"

    lista = client.get(f"/api/comprobantes/{doc['id']}/adjuntos", headers=headers)
    assert lista.status_code == 200
    assert len(lista.json()) == 2
    assert {a["nombre"] for a in lista.json()} == {"voucher-nuevo.pdf", "foto.png"}

    ajeno = client.post(
        f"/api/adjuntos/{pdf['id']}/reemplazar",
        headers=otro,
        files={"archivo": ("intruso.pdf", b"%PDF-1.4 no", "application/pdf")},
    )
    assert ajeno.status_code == 404
