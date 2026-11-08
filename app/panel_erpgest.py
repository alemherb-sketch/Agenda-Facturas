"""Conector con el panel de ERPGEST (el proveedor): cuentas, actividad, suspension, limite y acceso.

El panel de ERPGEST (Panel > Subdominios) da ordenes firmadas con Ed25519 a
/erpgest-conector/v1/<operacion>. Este modulo las comprueba con
conector_erpgest.py (copiado tal cual de ERPGEST) y las cumple con las reglas de
Agenda Facturas. Sin ERPGEST_CONECTOR_SISTEMA y ERPGEST_CONECTOR_LLAVE en el
entorno el conector no existe (404) y la suspension no se consulta.

Aqui cada usuario se registra solo y es su propia cuenta: el limite de usuarios
frena el registro publico y las reactivaciones; no hay administradores.
"""
import json
from datetime import datetime, timedelta, timezone
from html import escape

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app import conector_erpgest as conector
from app.auth import hash_password
from app.database import SessionLocal
from app.models import Agenda, Cliente, Comprobante, PanelEstado, PanelIngreso, Usuario

MAXIMO_USUARIOS = 500
LIMA = timezone(timedelta(hours=-5))  # el Peru no tiene horario de verano
MENSAJE_LIMITE = ("Este servicio admite hasta {n} cuentas activas. Para ampliarlo, "
                  "comuniquese con su proveedor (ERPGEST).")

router = APIRouter(prefix="/erpgest-conector/v1", tags=["conector ERPGEST"], include_in_schema=False)


def ahora_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Reglas -------------------------------------------------------------------

def leer_estado(db):
    """El estado vigente; sin fila, uno nuevo sin guardar (sistema normal y sin limite)."""
    return (db.query(PanelEstado).filter(PanelEstado.id == 1).first()
            or PanelEstado(id=1, suspendido=False, mensaje="", limite_usuarios=0))


def _activos(db, excluir=None):
    q = db.query(Usuario).filter(Usuario.activo.is_(True))
    return q.filter(Usuario.id != excluir) if excluir is not None else q


def error_de_limite(db, usuario_id, activo):
    """Texto del aviso si dejar activa esta cuenta pasaria del limite contratado; "" si se puede."""
    limite = leer_estado(db).limite_usuarios or 0
    if not limite or not activo:
        return ""
    if usuario_id is not None and _activos(db).filter(Usuario.id == usuario_id).first() is not None:
        return ""
    return MENSAJE_LIMITE.format(n=limite) if _activos(db, excluir=usuario_id).count() >= limite else ""


def registrar_ingreso(db, usuario):
    try:
        fila = db.query(PanelIngreso).filter(PanelIngreso.usuario_id == usuario.id).first()
        if fila is None:
            db.add(PanelIngreso(usuario_id=usuario.id, ultimo=ahora_utc()))
        else:
            fila.ultimo = ahora_utc()
        db.commit()
    except IntegrityError:  # dos ingresos a la vez de la misma cuenta: basta con uno
        db.rollback()


# --- Operaciones --------------------------------------------------------------

def _iso(valor):
    return valor.replace(tzinfo=timezone.utc).isoformat() if valor else None


def _json(datos, status=200):
    return JSONResponse(datos, status_code=status, headers={"Cache-Control": "no-store"})


def _estado(db, datos, sistema):
    ahora = ahora_utc()
    inicio_hoy = (datetime.now(LIMA).replace(hour=0, minute=0, second=0, microsecond=0)
                  .astimezone(timezone.utc).replace(tzinfo=None))
    estado = leer_estado(db)
    ingresos = db.query(PanelIngreso)

    def ingresaron(desde):
        return ingresos.filter(PanelIngreso.ultimo >= desde).count()

    return _json({
        "protocolo": 1, "sistema": sistema, "version": None, "hora": _iso(ahora),
        "suspendido": bool(estado.suspendido), "mensaje_suspension": estado.mensaje or "",
        "limite_usuarios": estado.limite_usuarios or 0,
        "usuarios": {"total": db.query(Usuario).count(), "activos": _activos(db).count(), "administradores": 0},
        "actividad": {"ultimo_ingreso": _iso(db.query(func.max(PanelIngreso.ultimo)).scalar()),
                      "activos_hoy": ingresaron(inicio_hoy), "activos_7d": ingresaron(ahora - timedelta(days=7)),
                      "activos_30d": ingresaron(ahora - timedelta(days=30))},
        "datos": [
            {"nombre": "Comprobantes", "valor": db.query(Comprobante).count()},
            {"nombre": "Clientes", "valor": db.query(Cliente).count()},
            {"nombre": "Eventos de agenda", "valor": db.query(Agenda).count()},
        ],
    })


def _usuarios(db, datos, sistema):
    ultimos = dict(db.query(PanelIngreso.usuario_id, PanelIngreso.ultimo).all())
    usuarios = db.query(Usuario).order_by(Usuario.activo.desc(), Usuario.email)
    lista = [{
        "id": str(u.id), "usuario": u.email, "nombre": u.nombre or u.email, "email": u.email,
        "rol": u.razon_social or (f"RUC {u.ruc_empresa}" if u.ruc_empresa else None), "administrador": False,
        "activo": bool(u.activo), "ultimo_ingreso": _iso(ultimos.get(u.id)), "creado": _iso(u.creado_en),
    } for u in usuarios.limit(MAXIMO_USUARIOS)]
    return _json({"total": usuarios.count(), "usuarios": lista})


def _suspension(db, datos, sistema):
    estado = leer_estado(db)
    estado.suspendido = bool(datos.get("suspendido"))
    estado.mensaje = str(datos.get("mensaje") or "").strip()[:300] if estado.suspendido else ""
    db.add(estado)
    db.commit()
    return _json({"suspendido": estado.suspendido, "mensaje_suspension": estado.mensaje})


def _limite(db, datos, sistema):
    limite = datos.get("limite")
    if not isinstance(limite, int) or isinstance(limite, bool) or limite < 0:
        return _json({"error": "El limite debe ser un numero entero de 0 en adelante."}, 400)
    estado = leer_estado(db)
    estado.limite_usuarios = limite
    db.add(estado)
    db.commit()
    return _json({"limite_usuarios": limite, "activos": _activos(db).count()})


def _usuario(db, datos):
    try:
        return db.query(Usuario).filter(Usuario.id == int(str(datos.get("usuario")))).first()
    except (TypeError, ValueError):
        return None


def _restablecer_acceso(db, datos, sistema):
    usuario = _usuario(db, datos)
    if usuario is None:
        return _json({"error": "No existe esa cuenta."}, 404)
    clave = datos.get("clave")
    if not isinstance(clave, str) or len(clave) < 8:
        return _json({"error": "La contraseña debe tener al menos 8 caracteres."}, 400)
    cerrar = bool(datos.get("cerrar_sesiones"))
    usuario.hashed_password = hash_password(clave)
    usuario.activo = True  # devolver el acceso no cuenta contra el limite
    if cerrar:
        estado = leer_estado(db)
        estado.sesiones_desde = ahora_utc()  # los tokens emitidos antes ya no valen (auth.get_current_user)
        db.add(estado)
    db.commit()
    return _json({"usuario": usuario.email, "sesiones_cerradas": cerrar})


def _usuario_activo(db, datos, sistema):
    usuario = _usuario(db, datos)
    if usuario is None:
        return _json({"error": "No existe esa cuenta."}, 404)
    activo = bool(datos.get("activo"))
    if activo:
        mensaje = error_de_limite(db, usuario.id, True)
        if mensaje:
            return _json({"error": mensaje}, 409)
    usuario.activo = activo
    db.commit()
    return _json({"usuario": usuario.email, "activo": activo})


OPERACIONES = {"estado": _estado, "usuarios": _usuarios, "suspension": _suspension, "limite-usuarios": _limite,
               "restablecer-acceso": _restablecer_acceso, "usuario-activo": _usuario_activo}


def _atender(operacion, datos, sistema):
    with SessionLocal() as db:
        return OPERACIONES[operacion](db, datos, sistema)


@router.api_route("/{operacion}", methods=["GET", "POST"])
async def orden(operacion: str, request: Request):
    configuracion = conector.configuracion()
    if configuracion is None or operacion not in OPERACIONES:
        return _json({"error": "No existe."}, 404)
    sistema, llave = configuracion
    cuerpo = await request.body()
    try:
        conector.verificar(request.method, operacion, cuerpo, request.headers.get(conector.CABECERA_FECHA),
                           request.headers.get(conector.CABECERA_FIRMA), sistema, llave)
    except conector.FirmaInvalida:
        return _json({"error": "firma"}, 401)
    if request.method != conector.OPERACIONES[operacion]:
        return _json({"error": "Metodo no permitido."}, 405)
    try:
        datos = json.loads(cuerpo) if cuerpo else {}
    except ValueError:
        return _json({"error": "El cuerpo no es JSON."}, 400)
    if not isinstance(datos, dict):
        return _json({"error": "El cuerpo debe ser un objeto JSON."}, 400)
    return await run_in_threadpool(_atender, operacion, datos, sistema)


# --- Suspension ---------------------------------------------------------------

PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Servicio suspendido</title>
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#f1f5f9;color:#0f172a;
font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}main{{max-width:460px;margin:24px;padding:32px;
background:#fff;border-radius:16px;box-shadow:0 10px 30px rgba(15,23,42,.08);text-align:center}}
h1{{font-size:1.3rem;margin:.6rem 0}}p{{color:#475569;line-height:1.5;margin:0}}</style>
</head><body><main><div style="font-size:2.2rem" aria-hidden="true">&#9208;</div><h1>Servicio suspendido</h1>
<p>{mensaje}</p></main></body></html>"""


def _suspendido():
    with SessionLocal() as db:
        estado = db.query(PanelEstado).filter(PanelEstado.id == 1).first()
        return (estado.mensaje or "El servicio esta suspendido temporalmente.") if estado and estado.suspendido else None


class MiddlewareSuspension(BaseHTTPMiddleware):
    """Con el sistema suspendido desde el panel, toda ruta responde 503 con el aviso del proveedor: una pagina para
    el navegador y JSON con motivo "suspendido" para el API (api.js lo muestra a pantalla completa). Solo siguen el
    conector, para poder reactivarlo, y los archivos estaticos. Los datos no se tocan."""

    async def dispatch(self, request, call_next):
        ruta = request.url.path
        if (conector.configuracion() is not None and not ruta.startswith(conector.PREFIJO)
                and not ruta.startswith("/static/")):
            mensaje = await run_in_threadpool(_suspendido)
            if mensaje:
                if ruta.startswith("/api/"):
                    return JSONResponse({"detail": mensaje, "motivo": "suspendido"}, status_code=503,
                                        headers={"Cache-Control": "no-store"})
                return HTMLResponse(PAGINA.format(mensaje=escape(mensaje)), status_code=503,
                                    headers={"Cache-Control": "no-store"})
        return await call_next(request)
