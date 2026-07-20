from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import EstadoComprobante, TipoAgenda, TipoDocumento


class UsuarioCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    telefono: str | None = None
    ruc_empresa: str | None = None
    razon_social: str | None = None
    direccion: str | None = None


class UsuarioLogin(BaseModel):
    email: EmailStr
    password: str


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: EmailStr
    telefono: str | None = None
    ruc_empresa: str | None = None
    razon_social: str | None = None
    direccion: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class ItemCreate(BaseModel):
    descripcion: str = Field(min_length=1, max_length=300)
    cantidad: Decimal = Field(gt=0)
    precio_unitario: Decimal = Field(ge=0)
    unidad: str = "NIU"
    aplica_igv: bool = True


class ItemOut(ItemCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subtotal: Decimal


class ComprobanteCreate(BaseModel):
    tipo: TipoDocumento
    serie: str = Field(min_length=1, max_length=10)
    numero: str = Field(min_length=1, max_length=20)
    fecha_emision: date
    fecha_vencimiento: date | None = None
    moneda: str = "PEN"
    estado: EstadoComprobante = EstadoComprobante.EMITIDO
    observaciones: str | None = None
    cliente_nombre: str = Field(min_length=1, max_length=200)
    cliente_documento: str | None = None
    cliente_email: str | None = None
    cliente_telefono: str | None = None
    items: list[ItemCreate] = Field(min_length=1)


class ComprobanteUpdate(BaseModel):
    tipo: TipoDocumento | None = None
    serie: str | None = None
    numero: str | None = None
    fecha_emision: date | None = None
    fecha_vencimiento: date | None = None
    moneda: str | None = None
    estado: EstadoComprobante | None = None
    observaciones: str | None = None
    cliente_nombre: str | None = None
    cliente_documento: str | None = None
    items: list[ItemCreate] | None = None


class ComprobanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoDocumento
    serie: str
    numero: str
    fecha_emision: date
    fecha_vencimiento: date | None
    moneda: str
    igv: Decimal
    subtotal: Decimal
    total: Decimal
    estado: EstadoComprobante
    observaciones: str | None
    cliente_nombre: str
    cliente_documento: str | None
    items: list[ItemOut]
    creado_en: datetime


class AgendaCreate(BaseModel):
    tipo: TipoAgenda
    titulo: str = Field(min_length=1, max_length=200)
    descripcion: str | None = None
    fecha_inicio: datetime
    fecha_fin: datetime | None = None
    ubicacion: str | None = None
    participantes: str | None = None
    recordatorio_minutos: int = 30


class AgendaUpdate(BaseModel):
    tipo: TipoAgenda | None = None
    titulo: str | None = None
    descripcion: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    ubicacion: str | None = None
    participantes: str | None = None
    completado: bool | None = None
    recordatorio_minutos: int | None = None


class AgendaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoAgenda
    titulo: str
    descripcion: str | None
    fecha_inicio: datetime
    fecha_fin: datetime | None
    ubicacion: str | None
    participantes: str | None
    completado: bool
    recordatorio_minutos: int
    creado_en: datetime


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: dict[str, str]
    reemplazar_todas: bool = True


class NotificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    mensaje: str
    tipo: str
    leida: bool
    enlace: str | None
    creado_en: datetime


class PreferenciasAvisoIn(BaseModel):
    telegram_chat_id: str | None = None
    notificar_email: bool = True


class PreferenciasAvisoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    telegram_chat_id: str | None
    notificar_email: bool


class ClienteCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    documento: str | None = None
    tipo_documento: str | None = "RUC"
    email: str | None = None
    telefono: str | None = None
    direccion: str | None = None


class ClienteUpdate(BaseModel):
    nombre: str | None = None
    documento: str | None = None
    tipo_documento: str | None = None
    email: str | None = None
    telefono: str | None = None
    direccion: str | None = None
    activo: bool | None = None


class ClienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    documento: str | None = None
    tipo_documento: str | None = None
    email: str | None = None
    telefono: str | None = None
    direccion: str | None = None
    activo: bool = True


class ProductoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=300)
    tipo: str = "producto"
    codigo: str | None = None
    unidad: str = "NIU"
    precio_unitario: Decimal = Field(ge=0)


class ProductoUpdate(BaseModel):
    nombre: str | None = None
    tipo: str | None = None
    codigo: str | None = None
    unidad: str | None = None
    precio_unitario: Decimal | None = None
    activo: bool | None = None


class ProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    tipo: str
    codigo: str | None = None
    unidad: str
    precio_unitario: Decimal
    activo: bool = True


class EmailShareIn(BaseModel):
    email: EmailStr
    mensaje: str | None = None


class WhatsAppShareOut(BaseModel):
    url: str
    mensaje: str


class DashboardOut(BaseModel):
    total_comprobantes: int
    total_facturado: Decimal
    total_cobrado: Decimal
    total_pendiente: Decimal
    total_anulado: Decimal
    por_estado: dict[str, int]
    por_tipo: dict[str, int]
    por_mes: list[dict]
    agendas_proximas: int
    agendas_hoy: int
    documentos_vencidos: int
    recientes: list[ComprobanteOut]
