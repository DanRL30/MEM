"""Historial de evaluaciones y bitacora de auditoria."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from minsur_domain.estados import Perfil

from ..esquemas import PaginaHistorial, Problema
from ..seguridad import Usuario, requiere, usuario_actual

router = APIRouter(tags=["Historial"])

PENDIENTE = HTTPException(
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    detail={
        "detalle": (
            "El historial requiere la persistencia de corridas, cuyo esquema "
            "depende de las plantillas definitivas de MINSUR."
        ),
        "restriccion": "R-07",
    },
)


@router.get(
    "/historial",
    response_model=PaginaHistorial,
    summary="Historial de evaluaciones",
    responses={501: {"model": Problema}},
)
async def historial(
    limite: int = Query(default=25, ge=1, le=200),
    caso: str | None = Query(default=None),
    continuacion: str | None = Query(default=None),
    usuario: Usuario = Depends(usuario_actual),
) -> PaginaHistorial:
    """Corridas ordenadas de la mas reciente a la mas antigua.

    Cada entrada incluye la version del motor con la que se calculo, no la
    vigente: es lo que permite entender por que dos corridas del mismo caso
    dan distinto.

    Es la quinta de las cinco comprobaciones obligatorias del pase.
    """
    raise PENDIENTE


@router.get(
    "/auditoria",
    summary="Bitacora de auditoria",
    responses={403: {"model": Problema}, 501: {"model": Problema}},
)
async def auditoria(
    caso: str | None = Query(default=None),
    corrida: str | None = Query(default=None),
    usuario: Usuario = Depends(
        requiere(Perfil.ADMINISTRADOR, Perfil.AUDITOR)
    ),
) -> dict:
    """Bitacora de solo escritura, restringida al perfil Auditor.

    Cada registro contiene el identificador de la corrida, el usuario
    responsable, la marca de tiempo, la accion y, ante modificacion de
    insumos o parametros, los valores anterior y posterior.

    Las entradas van encadenadas: cada una incluye el resumen de la anterior,
    de modo que suprimir una intermedia rompe la cadena y se detecta.
    """
    raise PENDIENTE
