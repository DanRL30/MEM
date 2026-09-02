"""Tablero de visualización y estados financieros estimados."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from minsur_engine.cash_cost import cash_cost_unitario

from ..dependencias import repositorio
from ..esquemas import EstadosFinancieros, Problema, ResultadoExportacion, Tablero
from ..evaluacion import indicadores_de
from ..repositorio import CorridaAlmacenada, RepositorioDeCasos
from ..seguridad import Usuario, usuario_actual

router = APIRouter(tags=["Tablero"])

SIN_CORRIDA = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail={
        "detalle": "El caso no tiene ninguna corrida. Calculalo antes de abrir el tablero.",
        "restriccion": None,
    },
)

SIN_ALMACENAMIENTO = HTTPException(
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    detail={
        "detalle": (
            "La exportacion deposita el archivo en el almacenamiento y devuelve una firma "
            "de lectura de corta vigencia. Esa cuenta se aprovisiona en el tenant de MINSUR, "
            "que aun no esta habilitado."
        ),
        "restriccion": "R-23",
    },
)


def _corrida(repo: RepositorioDeCasos, id_caso: str | None) -> CorridaAlmacenada:
    """Ultima corrida del caso pedido, o la mas reciente si no se indica caso."""
    if id_caso:
        corrida = repo.ultima_corrida(id_caso)
    else:
        recientes, _ = repo.historial(limite=1)
        corrida = recientes[0] if recientes else None
    if corrida is None:
        raise SIN_CORRIDA
    return corrida


@router.get(
    "/tablero",
    response_model=Tablero,
    summary="Indicadores, cascada y curvas del caso",
    responses={501: {"model": Problema}},
)
async def tablero(
    caso: str | None = Query(default=None, description="Caso a mostrar"),
    usuario: Usuario = Depends(usuario_actual),
    repo: RepositorioDeCasos = Depends(repositorio),
) -> Tablero:
    """Apertura comprometida por debajo de cinco segundos.

    Es la tercera de las cinco comprobaciones obligatorias de la ventana de
    pase, que mide esa latencia contra el objetivo del alcance.
    """
    corrida = _corrida(repo, caso)
    resultado = corrida.resultado
    anos = resultado.caso.horizonte.anos_calendario
    tributos = [
        regalia + renta
        for regalia, renta in zip(resultado.regalias, resultado.impuesto_renta, strict=True)
    ]
    return Tablero(
        id_caso=corrida.id_caso,
        indicadores=indicadores_de(corrida),
        cascada=[
            {"concepto": "Ventas", "valor": sum(resultado.ventas)},
            {"concepto": "Cash cost", "valor": -sum(resultado.cash_cost)},
            {"concepto": "Tributos", "valor": -sum(tributos)},
            {"concepto": "Capital", "valor": -sum(resultado.capex)},
        ],
        curva_produccion=[
            {"ano": ano, "valor": valor}
            for ano, valor in zip(anos, resultado.complejo.concentrado_alimentado, strict=True)
        ],
        curva_costo_unitario=[
            {"ano": ano, "valor": cash_cost_unitario(costo, tratado)}
            for ano, costo, tratado in zip(
                anos, resultado.cash_cost, resultado.complejo.concentrado_alimentado, strict=True
            )
        ],
        capex_por_etapa=[
            {"ano": ano, "valor": valor} for ano, valor in zip(anos, resultado.capex, strict=True)
        ],
    )


@router.get(
    "/estados-financieros",
    response_model=EstadosFinancieros,
    summary="Estados financieros estimados, auditables linea por linea",
    responses={501: {"model": Problema}},
)
async def estados_financieros(
    caso: str | None = Query(default=None),
    usuario: Usuario = Depends(usuario_actual),
    repo: RepositorioDeCasos = Depends(repositorio),
) -> EstadosFinancieros:
    """Cada linea con un valor por ano del horizonte detectado.

    La auditabilidad linea por linea es lo que permite localizar una
    discrepancia contra el modelo de referencia en el bloque que la origina,
    y no solo constatar que el indicador final difiere.
    """
    corrida = _corrida(repo, caso)
    resultado = corrida.resultado
    return EstadosFinancieros(
        id_caso=corrida.id_caso,
        anios=list(resultado.caso.horizonte.anos_calendario),
        lineas={
            "Ventas": list(resultado.ventas),
            "Cash cost": list(resultado.cash_cost),
            "Regalias": list(resultado.regalias),
            "Participacion de trabajadores": list(resultado.participacion_trabajadores),
            "Impuesto a la renta": list(resultado.impuesto_renta),
            "EBITDA ajustado": list(resultado.flujo.ebitda_ajustado),
            "Flujo operativo": list(resultado.flujo.flujo_operativo),
            "Flujo de inversiones": list(resultado.flujo.flujo_de_inversiones),
            "Flujo economico": list(resultado.flujo.flujo_economico),
            "Variacion de capital de trabajo": list(resultado.variacion_capital_trabajo),
        },
    )


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
    raise SIN_ALMACENAMIENTO
