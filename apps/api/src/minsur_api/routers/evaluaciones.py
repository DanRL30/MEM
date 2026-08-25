"""Ejecución, congelamiento y contraste de evaluaciones.

Los endpoints están definidos con su contrato completo para que el esquema
OpenAPI sea utilizable desde ya: de él salen los tipos del frontend y la
definición que se importa a API Management.

La implementación del cálculo espera el modelo económico de referencia
(`R-02`). Hasta que llegue, cada operación de cálculo responde 501 con la
restricción que la bloquea, en lugar de devolver un resultado inventado que
alguien podría tomar por bueno.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status

from minsur_domain.estados import Perfil

from ..esquemas import (
    CorridaCongelada,
    Problema,
    ResultadoEvaluacion,
    ResultadoFidelidad,
    SolicitudCongelamiento,
)
from ..seguridad import Usuario, requiere, usuario_actual

router = APIRouter(prefix="/casos/{id_caso}", tags=["Evaluación"])

ID_CASO = Path(description="Identificador del caso", examples=["CASO-SR-2026-014"])


def _pendiente_del_modelo(operacion: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "detalle": (
                f"{operacion} requiere el motor de cálculo, cuya construcción "
                "no ha iniciado por estar pendiente la entrega del modelo "
                "económico de referencia."
            ),
            "restriccion": "R-02",
        },
    )


@router.post(
    "/evaluar",
    response_model=ResultadoEvaluacion,
    summary="Ejecutar la evaluación económica",
    responses={501: {"model": Problema}},
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
) -> ResultadoEvaluacion:
    """Calcula la evaluación y deja la corrida en estado *calculada*.

    Registra la terna de versiones con la que se calculó. Una corrida no
    guarda una referencia a la versión vigente del motor: guarda la versión
    exacta, para que publicar una versión nueva no altere corridas previas.
    """
    raise _pendiente_del_modelo("Ejecutar una evaluación")


@router.post(
    "/congelar",
    response_model=CorridaCongelada,
    summary="Congelar la evaluación como sustento de decisión",
    responses={403: {"model": Problema}, 409: {"model": Problema}},
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
    raise _pendiente_del_modelo("Congelar una evaluación")


@router.post(
    "/recalcular",
    response_model=ResultadoEvaluacion,
    summary="Recalcular una corrida congelada con el motor vigente",
    responses={409: {"model": Problema}},
)
async def recalcular(
    id_caso: str = ID_CASO,
    usuario: Usuario = Depends(usuario_actual),
) -> ResultadoEvaluacion:
    """Crea una corrida nueva a partir de una congelada. **No la modifica.**

    Es la forma de observar el efecto de un cambio del modelo sin que la
    evidencia que sustentó una decisión deje de existir. La corrida nueva
    apunta a la anterior como origen.
    """
    raise _pendiente_del_modelo("Recalcular una corrida")


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
    raise _pendiente_del_modelo("Contrastar contra el modelo de referencia")
