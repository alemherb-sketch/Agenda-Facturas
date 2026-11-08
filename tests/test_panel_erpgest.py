"""Conector con el panel de ERPGEST: firmas, estado, cuentas, suspension, limite y restablecer el acceso.

Correr con: python -m pytest tests -q   (usa una base SQLite temporal, nunca la de la carpeta).
"""
import base64
import json
import os
import sys
import tempfile
import time

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)
_tmp = tempfile.mkdtemp(prefix="agenda-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
os.environ["SECRET_KEY"] = "clave-solo-para-tests"
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
os.chdir(_tmp)  # sin el .env de la carpeta del proyecto

import pytest  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import conector_erpgest as conector  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402  (sin «with»: no arranca el programador de recordatorios)
from app.models import PanelEstado, PanelIngreso, Usuario  # noqa: E402


def _llave():
    privada = Ed25519PrivateKey.generate()
    crudo = privada.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return privada, base64.b64encode(crudo).decode()


@pytest.fixture
def client():
    with SessionLocal() as db:
        db.query(PanelEstado).delete()
        db.query(PanelIngreso).delete()
        db.query(Usuario).delete()  # la cuenta de demostracion incluida: cada prueba cuenta las suyas
        db.commit()
    return TestClient(app)


@pytest.fixture
def panel(monkeypatch):
    privada, publica = _llave()
    monkeypatch.setenv("ERPGEST_CONECTOR_SISTEMA", "agenda")
    monkeypatch.setenv("ERPGEST_CONECTOR_LLAVE", publica)
    return privada


def orden(cliente, privada, operacion, datos=None, sistema="agenda", fecha=None):
    metodo = conector.OPERACIONES[operacion]
    cuerpo = json.dumps(datos).encode() if datos is not None else b""
    fecha = int(time.time()) if fecha is None else fecha
    firma = base64.b64encode(privada.sign(conector.mensaje(fecha, metodo, sistema, operacion, cuerpo))).decode()
    cabeceras = {conector.CABECERA_FECHA: str(fecha), conector.CABECERA_FIRMA: firma}
    url = "/erpgest-conector/v1/" + operacion
    if metodo == "POST":
        return cliente.post(url, content=cuerpo, headers={**cabeceras, "Content-Type": "application/json"})
    return cliente.get(url, headers=cabeceras)


def registrar(cliente, email="ana@negocio.pe", password="secreto8"):
    return cliente.post("/api/auth/registro", json={"nombre": "Ana Quispe", "email": email, "password": password,
                                                     "razon_social": "Bodega Ana"})


def test_sin_configuracion_el_conector_no_existe(client):
    assert client.get("/erpgest-conector/v1/estado").status_code == 404


def test_solo_ordenes_firmadas_para_esta_agenda(client, panel):
    assert client.get("/erpgest-conector/v1/estado").status_code == 401
    otra, _ = _llave()
    assert orden(client, otra, "estado").status_code == 401
    assert orden(client, panel, "estado", sistema="metsalud").status_code == 401
    assert orden(client, panel, "estado", fecha=int(time.time()) - 301).status_code == 401


def test_estado_y_cuentas(client, panel):
    assert registrar(client).status_code == 200
    datos = orden(client, panel, "estado").json()
    assert (datos["sistema"], datos["suspendido"], datos["limite_usuarios"]) == ("agenda", False, 0)
    assert datos["usuarios"] == {"total": 1, "activos": 1, "administradores": 0}
    assert datos["actividad"]["activos_hoy"] == 1
    assert [d["nombre"] for d in datos["datos"]] == ["Comprobantes", "Clientes", "Eventos de agenda"]
    cuenta = orden(client, panel, "usuarios").json()["usuarios"][0]
    assert (cuenta["usuario"], cuenta["rol"], cuenta["activo"]) == ("ana@negocio.pe", "Bodega Ana", True)
    assert cuenta["ultimo_ingreso"].endswith("+00:00")


def test_suspendida_la_pagina_y_el_api_muestran_el_aviso(client, panel):
    token = registrar(client).json()["access_token"]
    orden(client, panel, "suspension", {"suspendido": True, "mensaje": "Pago pendiente."})
    pagina = client.get("/")
    assert pagina.status_code == 503 and "Pago pendiente." in pagina.text
    api = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert api.status_code == 503
    assert api.json() == {"detail": "Pago pendiente.", "motivo": "suspendido"}
    assert client.get("/static/js/api.js").status_code == 200  # el aviso se pinta con estos archivos
    assert orden(client, panel, "estado").json()["suspendido"] is True
    orden(client, panel, "suspension", {"suspendido": False})
    assert client.get("/").status_code == 200


def test_el_limite_frena_registros_y_reactivaciones(client, panel):
    registrar(client)
    assert orden(client, panel, "limite-usuarios", {"limite": 1}).json() == {"limite_usuarios": 1, "activos": 1}
    otra = registrar(client, email="luis@negocio.pe")
    assert otra.status_code == 409
    assert "hasta 1 cuentas activas" in otra.json()["detail"]
    with SessionLocal() as db:
        db.add(Usuario(nombre="Luis", email="luis@negocio.pe", hashed_password="x", activo=False))
        db.commit()
        luis = db.query(Usuario).filter(Usuario.email == "luis@negocio.pe").one().id
    assert orden(client, panel, "usuario-activo", {"usuario": str(luis), "activo": True}).status_code == 409
    orden(client, panel, "limite-usuarios", {"limite": 0})
    assert orden(client, panel, "usuario-activo", {"usuario": str(luis), "activo": True}).json() == {
        "usuario": "luis@negocio.pe", "activo": True}


def test_restablecer_el_acceso_cierra_todas_las_sesiones(client, panel):
    token = registrar(client).json()["access_token"]
    yo = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=yo).status_code == 200
    with SessionLocal() as db:
        cuenta = db.query(Usuario).filter(Usuario.email == "ana@negocio.pe").one()
        cuenta.activo = False
        db.commit()
        uid = cuenta.id
    orden(client, panel, "limite-usuarios", {"limite": 1})
    r = orden(client, panel, "restablecer-acceso", {"usuario": str(uid), "clave": "NuevaClave2026",
                                                    "cerrar_sesiones": True})
    assert r.json() == {"usuario": "ana@negocio.pe", "sesiones_cerradas": True}
    assert client.get("/api/auth/me", headers=yo).status_code == 401
    nuevo = client.post("/api/auth/login", json={"email": "ana@negocio.pe", "password": "NuevaClave2026"})
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {nuevo.json()['access_token']}"}).status_code == 200
    assert orden(client, panel, "restablecer-acceso", {"usuario": "x", "clave": "NuevaClave2026"}).status_code == 404
