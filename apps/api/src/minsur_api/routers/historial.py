"""Historial de evaluaciones y bitacora de auditoria."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from minsur_domain.estados import Perfil

from ..dependencias import repositorio
from ..esquemas import PaginaHistorial, Problema
from ..evaluacion import entrada_de_historial
from ..repositorio import RepositorioDeCasos
from ..seguridad import Usuario, requiere, usuario_actual

router = APIRouter(tags=["Historial"])

BITACORA_PENDIENTE = HTTPException(
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    detail={
        "detalle": (
            "La bitacora encadenada se guarda en el almacen de solo escritura que la "
            "plantilla Bicep aprovisiona en el tenant de MINSUR. El modelo de la bitacora "
            "ya esta implementado; lo que falta es donde escribirla sin poder alterarla."
        ),
        "restriccion": "R-23",
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
    repo: RepositorioDeCasos = Depends(repositorio),
) -> PaginaHistorial:
    """Corridas ordenadas de la mas reciente a la mas antigua.

    Cada entrada incluye la version del motor con la que se calculo, no la
    vigente: es lo que permite entender por que dos corridas del mismo caso
    dan distinto.

    Es la quinta de las cinco comprobaciones obligatorias del pase.
    """
    desde = int(continuacion) if continuacion and continuacion.isdigit() else 0
    corridas, total = repo.historial(limite=limite, desde=desde)
    if caso:
        corridas = [c for c in corridas if c.id_caso == caso]

    nombres = {c.id_caso: c.nombre for c in repo.listar()}
    siguiente = desde + limite
    return PaginaHistorial(
        corridas=[entrada_de_historial(c, nombres.get(c.id_caso, c.id_caso)) for c in corridas],
        total=total,
        continuacion=str(siguiente) if siguiente < total else None,
    )


@router.get(
    "/auditoria",
    summary="Bitacora de auditoria",
    responses={403: {"model": Problema}, 501: {"model": Problema}},
)
async def auditoria(
    caso: str | None = Query(default=None),
    corrida: str | None = Query(default=None),
    usuario: Usuario = Depends(requiere(Perfil.ADMINISTRADOR, Perfil.AUDITOR)),
) -> dict[str, Any]:
    """Bitacora de solo escritura, restringida al perfil Auditor.

    Cada registro contiene el identificador de la corrida, el usuario
    responsable, la marca de tiempo, la accion y, ante modificacion de
    insumos o parametros, los valores anterior y posterior.

    Las entradas van encadenadas: cada una incluye el resumen de la anterior,
    de modo que suprimir una intermedia rompe la cadena y se detecta.
    """
    raise BITACORA_PENDIENTE
