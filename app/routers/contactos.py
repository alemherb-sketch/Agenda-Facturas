from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Contacto, Usuario
from app.schemas import (
    ClienteOut,
    ContactoCreate,
    ContactoImportIn,
    ContactoImportOut,
    ContactoOut,
    ContactoUpdate,
)
from app.services.catalogo import upsert_cliente

router = APIRouter(prefix="/api/contactos", tags=["contactos"])


def _norm_tel(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(c for c in value if c.isdigit() or c == "+")
    return digits[:40] or None


def _clean(value: str | None, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if max_len:
        return text[:max_len]
    return text


def _get_owned(db: Session, user: Usuario, contacto_id: int) -> Contacto:
    item = (
        db.query(Contacto)
        .filter(Contacto.id == contacto_id, Contacto.usuario_id == user.id, Contacto.activo.is_(True))
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    return item


def _find_by_phone(db: Session, user_id: int, telefono: str | None) -> Contacto | None:
    tel = _norm_tel(telefono)
    if not tel:
        return None
    # Match last 9 digits (Perú móvil) or full string
    suffix = tel[-9:] if len(tel) >= 9 else tel
    rows = (
        db.query(Contacto)
        .filter(Contacto.usuario_id == user_id, Contacto.activo.is_(True))
        .all()
    )
    for row in rows:
        for cand in (row.telefono, row.telefono_alt):
            n = _norm_tel(cand)
            if not n:
                continue
            if n == tel or n.endswith(suffix) or tel.endswith(n[-9:] if len(n) >= 9 else n):
                return row
    return None


@router.get("", response_model=list[ContactoOut])
def listar(
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = None,
    limit: int = Query(300, le=500),
):
    query = (
        db.query(Contacto)
        .filter(Contacto.usuario_id == user.id, Contacto.activo.is_(True))
        .order_by(Contacto.nombre.asc())
    )
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Contacto.nombre.ilike(like),
                Contacto.telefono.ilike(like),
                Contacto.telefono_alt.ilike(like),
                Contacto.email.ilike(like),
                Contacto.empresa.ilike(like),
            )
        )
    return query.limit(limit).all()


@router.post("", response_model=ContactoOut, status_code=201)
def crear(
    payload: ContactoCreate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    nombre = payload.nombre.strip()
    telefono = _norm_tel(payload.telefono)
    if telefono:
        existing = _find_by_phone(db, user.id, telefono)
        if existing:
            existing.nombre = nombre
            existing.telefono = telefono or existing.telefono
            existing.telefono_alt = _norm_tel(payload.telefono_alt) or existing.telefono_alt
            existing.email = _clean(payload.email, 180) or existing.email
            existing.empresa = _clean(payload.empresa, 200) or existing.empresa
            existing.notas = _clean(payload.notas, 500) or existing.notas
            db.commit()
            db.refresh(existing)
            return existing

    contacto = Contacto(
        usuario_id=user.id,
        nombre=nombre,
        telefono=telefono,
        telefono_alt=_norm_tel(payload.telefono_alt),
        email=_clean(payload.email, 180),
        empresa=_clean(payload.empresa, 200),
        notas=_clean(payload.notas, 500),
        origen=payload.origen if payload.origen in {"manual", "telefono"} else "manual",
    )
    db.add(contacto)
    db.commit()
    db.refresh(contacto)
    return contacto


@router.post("/importar", response_model=ContactoImportOut)
def importar(
    payload: ContactoImportIn,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    creados = 0
    actualizados = 0
    omitidos = 0
    result: list[Contacto] = []
    existentes = (
        db.query(Contacto)
        .filter(Contacto.usuario_id == user.id, Contacto.activo.is_(True))
        .all()
    )

    def match_phone(telefono: str | None) -> Contacto | None:
        tel = _norm_tel(telefono)
        if not tel:
            return None
        suffix = tel[-9:] if len(tel) >= 9 else tel
        for row in existentes:
            for cand in (row.telefono, row.telefono_alt):
                n = _norm_tel(cand)
                if not n:
                    continue
                if n == tel or n.endswith(suffix) or tel.endswith(n[-9:] if len(n) >= 9 else n):
                    return row
        return None

    for item in payload.contactos:
        nombre = (item.nombre or "").strip()
        telefono = _norm_tel(item.telefono)
        telefono_alt = _norm_tel(item.telefono_alt)
        email = _clean(item.email, 180)
        empresa = _clean(item.empresa, 200)
        if not nombre:
            omitidos += 1
            continue
        if not telefono and not email:
            omitidos += 1
            continue

        existing = match_phone(telefono) if telefono else None
        if existing is None and email:
            existing = next((r for r in existentes if (r.email or "").lower() == email.lower()), None)

        if existing:
            existing.nombre = nombre or existing.nombre
            if telefono:
                existing.telefono = telefono
            if telefono_alt:
                existing.telefono_alt = telefono_alt
            if email:
                existing.email = email
            if empresa:
                existing.empresa = empresa
            if existing.origen != "telefono":
                existing.origen = "telefono"
            actualizados += 1
            result.append(existing)
        else:
            contacto = Contacto(
                usuario_id=user.id,
                nombre=nombre,
                telefono=telefono,
                telefono_alt=telefono_alt,
                email=email,
                empresa=empresa,
                origen="telefono",
            )
            db.add(contacto)
            existentes.append(contacto)
            creados += 1
            result.append(contacto)

    db.commit()
    for c in result:
        db.refresh(c)

    return ContactoImportOut(
        creados=creados,
        actualizados=actualizados,
        omitidos=omitidos,
        total=creados + actualizados,
        contactos=result[:50],
    )


@router.put("/{contacto_id}", response_model=ContactoOut)
def actualizar(
    contacto_id: int,
    payload: ContactoUpdate,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    contacto = _get_owned(db, user, contacto_id)
    data = payload.model_dump(exclude_unset=True)
    if "nombre" in data and data["nombre"]:
        data["nombre"] = data["nombre"].strip()
    if "telefono" in data:
        data["telefono"] = _norm_tel(data["telefono"])
    if "telefono_alt" in data:
        data["telefono_alt"] = _norm_tel(data["telefono_alt"])
    for key in ("email", "empresa", "notas"):
        if key in data:
            data[key] = _clean(data[key], 500 if key == "notas" else 200 if key == "empresa" else 180)
    for key, value in data.items():
        setattr(contacto, key, value)
    db.commit()
    db.refresh(contacto)
    return contacto


@router.delete("/{contacto_id}")
def eliminar(
    contacto_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    contacto = _get_owned(db, user, contacto_id)
    contacto.activo = False
    db.commit()
    return {"ok": True}


@router.post("/{contacto_id}/a-cliente", response_model=ClienteOut)
def convertir_a_cliente(
    contacto_id: int,
    user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    contacto = _get_owned(db, user, contacto_id)
    cliente = upsert_cliente(
        db,
        user.id,
        nombre=contacto.nombre,
        email=contacto.email,
        telefono=contacto.telefono or contacto.telefono_alt,
        direccion=None,
    )
    contacto.cliente_id = cliente.id
    db.commit()
    db.refresh(cliente)
    return cliente
