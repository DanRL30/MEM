"""El bloque del complejo: todo resultado, y componente a componente.

Ninguna fila de este bloque es un dato. La lectura de las fórmulas del libro lo
confirmó una por una: lo que alimenta al complejo es el concentrado de cada mina
y su ley, el consolidado es la suma acotada por la capacidad, la ley promedio es
el ponderado por tonelaje, y el excedente es lo que pasa del tope. Pedir
cualquiera de ellas como entrada invitaría a que contradijese a su origen.

**Regla de oro: nada se agrupa.** Cada unidad aporta con su propia recuperación
y su aporte al refinado se calcula por separado; el total es la suma de esos
aportes y no un cálculo hecho sobre magnitudes agregadas. El libro corporativo
agrupa —lleva una `Recuperación Sn SR + B2` y otra `NZ + SRP`— y ahí está el
problema: un proyecto nuevo no cabe en ningún grupo sin decidir a cuál se parece,
y una diferencia en el total no se puede atribuir a una unidad.

Las dos únicas entradas del bloque son supuestos, no producción: la capacidad del
complejo y la recuperación de cada componente. En el libro viven en la hoja
`Supuestos`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from minsur_engine.horizonte import Horizonte, Serie
from minsur_engine.produccion import (
    alimentacion_a_fundicion,
    excedente_por_capacidad,
    ley_agregada,
    tratamiento_limitado,
)


@dataclass(frozen=True)
class Componente:
    """Lo que una unidad entrega al complejo, con su propia recuperación."""

    unidad: str
    concentrado: Serie
    ley: Serie
    recuperacion: Serie = ()


@dataclass(frozen=True)
class AporteAlComplejo:
    """El aporte de una unidad, calculado sin mezclarlo con el de las demás.

    Que el refinado de cada componente salga por separado es lo que permite
    atribuir una diferencia a la unidad que la produce. Un total agregado solo
    dice que algo no cuadra.
    """

    unidad: str
    concentrado: Serie
    ley: Serie
    recuperacion: Serie
    refinado: Serie


@dataclass(frozen=True)
class BloqueDelComplejo:
    """El bloque completo, tal como lo escribe el libro."""

    aportes: tuple[AporteAlComplejo, ...]
    concentrado_entregado: Serie
    """Suma de lo que entregan las minas, antes del tope."""

    concentrado_alimentado: Serie
    """Lo que entra, ya acotado por la capacidad."""

    ley_de_alimentacion: Serie
    toneladas_alimentadas: Serie
    """Alimentado más escoria. En el libro la escoria no aporta nada."""

    refinado_sin_restriccion: Serie
    """Suma de los aportes, cada uno con su recuperación. Antes del tope."""

    concentrado_excedente: Serie
    ley_del_excedente: Serie
    refinado_del_excedente: Serie
    """Venta spot. El libro no le aplica recuperación: es metal contenido."""

    check: Serie
    """Tratado más excedente menos lo entregado. Debe ser cero."""


def calcular(
    horizonte: Horizonte,
    componentes: Sequence[Componente],
    capacidad: Serie = (),
) -> BloqueDelComplejo:
    """Rehace el bloque del complejo a partir de lo que producen las minas.

    Sin capacidad declarada no hay cuello de botella: todo lo entregado se trata
    y el excedente es cero.
    """
    entregado = alimentacion_a_fundicion(
        horizonte, [_serie(c.concentrado, horizonte) for c in componentes]
    )
    if capacidad:
        tope = _serie(capacidad, horizonte)
        alimentado = tratamiento_limitado(entregado, tope)
        excedente = excedente_por_capacidad(entregado, tope)
    else:
        alimentado, excedente = entregado, horizonte.ceros()

    ley = tuple(
        ley_agregada(
            [_en(c.concentrado, i) for c in componentes],
            [_en(c.ley, i) for c in componentes],
        )
        for i in range(horizonte.anos)
    )
    aportes = tuple(_aporte(c, horizonte) for c in componentes)
    refinado = tuple(sum(a.refinado[i] for a in aportes) for i in range(horizonte.anos))

    return BloqueDelComplejo(
        aportes=aportes,
        concentrado_entregado=entregado,
        concentrado_alimentado=alimentado,
        ley_de_alimentacion=ley,
        toneladas_alimentadas=alimentado,
        refinado_sin_restriccion=refinado,
        concentrado_excedente=excedente,
        ley_del_excedente=ley,
        refinado_del_excedente=tuple(excedente[i] * ley[i] for i in range(horizonte.anos)),
        check=tuple(alimentado[i] + excedente[i] - entregado[i] for i in range(horizonte.anos)),
    )


def _aporte(componente: Componente, horizonte: Horizonte) -> AporteAlComplejo:
    """El refinado de una unidad, con su recuperación y solo la suya."""
    concentrado = _serie(componente.concentrado, horizonte)
    ley = _serie(componente.ley, horizonte)
    recuperacion = _serie(componente.recuperacion, horizonte)
    return AporteAlComplejo(
        unidad=componente.unidad,
        concentrado=concentrado,
        ley=ley,
        recuperacion=recuperacion,
        refinado=tuple(concentrado[i] * ley[i] * recuperacion[i] for i in range(horizonte.anos)),
    )


def _serie(valores: Serie, horizonte: Horizonte) -> Serie:
    return horizonte.ceros() if not valores else valores


def _en(serie: Serie, i: int) -> float:
    return serie[i] if i < len(serie) else 0.0
