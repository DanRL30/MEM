"""Gestión de casos: creación, duplicado, versionado y comparación."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from minsur_domain.estados import Perfil

from ..esquemas import DetalleCaso, NuevoCaso, Problema, ResumenCaso
from ..seguridad import Usuario, requiere, usuario_actual

router = APIRouter(prefix="/casos", tags=["Casos"])

PENDIENTE = HTTPException(
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    detail={
        "detalle": (
            "La persistencia de casos requiere el esquema de datos, cuya "
            "definicion depende de las plantillas definitivas de MINSUR."
        ),
        "restriccion": "R-07",
    },
)


@router.get("", response_model=list[ResumenCaso], summary="Listar casos")
async def listar(
    tipo: str | None = Query(default=None, description="Filtra por tipo de caso"),
    usuario: Usuario = Depends(usuario_actual),
) -> list[ResumenCaso]:
    raise PENDIENTE


@router.post(
    "",
    response_model=DetalleCaso,
    status_code=status.HTTP_201_CREATED,
    summary="Crear o duplicar un caso",
    responses={501: {"model": Problema}},
)
async def crear(
    nuevo: NuevoCaso,
    usuario: Usuario = Depends(
        requiere(
            Perfil.ADMINISTRADOR,
            Perfil.LIDER_DE_ESTUDIO,
            Perfil.INGENIERO_DE_PROYECTO,
        )
    ),
) -> DetalleCaso:
    """Crea un caso en estado borrador.

    Con `duplicar_de`, copia los insumos de un caso existente. El duplicado
    nace en borrador y con revision de inputs 1: es un caso nuevo, no una
    version del anterior.
    """
    raise PENDIENTE


@router.get(
    "/{id_caso}",
    response_model=DetalleCaso,
    summary="Detalle de un caso",
    responses={404: {"model": Problema}},
)
async def detalle(
    id_caso: str = Path(examples=["CASO-SR-2026-014"]),
    usuario: Usuario = Depends(usuario_actual),
) -> DetalleCaso:
    """Incluye las acciones disponibles para el perfil del solicitante."""
    raise PENDIENTE


@router.get(
    "/{id_caso}/comparar/{id_otro}",
    summary="Comparar dos casos",
    responses={409: {"model": Problema}},
)
async def comparar(
    id_caso: str,
    id_otro: str,
    usuario: Usuario = Depends(usuario_actual),
) -> dict[str, Any]:
    """Compara el caso sin proyecto contra uno o varios casos con proyecto.

    Advierte cuando las corridas no son comparables: contrastar un caso base
    calculado con una version mayor del motor contra otro calculado con una
    version mayor distinta produce una diferencia que no es atribuible al
    proyecto.
    """
    raise PENDIENTE
