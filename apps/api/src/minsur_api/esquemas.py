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

TipoDeCaso = Literal["sin-proyecto", "con-proyecto"]
"""El eje del modelo: un proyecto se evalua contra la operacion sin el.

No es una clasificacion por metal. Monometalico y polimetalico describen la
forma del concentrado, que ya se deduce de las unidades que el caso declara y
no es algo que el usuario elija al abrirlo. Lo que si elige es de que lado de
la comparacion esta el escenario, porque de esa pareja sale el indicador
incremental que sustenta la decision de inversion.

El proyecto y la fase FEL no viajan aqui: el escenario se abre desde dentro de
un FEL de un proyecto, de modo que los dos son contexto de navegacion y
volverlos a preguntar abriria la puerta a que contradigan donde esta el
usuario. Modelarlos como entidades propias esta pendiente.
"""


class ResumenCaso(Base):
    id_caso: str
    abreviatura: str = Field(
        default="",
        description="Nombre corto del escenario, para tablas y comparaciones",
    )
    nombre: str
    tipo: TipoDeCaso
    estado: Estado
    actualizado_en: datetime
    actualizado_por: str


class NuevoCaso(Base):
    abreviatura: str = Field(
        min_length=2,
        max_length=16,
        description=(
            "Nombre corto con el que el escenario aparece en tablas, leyendas y "
            "comparaciones, donde el nombre completo no cabe"
        ),
        examples=["SD Fase III"],
    )
    nombre: str = Field(min_length=3, max_length=120)
    tipo: TipoDeCaso
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


class IncidenciaDePlantilla(Base):
    """Un problema de lectura, con su ubicación exacta en el libro.

    La ingesta acumula incidencias y no se detiene en la primera, porque una
    plantilla llenada a mano llega con varias a la vez. Los tres campos van
    separados para que la interfaz pueda llevar al usuario a la celda: una
    cadena ya compuesta obliga a que la pantalla la desarme para eso.
    """

    hoja: str = Field(description="Pestaña del libro, o `(archivo)` y `(libro)`")
    celda: str = Field(description="Referencia de celda, o `-` si el problema es del libro")
    mensaje: str


class ResultadoValidacion(Base):
    """Validación de una plantilla antes de admitirla al cálculo."""

    valida: bool
    filas_leidas: int
    incidencias: list[IncidenciaDePlantilla] = Field(
        default_factory=list,
        description="Problemas encontrados, con su hoja y su celda",
    )
    hallazgos: list[str] = Field(
        default_factory=list,
        description="Las mismas incidencias ya compuestas como texto, para registro",
    )
    huella: str = Field(default="", description="SHA-256 del contenido admitido")


# --- Evaluación --------------------------------------------------------------


class Indicadores(Base):
    """Los cuatro indicadores del contraste N3.

    `tir` y `capital_intensity` son opcionales porque el caso puede no
    definirlas, y eso es un resultado correcto, no un fallo. Un caso que abre
    en positivo —una operación en marcha— no tiene una tasa que describa su
    rentabilidad, y el libro escribe un guion en esa celda. Devolver cero en su
    lugar haría indistinguible «no hay TIR» de «TIR igual a cero», que es
    justamente la distinción que fija el ADR 0011.
    """

    npv_musd: float = Field(description="Valor actual neto, millones de dólares")
    tir: float | None = Field(
        default=None,
        description="Tasa interna de retorno en tanto por uno, o nula si el caso no la define",
    )
    payback_anios: float
    capital_intensity: float | None = Field(
        default=None,
        description="Dólares de capital por tonelada de capacidad, o nula si no hay capacidad",
    )


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


# --- Bloques intermedios -----------------------------------------------------


class SerieAnual(Base):
    """Una línea del libro, con un valor por año del horizonte.

    La etiqueta y la medida son las del libro corporativo, no una traducción de
    la interfaz: salen del mismo catálogo con el que se emite la plantilla y con
    el que se lee. El usuario ve en pantalla la fila que llenó, con su nombre.

    `concepto` es el campo del motor que la alimenta y no se muestra. Está para
    que una discrepancia se pueda seguir de la celda al módulo que la produce.
    """

    etiqueta: str = Field(description="Nombre de la fila en el libro corporativo")
    medida: str = Field(
        default="",
        description="Unidad de medida tal como la declara el libro: t, %, oz/t, $k",
    )
    concepto: str = Field(default="", description="Campo del motor que alimenta la línea")
    codigo: str = Field(
        default="",
        description=(
            "Código contable de la fila, en la columna de la izquierda. Hoy solo lo "
            "lleva el capital: son las tres letras con las que el libro agrupa"
        ),
    )
    valores: list[float]
    origen: Literal["dato", "calculada"] = Field(
        default="calculada",
        description="Si la línea la carga el usuario o la produce el motor",
    )
    recalculada: list[float] | None = Field(
        default=None,
        description=(
            "Lo que el sistema esperaba para una línea que el usuario carga y el motor "
            "sabe rehacer. Va debajo de la cargada; sin ella la alerta no dice qué esperaba"
        ),
    )
    acumulado: float | None = Field(
        default=None,
        description=(
            "El total del horizonte, en la columna de la derecha. Lo resuelve la API "
            "porque no siempre es una suma: una ley es el promedio ponderado por el "
            "tonelaje de su fila, y un ratio no tiene total"
        ),
    )
    total: bool = Field(
        default=False,
        description=(
            "Si la fila cierra un bloque o es una linea de calculo. El libro las "
            "sombrea, y quien lee la hoja las busca por ese sombreado"
        ),
    )
    nota: str | None = Field(
        default=None,
        description="Aviso al pie de la fila, cuando la plataforma se aparta del libro",
    )


class SeccionDelBloque(Base):
    """Un sub-bloque dentro de un grupo: `Mina`, `Planta`, `Concentrado de Cu`.

    Sin título cuando el grupo no se subdivide, que es el caso del complejo y de
    la venta spot.
    """

    titulo: str | None = None
    series: list[SerieAnual]


class GrupoDelBloque(Base):
    """Una banda del libro: una unidad productiva, o un bloque propio del caso."""

    titulo: str = Field(
        default="",
        description=(
            "Nombre de la unidad, o del bloque: Pisco, Venta Sn Spot. Vacío cuando "
            "las líneas son del caso entero y el libro no les pone banda"
        ),
    )
    secciones: list[SeccionDelBloque]


class BloqueDeCorrida(Base):
    """Un bloque del cálculo, correspondiente a una hoja del libro."""

    clave: str
    etiqueta: str = Field(
        description="Rótulo corto de la pestaña. Es el nombre de la hoja del libro"
    )
    titulo: str
    hoja: str = Field(description="Hoja del libro corporativo que reproduce este bloque")
    grupos: list[GrupoDelBloque]


class DiscrepanciaDeCorroboracion(Base):
    """Una celda donde el dato cargado y el recálculo del sistema no coinciden.

    No detiene el cálculo ni sustituye el dato: el que manda es el del usuario.
    Es control de calidad, y viaja con la corrida para poder sustentar después
    por qué se aceptó una diferencia.
    """

    unidad: str
    concepto: str
    ano: int
    cargado: float
    recalculado: float
    diferencia: float
    diferencia_relativa: float


class BloquesDeCorrida(Base):
    """La cadena de cálculo entera, en el orden en que la presenta el libro."""

    id_caso: str
    id_corrida: str
    anios: list[int]
    unidades: list[str]
    bloques: list[BloqueDeCorrida]
    campos_con_dato: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Campos con algún valor distinto de cero, por unidad. Lo decide el motor "
            "para que la API y la interfaz oculten las mismas filas del mismo caso"
        ),
    )
    discrepancias: list[DiscrepanciaDeCorroboracion] = Field(default_factory=list)


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
