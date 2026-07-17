"""Alta / actualización automática de clientes y productos."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Cliente, Producto
from app.schemas import ItemCreate


def _tipo_doc(documento: str | None) -> str:
    if not documento:
        return "OTRO"
    digitos = "".join(c for c in documento if c.isdigit())
    if len(digitos) == 11:
        return "RUC"
    if len(digitos) == 8:
        return "DNI"
    return "OTRO"


def upsert_cliente(
    db: Session,
    usuario_id: int,
    *,
    nombre: str,
    documento: str | None = None,
    email: str | None = None,
    telefono: str | None = None,
    direccion: str | None = None,
) -> Cliente:
    nombre = (nombre or "").strip()
    documento = (documento or "").strip() or None
    cliente = None

    if documento:
        cliente = (
            db.query(Cliente)
            .filter(Cliente.usuario_id == usuario_id, Cliente.documento == documento)
            .first()
        )
    if not cliente and nombre:
        query = db.query(Cliente).filter(
            Cliente.usuario_id == usuario_id,
            func.lower(Cliente.nombre) == nombre.lower(),
        )
        if not documento:
            query = query.filter(Cliente.documento.is_(None))
        cliente = query.first()

    if not cliente:
        cliente = Cliente(
            usuario_id=usuario_id,
            nombre=nombre,
            documento=documento,
            tipo_documento=_tipo_doc(documento),
            email=email,
            telefono=telefono,
            direccion=direccion,
        )
        db.add(cliente)
        db.flush()
        return cliente

    cliente.nombre = nombre or cliente.nombre
    if documento:
        cliente.documento = documento
        cliente.tipo_documento = _tipo_doc(documento)
    if email:
        cliente.email = email
    if telefono:
        cliente.telefono = telefono
    if direccion:
        cliente.direccion = direccion
    db.flush()
    return cliente


def upsert_producto(
    db: Session,
    usuario_id: int,
    *,
    descripcion: str,
    precio_unitario: Decimal,
    unidad: str = "NIU",
    tipo: str = "producto",
) -> Producto:
    nombre = (descripcion or "").strip()
    producto = (
        db.query(Producto)
        .filter(
            Producto.usuario_id == usuario_id,
            func.lower(Producto.nombre) == nombre.lower(),
        )
        .first()
    )
    if not producto:
        producto = Producto(
            usuario_id=usuario_id,
            nombre=nombre,
            precio_unitario=precio_unitario,
            unidad=unidad or "NIU",
            tipo=tipo if tipo in {"producto", "servicio"} else "producto",
        )
        db.add(producto)
        db.flush()
        return producto

    producto.precio_unitario = precio_unitario
    if unidad:
        producto.unidad = unidad
    if tipo in {"producto", "servicio"}:
        producto.tipo = tipo
    db.flush()
    return producto


def upsert_productos_desde_items(
    db: Session,
    usuario_id: int,
    items: list[ItemCreate],
) -> None:
    for item in items:
        # Heurística simple: si la descripción sugiere servicio
        texto = item.descripcion.lower()
        tipo = "servicio" if any(k in texto for k in ("servicio", "asesor", "consult", "manten")) else "producto"
        upsert_producto(
            db,
            usuario_id,
            descripcion=item.descripcion,
            precio_unitario=item.precio_unitario,
            unidad=item.unidad or "NIU",
            tipo=tipo,
        )
