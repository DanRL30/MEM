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

El bloque de gastos de `InputsOpex` vive aquí y no en un módulo propio porque
comparte su línea del contraste: la hoja resumen del estándar corporativo agrupa
`Mine, Plant, Tailings, Power Substation, G&A` en una sola línea, y G&A son
estos gastos. Dos de sus filas no se cargan porque el libro las deriva:
`Planilla` sale del cash cost de la unidad y `Gestión Social Deducible` es la
parte de la gestión social que la base imponible admite.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

GASTOS_ADMINISTRATIVOS = "Gastos administrativos"
GESTION_SOCIAL = "Gestión Social"
PREDIOS = "Predios"
SERVIDUMBRES = "Servidumbres y usufructos"
ESTUDIOS_DE_GASTO = "Estudios Pre Factibilidad (Gasto)"
ESTUDIOS_CAPITALIZABLES = "Estudios Factibilidad (Capitalizable)"
EXPLORACIONES = "Exploraciones"
"""Conceptos del bloque de gastos que el usuario carga, uno por unidad.

Los nombres viven en el motor y no en la ingesta porque los necesitan los dos:
la plantilla los escribe como etiquetas y el cálculo decide con ellos a qué
línea del flujo va cada uno. Repetirlos en ambos lados los deja divergir.
"""

PLANILLA = "Planilla"
GESTION_SOCIAL_DEDUCIBLE = "Gestión Social Deducible"
"""Los dos conceptos que el motor deriva y la plantilla no pide."""

DONACIONES = "Donaciones"
"""El rotulo con que el libro escribe la gestion social en la hoja `Otros`.

**No es un concepto aparte y la plantilla no lo pide.** `Otros!29` y
`Otros!48` se rotulan `Donaciones` y las dos leen `InputsOpex!175`, que se
llama `Gestion Social`; el bloque de gastos del libro no tiene ninguna fila
de donaciones. Hasta el 04/09/2026 la plataforma pedia las dos cosas por
separado, porque la regla `055` dedujo el concepto de ese rotulo. El nombre
se conserva donde el libro lo escribe -es el que el cliente reconoce- y el
calculo pasa a ser el del libro. Es la regla `094`.
"""


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


def planilla(cash_cost: float, tasa: float) -> float:
    """Planilla del año: el cash cost de la unidad por la tasa del supuesto.

    El libro no la carga: la calcula sobre el costo de la unidad con la tasa de
    `Supuestos`. Pedirla como dato dejaría al usuario tecleando un valor que el
    modelo deriva, y que quedaría desactualizado en cuanto cambiara un costo.
    """
    return cash_cost * tasa


def parte_deducible(gasto: float, fraccion: float) -> float:
    """Parte de un gasto que admite la base imponible.

    La gestión social entra entera en el flujo y solo en parte en la base
    imponible. El libro escribe la fila deducible como una copia de la otra,
    afectada en algunos escenarios por una fracción. Sin fracción declarada, el
    gasto es deducible entero, que es lo que hace el libro por defecto.
    """
    return gasto * fraccion


def total_de_conceptos(conceptos: Mapping[str, float]) -> float:
    """Suma de una lista abierta de conceptos.

    El acuerdo 6 de la minuta del 27/08/2026 permite al usuario añadir
    conceptos de costo propios del proyecto, que solo afectan al total. Por eso
    los conceptos son un mapa y no campos fijos: el motor no necesita conocer
    sus nombres para sumarlos.
    """
    return sum(conceptos.values())
