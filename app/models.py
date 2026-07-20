from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TipoDocumento(str, enum.Enum):
    FACTURA = "factura"
    BOLETA = "boleta"
    NOTA_VENTA = "nota_venta"
    COTIZACION = "cotizacion"
    NOTA_CREDITO = "nota_credito"
    NOTA_DEBITO = "nota_debito"
    RECIBO_HONORARIOS = "recibo_honorarios"
    GUIA_REMISION = "guia_remision"
    TICKET = "ticket"


class EstadoComprobante(str, enum.Enum):
    EMITIDO = "emitido"
    PAGADO = "pagado"
    NO_PAGADO = "no_pagado"
    ANULADO = "anulado"


class TipoAgenda(str, enum.Enum):
    REUNION = "reunion"
    CITA = "cita"
    NOTA = "nota"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(20))
    ruc_empresa: Mapped[str | None] = mapped_column(String(11))
    razon_social: Mapped[str | None] = mapped_column(String(200))
    direccion: Mapped[str | None] = mapped_column(String(250))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32))
    notificar_email: Mapped[bool] = mapped_column(Boolean, default=True)

    comprobantes: Mapped[list[Comprobante]] = relationship(back_populates="usuario", cascade="all, delete-orphan")
    agendas: Mapped[list[Agenda]] = relationship(back_populates="usuario", cascade="all, delete-orphan")
    clientes: Mapped[list[Cliente]] = relationship(back_populates="usuario", cascade="all, delete-orphan")
    productos: Mapped[list[Producto]] = relationship(back_populates="usuario", cascade="all, delete-orphan")
    suscripciones: Mapped[list[PushSubscription]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )


class Cliente(Base):
    __tablename__ = "clientes"
    __table_args__ = (UniqueConstraint("usuario_id", "documento", name="uq_cliente_doc"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    documento: Mapped[str | None] = mapped_column(String(15))
    tipo_documento: Mapped[str | None] = mapped_column(String(10), default="RUC")
    email: Mapped[str | None] = mapped_column(String(180))
    telefono: Mapped[str | None] = mapped_column(String(20))
    direccion: Mapped[str | None] = mapped_column(String(250))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    usuario: Mapped[Usuario] = relationship(back_populates="clientes")
    comprobantes: Mapped[list[Comprobante]] = relationship(back_populates="cliente")


class Producto(Base):
    __tablename__ = "productos"
    __table_args__ = (UniqueConstraint("usuario_id", "nombre", name="uq_producto_nombre"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(300), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), default="producto")  # producto | servicio
    codigo: Mapped[str | None] = mapped_column(String(40))
    unidad: Mapped[str] = mapped_column(String(20), default="NIU")
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    usuario: Mapped[Usuario] = relationship(back_populates="productos")


class Comprobante(Base):
    __tablename__ = "comprobantes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"))
    tipo: Mapped[TipoDocumento] = mapped_column(Enum(TipoDocumento, native_enum=False), nullable=False)
    serie: Mapped[str] = mapped_column(String(10), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_emision: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date)
    moneda: Mapped[str] = mapped_column(String(3), default="PEN")
    igv: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    estado: Mapped[EstadoComprobante] = mapped_column(
        Enum(EstadoComprobante, native_enum=False), default=EstadoComprobante.EMITIDO
    )
    observaciones: Mapped[str | None] = mapped_column(Text)
    cliente_nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    cliente_documento: Mapped[str | None] = mapped_column(String(15))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    usuario: Mapped[Usuario] = relationship(back_populates="comprobantes")
    cliente: Mapped[Cliente | None] = relationship(back_populates="comprobantes")
    items: Mapped[list[ComprobanteItem]] = relationship(
        back_populates="comprobante", cascade="all, delete-orphan"
    )


class ComprobanteItem(Base):
    __tablename__ = "comprobante_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comprobante_id: Mapped[int] = mapped_column(ForeignKey("comprobantes.id"), index=True)
    descripcion: Mapped[str] = mapped_column(String(300), nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unidad: Mapped[str] = mapped_column(String(20), default="NIU")
    aplica_igv: Mapped[bool] = mapped_column(Boolean, default=True)

    comprobante: Mapped[Comprobante] = relationship(back_populates="items")


class Agenda(Base):
    __tablename__ = "agendas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    tipo: Mapped[TipoAgenda] = mapped_column(Enum(TipoAgenda, native_enum=False), nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime)
    ubicacion: Mapped[str | None] = mapped_column(String(250))
    participantes: Mapped[str | None] = mapped_column(Text)
    completado: Mapped[bool] = mapped_column(Boolean, default=False)
    recordatorio_minutos: Mapped[int] = mapped_column(Integer, default=30)
    notificado: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    usuario: Mapped[Usuario] = relationship(back_populates="agendas")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    usuario: Mapped[Usuario] = relationship(back_populates="suscripciones")


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), default="info")
    leida: Mapped[bool] = mapped_column(Boolean, default=False)
    enlace: Mapped[str | None] = mapped_column(String(250))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SistemaConfig(Base):
    """Claves y ajustes persistentes (sobreviven redeploys en Railway)."""

    __tablename__ = "sistema_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clave: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    valor: Mapped[str] = mapped_column(Text, nullable=False)
