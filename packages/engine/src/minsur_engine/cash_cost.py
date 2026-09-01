"""Cash cost, gastos de venta y fletes.

Reproduce el bloque de costos de la hoja `Otros`, que es donde el libro
consolida lo que `InputsOpex` trae por unidad productiva y lo convierte en las
líneas que consume el flujo.

Tres cosas que este módulo hace explícitas y el libro deja implícitas:

**El cash cost es una suma por unidad, y nada más.** El libro escribe una fila
por unidad, con la referencia a su bloque de `InputsOpex`, y las suma. Al ser
una lista y no seis celdas, un proyecto nuevo entra sin tocar el cálculo.

**El signo lo pone el flujo, no el costo.** En la hoja los costos llegan
negados, porque el flujo los suma. Aquí un costo es un número positivo y quien
arma el flujo decide el signo: mezclar ambas convenciones es la forma más
rápida de equivocarse en una línea del contraste.

**El cash cost unitario divide entre toneladas y puede dividir entre cero.** El
libro lo envuelve en `IFERROR` y devuelve cero, y Finanzas confirmó el
01/09/2026 que ese es el resultado esperado y que una indeterminación no debe
detener el cálculo (regla 008).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


class ErrorCashCost(ValueError):
    """Los costos de un año no son consistentes."""


@dataclass(frozen=True)
class CostoDeUnidad:
    """Costo operativo de una unidad productiva en un año, en dólares."""

    unidad: str
    conceptos: Mapping[str, float]

    def __post_init__(self) -> None:
        for concepto, valor in self.conceptos.items():
            if valor < 0.0:
                raise ErrorCashCost(
                    f"El concepto {concepto!r} de {self.unidad!r} vale {valor}. Los costos se "
                    "expresan en positivo; el signo lo pone el flujo."
                )

    @property
    def total(self) -> float:
        return sum(self.conceptos.values())


def cash_cost_total(unidades: Sequence[CostoDeUnidad]) -> float:
    """Cash cost del caso: la suma de las unidades que participan."""
    return sum(unidad.total for unidad in unidades)


def cash_cost_por_unidad(unidades: Sequence[CostoDeUnidad]) -> dict[str, float]:
    """Cash cost desglosado, que es como el libro lo presenta y lo contrasta."""
    desglose: dict[str, float] = {}
    for unidad in unidades:
        if unidad.unidad in desglose:
            raise ErrorCashCost(
                f"La unidad {unidad.unidad!r} aparece dos veces. El cash cost quedaria duplicado."
            )
        desglose[unidad.unidad] = unidad.total
    return desglose


def cash_cost_unitario(costo: float, toneladas: float) -> float:
    """Cash cost por tonelada tratada. Con cero toneladas devuelve cero."""
    if toneladas == 0.0:
        return 0.0
    return costo / toneladas


def gasto_de_ventas(volumen: float, tarifa: float) -> float:
    """Gasto de venta de un producto: su volumen por la tarifa del supuesto."""
    return volumen * tarifa


def flete(toneladas: float, tarifa: float) -> float:
    """Flete del concentrado embarcado."""
    return toneladas * tarifa


def total_de_conceptos(conceptos: Mapping[str, float]) -> float:
    """Suma de una lista abierta de conceptos.

    El acuerdo 6 de la minuta del 27/08/2026 permite al usuario añadir
    conceptos de costo propios del proyecto, que solo afectan al total. Por eso
    los conceptos son un mapa y no campos fijos: el motor no necesita conocer
    sus nombres para sumarlos.
    """
    return sum(conceptos.values())
