"""Esquemas de solicitud y respuesta.

Son el contrato con la interfaz: de aquí sale el esquema OpenAPI y de ese
esquema salen los tipos TypeScript. Un tipo escrito a mano en el frontend que
duplique algo de este archivo es una divergencia esperando ocurrir.

Las descripciones de los campos no son adorno: aparecen en la documentación
generada y son lo que lee quien construye la interfaz.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from minsur_domain.estados import Accion, Estado, Perfil


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# --- Identidad ---------------------------------------------------------------


class UsuarioActual(Base):
    """Identidad y alcance del usuario autenticado."""

    id_objeto: str = Field(description="Identificador de objeto en Entra ID")
    nombre: str
    correo: str
    perfil: Perfil = Field(description="Perfil derivado de la pertenencia a grupos")
    acciones_permitidas: list[str] = Field(
        default_factory=list,
        description="Operaciones que el perfil puede ejecutar en la plataforma",
    )


# --- Versionado --------------------------------------------------------------


class Terna(Base):
    """Las tres versiones que definen una corrida."""

    motor: str = Field(description="Versión del motor de cálculo", examples=["1.2.0"])
    datos_maestros: str = Field(description="Comité de Precios utilizado", examples=["CP-2026-03"])
    vigencia_datos_maestros: date
    revision_inputs: int = Field(ge=1)
    huella_inputs: str = Field(min_length=64, max_length=64)


# --- Casos -------------------------------------------------------------------


class ResumenCaso(Base):
    id_caso: str
    nombre: str
    tipo: Literal["sin-proyecto", "monometalico", "polimetalico"]
    estado: Estado
    actualizado_en: datetime
    actualizado_por: str


class NuevoCaso(Base):
    nombre: str = Field(min_length=3, max_length=120)
    tipo: Literal["sin-proyecto", "monometalico", "polimetalico"]
    descripcion: str = Field(default="", max_length=1000)
    duplicar_de: str | None = Field(
        default=None,
        description="Identificador del caso a duplicar. El duplicado nace en borrador",
    )


class DetalleCaso(ResumenCaso):
    descripcion: str
    terna: Terna | None = Field(
        default=None, description="Presente solo si el caso tiene una corrida"
    )
    acciones_disponibles: list[Accion]


# --- Plantillas --------------------------------------------------------------


class SolicitudCarga(Base):
    """Petición de autorización para subir una plantilla."""

    tipo: Literal["produccion", "capex", "opex"]
    nombre_archivo: str = Field(
        min_length=5,
        description="Nombre original. Se usa para validar la extensión, no para la ruta",
    )
    tamanio_bytes: int = Field(gt=0, le=25 * 1024 * 1024)


class AutorizacionCarga(Base):
    """Permiso temporal para escribir un blob concreto.

    El archivo se sube directamente al almacenamiento con esta URL. No
    atraviesa la puerta de enlace ni los servicios de aplicación.
    """

    url: str = Field(description="URL con firma de acceso compartido")
    metodo: Literal["PUT"] = "PUT"
    ruta_blob: str = Field(description="Ruta que debe confirmarse tras la subida")
    expira: datetime
    encabezados: dict[str, str] = Field(
        default_factory=lambda: {"x-ms-blob-type": "BlockBlob"},
        description="Encabezados obligatorios de la solicitud de subida",
    )


class ConfirmacionCarga(Base):
    ruta_blob: str


class ResultadoValidacion(Base):
    """Validación de una plantilla antes de admitirla al cálculo."""

    valida: bool
    filas_leidas: int
    hallazgos: list[str] = Field(
        default_factory=list,
        description="Problemas encontrados, con hoja y celda cuando aplica",
    )
    huella: str = Field(default="", description="SHA-256 del contenido admitido")


# --- Evaluación --------------------------------------------------------------


class Indicadores(Base):
    npv_musd: float = Field(description="Valor actual neto, millones de dólares")
    tir: float = Field(description="Tasa interna de retorno, en tanto por uno")
    payback_anios: float
    capital_intensity: float


class ResultadoEvaluacion(Base):
    id_corrida: str
    id_caso: str
    estado: Estado
    terna: Terna
    indicadores: Indicadores
    ejecutada_en: datetime
    ejecutada_por: str
    duracion_ms: int


class SolicitudCongelamiento(Base):
    motivo: str = Field(
        min_length=10,
        max_length=500,
        description=(
            "Qué decisión sustenta esta evaluación. Es lo que explica, años "
            "después, por qué se congeló"
        ),
    )
    rutas_respaldo: list[str] = Field(
        default_factory=list,
        description="Documentos y correos de aprobación asociados",
    )


class CorridaCongelada(Base):
    id_corrida: str
    huella_contenido: str
    huella_sello: str
    congelada_por: str
    congelada_en: datetime
    ruta_imagen: str = Field(description="Ubicación de la imagen sellada")


# --- Fidelidad ---------------------------------------------------------------


class DesviacionLinea(Base):
    linea: str
    anio: int | None = None
    valor_plataforma: float
    valor_referencia: float
    diferencia_relativa: float
    dentro_de_tolerancia: bool


class ResultadoFidelidad(Base):
    """Contraste contra el modelo de referencia en los cuatro niveles."""

    id_caso: str
    version_motor: str
    dentro_de_tolerancia: bool
    nivel_n0: bool = Field(description="Paridad de inputs, sin tolerancia")
    nivel_n1: bool = Field(description="Bloques intermedios, año a año")
    nivel_n2: bool = Field(description="Flujos, año a año")
    nivel_n3: bool = Field(description="Indicadores finales")
    desviaciones: list[DesviacionLinea] = Field(default_factory=list)


# --- Tablero e historial -----------------------------------------------------


class Tablero(Base):
    id_caso: str
    indicadores: Indicadores
    cascada: list[dict[str, Any]] = Field(default_factory=list)
    curva_produccion: list[dict[str, Any]] = Field(default_factory=list)
    curva_costo_unitario: list[dict[str, Any]] = Field(default_factory=list)
    capex_por_etapa: list[dict[str, Any]] = Field(default_factory=list)


class EstadosFinancieros(Base):
    """Estados estimados, auditables línea por línea."""

    id_caso: str
    anios: list[int]
    lineas: dict[str, list[float]] = Field(
        description="Cada línea del estado, con un valor por año del horizonte"
    )


class EntradaHistorial(Base):
    id_corrida: str
    id_caso: str
    nombre_caso: str
    estado: Estado
    usuario: str
    marca_tiempo: datetime
    version_motor: str
    npv_musd: float | None = None


class PaginaHistorial(Base):
    corridas: list[EntradaHistorial]
    total: int
    continuacion: str | None = None


# --- Exportación -------------------------------------------------------------


class ResultadoExportacion(Base):
    formato: Literal["xlsx", "pdf"]
    url_descarga: str = Field(description="URL temporal de lectura")
    url_sharepoint: str | None = Field(
        default=None,
        description="Presente si el sitio de SharePoint está habilitado (R-44)",
    )
    expira: datetime


# --- Operación ---------------------------------------------------------------


class Salud(Base):
    estado: Literal["ok", "degradado"]
    entorno: str
    version_api: str
    version_motor: str | None = None


class Problema(Base):
    """Cuerpo de error. Explica qué pasó y cómo resolverlo."""

    detalle: str
    restriccion: str | None = Field(
        default=None,
        description="Restricción del cuadro de control que bloquea, si aplica",
    )
