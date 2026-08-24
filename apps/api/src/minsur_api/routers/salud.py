"""Verificación de disponibilidad.

`/api/salud` es lo que consulta la verificación de humo del despliegue antes
de dar por terminado un pase. No exige autenticación a propósito: si la
exigiera, un fallo de identidad se reportaría como servicio caído y llevaría
a revertir por la causa equivocada dentro de la ventana de mantenimiento.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..config import config
from ..esquemas import Salud
from ..version import VERSION_API, version_motor

router = APIRouter(tags=["Operación"])


@router.get("/salud", response_model=Salud, summary="Estado del servicio")
async def salud() -> Salud:
    return Salud(
        estado="ok",
        entorno=config().entorno,
        version_api=VERSION_API,
        version_motor=version_motor(),
    )
