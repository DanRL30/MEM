"""Carga de plantillas en desarrollo local. **Este router no se monta fuera de local.**

La ruta oficial de carga es `plantillas.py`: el navegador pide una autorización
temporal y sube el archivo directamente al almacenamiento, sin que atraviese la
API. Esa ruta depende del contenedor del tenant (`R-23`) y de la plantilla
definitiva de MINSUR (`R-07`), y sigue respondiendo 501 tal como está.

Este router no la sustituye ni la adelanta: recibe el archivo por la API,
lo lee con la misma ingesta y deja el caso listo para calcular, para que la
interfaz pueda construirse contra la cadena real en vez de contra datos de
ejemplo. `main.py` solo lo monta cuando `ENTORNO=local`, de modo que en dev, QA
y producción esta superficie no existe.

Tres cosas que conviene entender antes de tocarlo:

**Escribe un temporal a propósito.** Las siete lectoras de `minsur_ingest`
reciben una ruta, no bytes, y esa firma es correcta: la ruta oficial trabaja
sobre un blob descargado. Adaptar el paquete para aceptar bytes solo por esta
ruta de desarrollo sería mover el compromiso al sitio equivocado.

**El nombre del archivo del cliente se descarta.** El temporal se llama siempre
igual. Un nombre que llega de fuera y se concatena a una ruta es una travesía de
directorios esperando ocurrir.

**Son cinco libros, no uno.** El del caso trae la hoja `Caso`, la produccion de
cada unidad y los precios; opex y capex tienen plantilla propia desde que se
cerraron sus formatos, y el comite de precios y los supuestos van aparte porque
tienen dueños distintos. Solo el primero es obligatorio: sin los demas el caso
se lee y se calcula igual, con los bloques que falten en cero.

**Las incidencias se devuelven todas.** La ingesta acumula y no se detiene en la
primera, porque una plantilla llenada a mano llega con varias a la vez.

**Un archivo que no es un libro tambien es una incidencia.** Las lectoras de la
ingesta comprueban que la ruta exista, no que su contenido sea un `xlsx`, porque
en la ruta oficial el archivo llega de un blob que la plataforma escribio. Aqui
lo elige el usuario, asi que puede ser cualquier cosa, y una carga equivocada
tiene que salir por el mismo sitio que un dato mal tecleado.
"""

from __future__ import annotations

import pathlib
import tempfile
import zipfile
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status
from openpyxl.utils.exceptions import InvalidFileException

from minsur_domain.estados import Perfil
from minsur_engine.caso import Caso as CasoDelMotor, campos_con_dato
from minsur_ingest.capex import (
    CapexDeUnidad,
    ErrorDeAsociacion as ErrorDeAsociacionDeCapex,
    aplicar as aplicar_capex,
)
from minsur_ingest.incidencias import Incidencia
from minsur_ingest.opex import (
    ErrorDeAsociacion as ErrorDeAsociacionDeOpex,
    OpexDeUnidad,
    aplicar as aplicar_opex,
)
from minsur_ingest.plantilla import (
    BloqueDeCapex,
    BloqueDeOpex,
    leer_capex,
    leer_comite_de_precios,
    leer_opex,
    leer_plantilla,
    leer_supuestos,
)
from minsur_ingest.supuestos import aplicar as aplicar_supuestos

from ..dependencias import repositorio
from ..esquemas import IncidenciaDePlantilla, Problema, ResultadoValidacion
from ..evaluacion import huella_de_insumos
from ..repositorio import CasoNoEncontrado, RepositorioDeCasos
from ..seguridad import Usuario, requiere

router = APIRouter(prefix="/desarrollo/casos/{id_caso}", tags=["Desarrollo"])

ID_CASO = Path(examples=["CASO-SR-2026-014"])

TOPE_DE_ARCHIVO = 25 * 1024 * 1024
"""El mismo tope que declara la autorización de carga directa."""

NOMBRE_TEMPORAL = "plantilla.xlsx"

PUEDE_CARGAR = requiere(
    Perfil.ADMINISTRADOR,
    Perfil.FINANZAS,
    Perfil.LIDER_DE_ESTUDIO,
    Perfil.INGENIERO_DE_PROYECTO,
)


def _a_esquema(incidencias: tuple[Incidencia, ...]) -> list[IncidenciaDePlantilla]:
    return [
        IncidenciaDePlantilla(hoja=i.hoja, celda=i.celda, mensaje=i.mensaje) for i in incidencias
    ]


# La pestana n corresponde a la unidad n. El nombre de la hoja viaja como pista
# y nunca como identidad, asi que lo que ordena es `orden` y no la posicion en
# la que la lectura las haya devuelto.
def _opex_en_orden(bloques: Sequence[BloqueDeOpex]) -> list[OpexDeUnidad]:
    return [b.opex for b in sorted(bloques, key=lambda b: b.orden)]


def _capex_en_orden(bloques: Sequence[BloqueDeCapex]) -> list[CapexDeUnidad]:
    return [b.capex for b in sorted(bloques, key=lambda b: b.orden)]


def _no_es_un_libro(nombre: str) -> Incidencia:
    return Incidencia(
        "(archivo)",
        nombre,
        "no es un libro de Excel legible. Sube el .xlsx que emite la plantilla.",
    )


async def _volcar(archivo: UploadFile, carpeta: pathlib.Path) -> pathlib.Path:
    """Escribe el archivo recibido en la carpeta temporal y devuelve su ruta."""
    contenido = await archivo.read()
    if len(contenido) > TOPE_DE_ARCHIVO:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "detalle": f"El archivo supera el tope de {TOPE_DE_ARCHIVO // (1024 * 1024)} MB.",
                "restriccion": None,
            },
        )
    ruta = carpeta / NOMBRE_TEMPORAL
    ruta.write_bytes(contenido)
    return ruta


@router.post(
    "/insumos",
    response_model=ResultadoValidacion,
    summary="Cargar y validar las plantillas de un caso, en desarrollo local",
    responses={404: {"model": Problema}, 413: {"model": Problema}},
)
async def cargar_insumos(
    id_caso: str = ID_CASO,
    caso: UploadFile = File(
        description="Libro del caso: hoja Caso, produccion por unidad, precios"
    ),
    opex: UploadFile | None = File(default=None, description="Cash cost y gastos, por unidad"),
    capex: UploadFile | None = File(default=None, description="Capital por unidad"),
    supuestos: UploadFile | None = File(default=None, description="Supuestos del caso"),
    comite: UploadFile | None = File(default=None, description="Comité de precios aprobado"),
    usuario: Usuario = Depends(PUEDE_CARGAR),
    repo: RepositorioDeCasos = Depends(repositorio),
) -> ResultadoValidacion:
    """Lee las plantillas, aplica los supuestos y deja el caso calculable.

    El comité de precios y los supuestos del caso van en libros distintos y con
    dueños distintos: el comité lo aprueba y lo sube Finanzas, y sin nombre de
    quien lo aprobó se rechaza, porque una corrida registra qué comité usó y no
    el vigente. Mezclarlos dejaría a cualquiera cambiando un precio aprobado sin
    que nadie lo advirtiera.

    No calcula. Cargar y calcular son dos pasos, y el segundo es el endpoint de
    evaluación de siempre, con su terna y su registro en el historial.
    """
    try:
        almacenado = repo.obtener(id_caso)
    except CasoNoEncontrado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detalle": "No existe un caso con ese identificador.", "restriccion": None},
        ) from None

    incidencias: tuple[Incidencia, ...] = ()
    with tempfile.TemporaryDirectory() as temporal:
        carpeta = pathlib.Path(temporal)

        del_caso = None
        try:
            lectura = leer_plantilla(await _volcar(caso, carpeta))
        except (zipfile.BadZipFile, InvalidFileException, OSError):
            incidencias += (_no_es_un_libro("caso"),)
        else:
            incidencias += lectura.incidencias
            del_caso = lectura.caso

        bloques_de_opex: tuple[BloqueDeOpex, ...] = ()
        if opex is not None:
            try:
                leido_opex = leer_opex(await _volcar(opex, carpeta))
            except (zipfile.BadZipFile, InvalidFileException, OSError):
                incidencias += (_no_es_un_libro("opex"),)
            else:
                incidencias += leido_opex.incidencias
                bloques_de_opex = leido_opex.bloques

        bloques_de_capex: tuple[BloqueDeCapex, ...] = ()
        if capex is not None:
            try:
                leido_capex = leer_capex(await _volcar(capex, carpeta))
            except (zipfile.BadZipFile, InvalidFileException, OSError):
                incidencias += (_no_es_un_libro("capex"),)
            else:
                incidencias += leido_capex.incidencias
                bloques_de_capex = leido_capex.bloques

        supuestos_leidos = None
        if supuestos is not None:
            try:
                leido = leer_supuestos(await _volcar(supuestos, carpeta))
            except (zipfile.BadZipFile, InvalidFileException, OSError):
                incidencias += (_no_es_un_libro("supuestos"),)
            else:
                incidencias += leido.incidencias
                supuestos_leidos = leido.supuestos

        comite_leido = None
        if comite is not None:
            try:
                leido_comite = leer_comite_de_precios(await _volcar(comite, carpeta))
            except (zipfile.BadZipFile, InvalidFileException, OSError):
                incidencias += (_no_es_un_libro("comite"),)
            else:
                incidencias += leido_comite.incidencias
                comite_leido = leido_comite.comite

    if del_caso is None:
        return ResultadoValidacion(
            valida=False,
            filas_leidas=0,
            incidencias=_a_esquema(incidencias),
            hallazgos=[str(i) for i in incidencias],
        )

    # El orden importa: opex y capex se pegan a las unidades que el libro del
    # caso ya declaro, y los supuestos entran al final porque son los que fijan
    # las condiciones comerciales con las que se vende lo que esas unidades
    # producen.
    #
    # Las pestanas se asocian por orden, no por nombre, asi que un libro con
    # una pestana de mas o de menos no se puede pegar al caso. Eso es un error
    # del usuario y sale como incidencia, no como fallo del servidor.
    completo: CasoDelMotor = del_caso
    try:
        if bloques_de_opex:
            completo = aplicar_opex(completo, _opex_en_orden(bloques_de_opex))
        if bloques_de_capex:
            completo = aplicar_capex(completo, _capex_en_orden(bloques_de_capex))
    except (ErrorDeAsociacionDeOpex, ErrorDeAsociacionDeCapex) as error:
        incidencias += (Incidencia("(libro)", "-", str(error)),)
        return ResultadoValidacion(
            valida=False,
            filas_leidas=0,
            incidencias=_a_esquema(incidencias),
            hallazgos=[str(i) for i in incidencias],
        )

    if supuestos_leidos is not None:
        completo = aplicar_supuestos(completo, supuestos_leidos, comite_leido)

    # La revisión sube con cada carga admitida: es el tercer eje de la terna, y
    # una corrida guarda la revisión exacta con la que se calculó.
    repo.guardar(
        replace(
            almacenado,
            insumos=completo,
            revision_inputs=almacenado.revision_inputs + 1,
            actualizado_en=datetime.now(UTC),
            actualizado_por=usuario.correo,
        )
    )

    return ResultadoValidacion(
        valida=not incidencias,
        filas_leidas=sum(len(campos_con_dato(u.produccion)) for u in completo.unidades),
        incidencias=_a_esquema(incidencias),
        hallazgos=[str(i) for i in incidencias],
        huella=huella_de_insumos(completo),
    )
