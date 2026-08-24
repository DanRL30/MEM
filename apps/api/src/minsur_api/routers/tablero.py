"""Tablero de visualización y estados financieros estimados."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..esquemas import EstadosFinancieros, Problema, ResultadoExportacion, Tablero
from ..seguridad import Usuario, usuario_actual

router = APIRouter(tags=["Tablero"])

PENDIENTE = HTTPException(
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    detail={
        "detalle": (
            "El tablero se alimenta del motor de calculo, cuya construccion "
            "no ha iniciado por estar pendiente el modelo de referencia."
        ),
        "restriccion": "R-02",
    },
)


@router.get(
    "/tablero",
    response_model=Tablero,
    summary="Indicadores, cascada y curvas del caso",
    responses={501: {"model": Problema}},
)
async def tablero(
    caso: str | None = Query(default=None, description="Caso a mostrar"),
    usuario: Usuario = Depends(usuario_actual),
) -> Tablero:
    """Apertura comprometida por debajo de cinco segundos.

    Es la tercera de las cinco comprobaciones obligatorias de la ventana de
    pase, que mide esa latencia contra el objetivo del alcance.
    """
    raise PENDIENTE


@router.get(
    "/estados-financieros",
    response_model=EstadosFinancieros,
    summary="Estados financieros estimados, auditables linea por linea",
    responses={501: {"model": Problema}},
)
async def estados_financieros(
    caso: str | None = Query(default=None),
    usuario: Usuario = Depends(usuario_actual),
) -> EstadosFinancieros:
    """Cada linea con un valor por ano del horizonte detectado.

    La auditabilidad linea por linea es lo que permite localizar una
    discrepancia contra el modelo de referencia en el bloque que la origina,
    y no solo constatar que el indicador final difiere.
    """
    raise PENDIENTE


@router.get(
    "/casos/{id_caso}/exportar",
    response_model=ResultadoExportacion,
    summary="Exportar el tablero y los estados a Excel o PDF",
    responses={501: {"model": Problema}},
)
async def exportar(
    id_caso: str,
    destino: str = Query(default="descarga", pattern="^(descarga|sharepoint)$"),
    formato: str = Query(default="xlsx", pattern="^(xlsx|pdf)$"),
    usuario: Usuario = Depends(usuario_actual),
) -> ResultadoExportacion:
    """Genera el reporte y devuelve una URL temporal de lectura.

    El archivo se descarga directamente del almacenamiento, por el mismo
    mecanismo de firma que usa la carga: no atraviesa la puerta de enlace.

    Con `destino=sharepoint` publica ademas en la biblioteca documental del
    proyecto. Si el sitio aun no esta habilitado (R-44), la exportacion se
    completa y `url_sharepoint` queda vacia: es una limitacion de
    habilitacion, no un defecto de la plataforma.

    Es la cuarta de las cinco comprobaciones obligatorias del pase.
    """
    raise PENDIENTE
