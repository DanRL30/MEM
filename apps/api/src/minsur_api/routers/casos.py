"""Gestión de casos: creación, duplicado, versionado y comparación."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from minsur_domain.estados import Estado, Perfil, acciones_disponibles

from ..dependencias import repositorio
from ..esquemas import DetalleCaso, NuevoCaso, Problema, ResumenCaso, Terna
from ..evaluacion import terna_de
from ..repositorio import (
    CasoAlmacenado,
    CasoNoEncontrado,
    RepositorioDeCasos,
    nuevo_id_de_caso,
)
from ..seguridad import Usuario, requiere, usuario_actual

router = APIRouter(prefix="/casos", tags=["Casos"])

NO_ENCONTRADO = "No existe un caso con ese identificador."


def _resumen(caso: CasoAlmacenado) -> ResumenCaso:
    return ResumenCaso(
        id_caso=caso.id_caso,
        abreviatura=caso.abreviatura,
        nombre=caso.nombre,
        tipo=caso.tipo,  # type: ignore[arg-type]
        estado=caso.estado,
        # Un caso guardado antes de que existieran estas dos columnas no las
        # tiene, y su creacion es lo mas antiguo que se sabe de el.
        creado_en=caso.creado_en or caso.actualizado_en,
        creado_por=caso.creado_por or caso.actualizado_por,
        actualizado_en=caso.actualizado_en,
        actualizado_por=caso.actualizado_por,
    )


def _detalle(caso: CasoAlmacenado, perfil: Perfil, terna: Terna | None) -> DetalleCaso:
    return DetalleCaso(
        **_resumen(caso).model_dump(),
        descripcion=caso.descripcion,
        terna=terna,
        acciones_disponibles=list(acciones_disponibles(caso.estado, perfil)),
    )


def _buscar(repo: RepositorioDeCasos, id_caso: str) -> CasoAlmacenado:
    try:
        return repo.obtener(id_caso)
    except CasoNoEncontrado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detalle": NO_ENCONTRADO, "restriccion": None},
        ) from None


@router.get("", response_model=list[ResumenCaso], summary="Listar casos")
async def listar(
    tipo: str | None = Query(default=None, description="Filtra por tipo de caso"),
    usuario: Usuario = Depends(usuario_actual),
    repo: RepositorioDeCasos = Depends(repositorio),
) -> list[ResumenCaso]:
    return [_resumen(caso) for caso in repo.listar(tipo=tipo)]


@router.post(
    "",
    response_model=DetalleCaso,
    status_code=status.HTTP_201_CREATED,
    summary="Crear o duplicar un caso",
    responses={404: {"model": Problema}},
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
    repo: RepositorioDeCasos = Depends(repositorio),
) -> DetalleCaso:
    """Crea un caso en estado borrador.

    Con `duplicar_de`, copia los insumos de un caso existente. El duplicado
    nace en borrador y con revision de inputs 1: es un caso nuevo, no una
    version del anterior.
    """
    ahora = datetime.now(UTC)
    insumos = None
    if nuevo.duplicar_de is not None:
        insumos = _buscar(repo, nuevo.duplicar_de).insumos

    caso = repo.guardar(
        CasoAlmacenado(
            id_caso=nuevo_id_de_caso(nuevo.tipo),
            abreviatura=nuevo.abreviatura,
            nombre=nuevo.nombre,
            tipo=nuevo.tipo,
            descripcion=nuevo.descripcion,
            estado=Estado.BORRADOR,
            creado_en=ahora,
            creado_por=usuario.correo,
            actualizado_en=ahora,
            actualizado_por=usuario.correo,
            insumos=insumos,
        )
    )
    return _detalle(caso, usuario.perfil, terna=None)


@router.get(
    "/{id_caso}",
    response_model=DetalleCaso,
    summary="Detalle de un caso",
    responses={404: {"model": Problema}},
)
async def detalle(
    id_caso: str = Path(examples=["CASO-SR-2026-014"]),
    usuario: Usuario = Depends(usuario_actual),
    repo: RepositorioDeCasos = Depends(repositorio),
) -> DetalleCaso:
    """Incluye las acciones disponibles para el perfil del solicitante."""
    caso = _buscar(repo, id_caso)
    corrida = repo.ultima_corrida(id_caso)
    return _detalle(caso, usuario.perfil, terna_de(corrida) if corrida else None)


@router.get(
    "/{id_caso}/comparar/{id_otro}",
    summary="Comparar dos casos",
    responses={404: {"model": Problema}, 409: {"model": Problema}},
)
async def comparar(
    id_caso: str,
    id_otro: str,
    usuario: Usuario = Depends(usuario_actual),
    repo: RepositorioDeCasos = Depends(repositorio),
) -> dict[str, Any]:
    """Compara el caso sin proyecto contra uno o varios casos con proyecto.

    Advierte cuando las corridas no son comparables: contrastar un caso base
    calculado con una version mayor del motor contra otro calculado con una
    version mayor distinta produce una diferencia que no es atribuible al
    proyecto.
    """
    primera = repo.ultima_corrida(_buscar(repo, id_caso).id_caso)
    segunda = repo.ultima_corrida(_buscar(repo, id_otro).id_caso)
    if primera is None or segunda is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detalle": "Ambos casos deben tener una corrida para poder compararse.",
                "restriccion": None,
            },
        )

    # Solo la version mayor importa: es la que significa que una regla de
    # calculo cambio y que los resultados difieren por el motor, no por el caso.
    comparables = primera.version_motor.split(".")[0] == segunda.version_motor.split(".")[0]
    npv_primera = primera.resultado.indicadores.npv
    npv_segunda = segunda.resultado.indicadores.npv

    return {
        "id_caso": id_caso,
        "id_otro": id_otro,
        "comparables": comparables,
        "advertencia": None
        if comparables
        else (
            "Las corridas se calcularon con versiones mayores distintas del motor. "
            "La diferencia incluye el cambio de logica y no es atribuible al proyecto."
        ),
        "delta_npv_musd": (npv_segunda - npv_primera) / 1_000_000.0,
        "versiones": {
            id_caso: primera.version_motor,
            id_otro: segunda.version_motor,
        },
    }
