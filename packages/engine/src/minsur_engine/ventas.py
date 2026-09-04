"""Ventas: metal refinado, metal en concentrado y liquidación del polimetálico.

Reproduce la hoja `Ventas` del libro corporativo, que tiene tres caminos de
ingreso y no uno:

1. **Estaño refinado**, que se vende al precio spot más un premio.
2. **Estaño en concentrado**, que se vende al precio spot afectado por el
   factor de metal pagable, porque el comprador no paga el contenido entero.
3. **Concentrado polimetálico**, que no se vende a un precio sino que se
   liquida: se valoriza el contenido pagable de cada metal y se descuentan
   maquila, refinación y penalidades.

Todo el módulo trabaja en dólares. El libro alterna dólares y miles de dólares
con factores de 10^3 repartidos por las fórmulas —es la regla 003 del registro,
todavía sin confirmar— y esa mezcla no se propaga al motor: las conversiones
son de frontera, en la ingesta.

## Dos detalles que el contraste N1 delata si se pierden

**La plata se paga por onza troy.** Su ley viene en gramos por tonelada y el
libro divide entre 31,1035 para convertirla. El cobre no lleva conversión.

**El valor pagable usa las toneladas vendidas y los cargos usan las netas.** La
merma se descuenta para maquila y refinación, pero no para valorizar el
contenido. Es asimétrico y es lo que hace el libro.

## Tres filas que el libro presenta como supuesto y son cálculo

La hoja `Supuestos` declara la ley pagable de cada metal y los dos cargos de
refinación como si fueran datos, pero las tres salen de una fórmula: la ley
pagable, de la ley del concentrado con su deducción mínima y su factor
(regla 023); la refinación del cobre, de una tarifa por libra convertida a
tonelada (regla 021); y la de la plata, de la ley pagable por una tarifa por
onza troy (regla 022). Aquí están las tres, para que el caso pueda declararlas
y el sistema las corrobore.

**La ley pagable de la plata no se calcula.** La fórmula del libro multiplica
por cien una ley que viene en onzas por tonelada, mezclando dos unidades; el
factor correcto sería 31,1035 y ponerlo sería corregir el modelo. Es la regla
045 y está consultada: hasta la respuesta, la de plata se carga como dato.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

GRAMOS_POR_ONZA_TROY = 31.1035
LIBRAS_POR_TONELADA = 2204.62
"""Conversión de la tarifa de refinación del cobre, que se cotiza por libra."""


class ErrorVentas(ValueError):
    """Los datos comerciales de un año no son consistentes."""


@dataclass(frozen=True)
class MetalPagable:
    """Contenido liquidable de un metal dentro del concentrado."""

    nombre: str
    ley_pagable: float
    """Ley que el comprador paga, ya neta de deducciones mínimas."""

    precio: float
    """Precio del metal, en dólares por unidad de contenido."""

    cargo_de_refinacion: float
    """RC, en dólares por tonelada neta de concentrado."""

    en_onzas_troy: bool = False
    """Cierto para los metales preciosos, cuya ley viene en gramos por tonelada."""

    penalidades: float = 0.0
    """Penalidad del embarque atribuible a este metal, en dólares."""


@dataclass(frozen=True)
class LiquidacionMetal:
    nombre: str
    valor_pagable: float
    cargo_de_refinacion: float
    ley_pagable: float = 0.0
    """La ley con la que se pago, en la unidad en que viene la del metal.

    Es la fila `Ley Pagable` del libro, y viaja con la liquidacion porque el
    caso puede declararla o dejar que el motor la calcule: sin ella, quien mira
    la liquidacion no sabe cual de las dos se uso.
    """

    volumen_pagable: float = 0.0
    """Contenido que el comprador paga, en toneladas para el cobre y en onzas
    troy para la plata. Es la línea `Volumen Pagable` del libro."""

    penalidades: float = 0.0

    @property
    def valor_neto(self) -> float:
        return self.valor_pagable - self.cargo_de_refinacion


@dataclass(frozen=True)
class LiquidacionConcentrado:
    """Resultado de liquidar un embarque de concentrado polimetálico."""

    toneladas_vendidas: float
    toneladas_netas: float
    metales: tuple[LiquidacionMetal, ...]
    maquila: float

    @property
    def valor_pagable(self) -> float:
        return sum(m.valor_pagable for m in self.metales)

    @property
    def penalidades(self) -> float:
        """Penalidades del embarque, que el libro lleva por metal."""
        return sum(m.penalidades for m in self.metales)

    @property
    def cargos(self) -> float:
        """Maquila más refinación. No incluye penalidades: ver `total_con_penalidades`."""
        return self.maquila + sum(m.cargo_de_refinacion for m in self.metales)

    @property
    def valor_neto(self) -> float:
        """Lo que el libro lleva a la línea de venta.

        **Las penalidades quedan fuera.** El libro las calcula en la fila de
        cargos y las suma al total del concentrado, pero el valor neto que
        alimenta la venta se arma solo con valor pagable menos maquila y
        refinación. Se reproduce tal cual, y la diferencia está registrada como
        regla 010 en `docs/modelo-economico/reglas-no-documentadas.md`.
        """
        return self.valor_pagable - self.cargos

    @property
    def total_con_penalidades(self) -> float:
        """Valor neto descontando además las penalidades. No entra en la venta."""
        return self.valor_neto - self.penalidades


def ley_pagable(ley: float, deduccion_minima: float, factor_pagable: float) -> float:
    """Ley que el comprador paga, en la unidad en que viene la ley.

    Es la regla 023: `max(0, min(ley - deduccion minima, ley x factor pagable))`.
    El comprador descuenta una deducción fija y, por separado, reconoce solo una
    fracción del contenido; se cobra la menor de las dos y nunca menos de cero.

    El libro escribe `ley x 100 - deduccion minima` porque su ley está en
    porcentaje. Aquí no aparece el cien: la escala se convierte en la ingesta, de
    modo que la ley y la deducción llegan en la misma unidad y la resta es
    directa. **Vale para el cobre, cuya ley y cuya deducción van en fracción.**
    Para la plata el libro repite la fórmula sobre onzas por tonelada, que es la
    regla 045, consultada y sin implementar.
    """
    return max(0.0, min(ley - deduccion_minima, ley * factor_pagable))


def cargo_de_refinacion_del_cobre(tarifa_por_libra: float) -> float:
    """RC del cobre en dólares por tonelada, desde su tarifa por libra.

    Es la regla 021: el libro escribe `0,02 x 2204,62` dentro de la fórmula. Los
    dos centavos son la tarifa y entran por la plantilla; la conversión de libra
    a tonelada es física y vive aquí.
    """
    return tarifa_por_libra * LIBRAS_POR_TONELADA


def cargo_de_refinacion_de_la_plata(
    ley_pagable_de_la_plata: float, tarifa_por_onza: float
) -> float:
    """RC de la plata en dólares por tonelada de concentrado.

    Es la regla 022: `ley pagable x 0,6 / 31,1035`. **No es un dato**: se deriva
    de la ley pagable, que a su vez sale de la producción de la unidad, y por eso
    el cargo es distinto en cada origen aunque el libro lo declare una vez.
    """
    return ley_pagable_de_la_plata / GRAMOS_POR_ONZA_TROY * tarifa_por_onza


def venta_de_metal_refinado(volumen: float, precio_spot: float, premio: float) -> float:
    """Estaño refinado: volumen por precio, y el premio se suma al spot."""
    return volumen * (precio_spot + premio)


def venta_de_metal_en_concentrado(
    volumen: float, precio_spot: float, factor_metal_pagable: float
) -> float:
    """Estaño en concentrado: el comprador paga una fracción del contenido."""
    if not 0.0 <= factor_metal_pagable <= 1.0:
        raise ErrorVentas(
            f"El factor de metal pagable vale {factor_metal_pagable} y se espera una fraccion "
            "entre 0 y 1."
        )
    return volumen * precio_spot * factor_metal_pagable


def liquidar_concentrado(
    *,
    toneladas_vendidas: float,
    merma: float,
    metales: Sequence[MetalPagable],
    maquila_por_tonelada: float,
) -> LiquidacionConcentrado:
    """Liquida un embarque: valoriza el contenido pagable y descuenta cargos."""
    if not 0.0 <= merma < 1.0:
        raise ErrorVentas(f"La merma vale {merma} y se espera una fraccion entre 0 y 1.")
    if toneladas_vendidas < 0.0:
        raise ErrorVentas(f"Toneladas vendidas negativas: {toneladas_vendidas}.")

    toneladas_netas = (1.0 - merma) * toneladas_vendidas

    liquidaciones = []
    for metal in metales:
        contenido = metal.ley_pagable
        if metal.en_onzas_troy:
            contenido /= GRAMOS_POR_ONZA_TROY
        liquidaciones.append(
            LiquidacionMetal(
                nombre=metal.nombre,
                ley_pagable=metal.ley_pagable,
                # El contenido se valoriza sobre las toneladas vendidas...
                valor_pagable=contenido * metal.precio * toneladas_vendidas,
                # ...y los cargos se cobran sobre las netas de merma.
                cargo_de_refinacion=metal.cargo_de_refinacion * toneladas_netas,
                volumen_pagable=contenido * toneladas_vendidas,
                penalidades=metal.penalidades,
            )
        )

    return LiquidacionConcentrado(
        toneladas_vendidas=toneladas_vendidas,
        toneladas_netas=toneladas_netas,
        metales=tuple(liquidaciones),
        maquila=maquila_por_tonelada * toneladas_netas,
    )


def venta_total(
    *,
    metal_refinado: float,
    metal_en_concentrado: float,
    concentrado: LiquidacionConcentrado | None,
    ajustes: float = 0.0,
) -> float:
    """Venta del año, que es lo que la hoja `Impuestos` toma como base.

    El libro llega al ingreso del concentrado por un rodeo: divide el valor
    neto entre las toneladas para obtener un precio unitario y vuelve a
    multiplicarlo por las toneladas. El rodeo se cancela y el resultado es el
    valor neto, así que aquí se suma directamente. La única consecuencia
    observable de la diferencia sería un embarque de cero toneladas, y ahí el
    libro protege la división con `IFERROR` y devuelve cero, que es lo mismo
    que dejar el término fuera.
    """
    neto = concentrado.valor_neto if concentrado is not None else 0.0
    return metal_refinado + metal_en_concentrado + neto + ajustes
