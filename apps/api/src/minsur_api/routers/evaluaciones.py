"""Ejecución, congelamiento y contraste de evaluaciones.

Los endpoints están definidos con su contrato completo para que el esquema
OpenAPI sea utilizable desde ya: de él salen los tipos del frontend y la
definición que se importa a API Management.

El cálculo ya está implementado: el modelo de referencia llegó el 31/08/2026 y
el motor lo reproduce. Siguen respondiendo 501 las dos operaciones cuyo insumo
falta de verdad —el contenedor con política de inmutabilidad para congelar, y
los casos certificados para contrastar—, con la restricción que las bloquea en
el cuerpo, en lugar de un resultado inventado que alguien podría tomar por
bueno.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status

from minsur_domain.estados import Perfil
from minsur_engine.caso import DatosMaestros

from ..dependencias import datos_maestros, repositorio
from ..esquemas import (
    CorridaCongelada,
    Problema,
    ResultadoEvaluacion,
    ResultadoFidelidad,
    SolicitudCongelamiento,
)
from ..evaluacion import ejecutar, resultado_de
from ..repositorio import CasoNoEncontrado, CasoSinInsumos, RepositorioDeCasos
from ..seguridad import Usuario, requiere, usuario_actual

router = APIRouter(prefix="/casos/{id_caso}", tags=["Evaluación"])

ID_CASO = Path(description="Identificador del caso", examples=["CASO-SR-2026-014"])


SIN_DATOS_MAESTROS = HTTPException(
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    detail={
        "detalle": (
            "No hay datos maestros cargados. Los parametros corporativos, las tasas de "
            "depreciacion y las escalas de regalia e IEM los confirma y mantiene MINSUR."
        ),
        "restriccion": "R-32",
    },
)


def _caso_no_encontrado() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"detalle": "No existe un caso con ese identificador.", "restriccion": None},
    )


@router.post(
    "/evaluar",
    response_model=ResultadoEvaluacion,
    summary="Ejecutar la evaluación económica",
    responses={404: {"model": Problema}, 409: {"model": Problema}, 501: {"model": Problema}},
)
async def evaluar(
    id_caso: str = ID_CASO,
    usuario: Usuario = Depends(
        requiere(
            Perfil.ADMINISTRADOR,
            Perfil.LIDER_DE_ESTUDIO,
            Perfil.INGENIERO_DE_PROYECTO,
        )
    ),
    repo: RepositorioDeCasos = Depends(repositorio),
    maestros: DatosMaestros | None = Depends(datos_maestros),
) -> ResultadoEvaluacion:
    """Calcula la evaluación y deja la corrida en estado *calculada*.

    Registra la terna de versiones con la que se calculó. Una corrida no
    guarda una referencia a la versión vigente del motor: guarda la versión
    exacta, para que publicar una versión nueva no altere corridas previas.
    """
    try:
        caso = repo.obtener(id_caso)
    except CasoNoEncontrado:
        raise _caso_no_encontrado() from None

    if maestros is None:
        raise SIN_DATOS_MAESTROS

    try:
        corrida = ejecutar(caso, maestros, usuario=usuario.correo)
    except CasoSinInsumos:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detalle": (
                    "El caso no tiene insumos cargados. Sube la plantilla antes de calcular."
                ),
                "restriccion": None,
            },
        ) from None

    return resultado_de(repo.registrar_corrida(corrida))


@router.post(
    "/congelar",
    response_model=CorridaCongelada,
    summary="Congelar la evaluación como sustento de decisión",
    responses={403: {"model": Problema}, 409: {"model": Problema}, 501: {"model": Problema}},
)
async def congelar(
    solicitud: SolicitudCongelamiento,
    id_caso: str = ID_CASO,
    usuario: Usuario = Depends(requiere(Perfil.ADMINISTRADOR, Perfil.LIDER_DE_ESTUDIO)),
) -> CorridaCongelada:
    """Transición irreversible.

    Genera una imagen sellada autocontenida —inputs, parámetros efectivamente
    utilizados, versión del motor, resultados y documentación de respaldo—,
    la resume con SHA-256 y la deposita en el contenedor con política de
    inmutabilidad.

    Desde ese momento la evaluación no puede alterarse. Para ver el efecto de
    un cambio posterior del modelo, se recalcula: eso genera una corrida
    nueva y deja esta intacta como sustento.

    Congelar corresponde a quien sustenta la decisión, no a quien opera la
    plataforma. Por eso el Ingeniero de Proyecto no aparece entre los
    perfiles autorizados.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "detalle": (
                "Congelar exige depositar la imagen sellada en un contenedor con politica "
                "de inmutabilidad. Ese contenedor se aprovisiona con la plantilla Bicep en "
                "el tenant de MINSUR, que aun no esta habilitado. El sellado en si ya esta "
                "implementado: lo que falta es donde depositarlo de forma irreversible."
            ),
            "restriccion": "R-23",
        },
    )


@router.post(
    "/recalcular",
    response_model=ResultadoEvaluacion,
    summary="Recalcular una corrida congelada con el motor vigente",
    responses={404: {"model": Problema}, 409: {"model": Problema}},
)
async def recalcular(
    id_caso: str = ID_CASO,
    usuario: Usuario = Depends(usuario_actual),
    repo: RepositorioDeCasos = Depends(repositorio),
    maestros: DatosMaestros | None = Depends(datos_maestros),
) -> ResultadoEvaluacion:
    """Crea una corrida nueva a partir de una congelada. **No la modifica.**

    Es la forma de observar el efecto de un cambio del modelo sin que la
    evidencia que sustentó una decisión deje de existir. La corrida nueva
    apunta a la anterior como origen.
    """
    try:
        caso = repo.obtener(id_caso)
    except CasoNoEncontrado:
        raise _caso_no_encontrado() from None

    anterior = repo.ultima_corrida(id_caso)
    if anterior is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detalle": "El caso no tiene ninguna corrida que recalcular.",
                "restriccion": None,
            },
        )

    if maestros is None:
        raise SIN_DATOS_MAESTROS

    # La corrida nueva apunta a la anterior y se anade al historial: registrar
    # nunca sobrescribe, que es la regla del alcance sobre el recalculo.
    nueva = ejecutar(caso, maestros, usuario=usuario.correo, origen=anterior.id_corrida)
    return resultado_de(repo.registrar_corrida(nueva))


@router.get(
    "/verificar-fidelidad",
    response_model=ResultadoFidelidad,
    summary="Contrastar contra el modelo de referencia",
    responses={501: {"model": Problema}},
)
async def verificar_fidelidad(
    id_caso: str = ID_CASO,
    usuario: Usuario = Depends(usuario_actual),
) -> ResultadoFidelidad:
    """Contraste en los cuatro niveles.

    | Nivel | Objeto | Criterio |
    |---|---|---|
    | N0 | Paridad de inputs | Coincidencia exacta |
    | N1 | Bloques intermedios, año a año | 0,1 % o US$ 10 000 por línea |
    | N2 | Flujos, año a año | 0,1 % o US$ 10 000 por año |
    | N3 | Indicadores finales | NPV 0,1 % · TIR 5 pb · Payback 0,1 año |

    Verificar solo el indicador final es metodológicamente insuficiente: dos
    errores compensatorios en bloques intermedios producen un NPV correcto
    sobre un modelo inválido.

    Los umbrales son la propuesta de INVA; el valor contractual lo fija
    Finanzas (`R-31`). Este endpoint es el que consulta la segunda de las
    cinco comprobaciones obligatorias de la ventana de pase.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "detalle": (
                "El contraste contra el modelo de referencia exige los tres casos "
                "certificados con sus inputs y resultados oficiales, que solo existen "
                "dentro del tenant de MINSUR. El arnes N0-N3 ya corre sobre casos "
                "sinteticos en cada integracion."
            ),
            "restriccion": "R-30",
        },
    )
