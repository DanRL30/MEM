"""Horizonte de evaluación y factores de descuento.

Toda serie del motor está alineada a un horizonte: una posición por año, sin
huecos. Esa alineación es lo que permite que el contraste N1 compare línea y
año contra la celda equivalente del modelo, y por eso las series se validan al
entrar y no cuando ya se mezclaron con otras.

El factor de descuento reproduce el del modelo corporativo, que descuenta **a
fin de año**: 1 / (1 + tasa) ^ t, con t entero desde 0. El estándar
`DM-STD-PE-27` §5.1 pide descontar desde la mitad de cada año, y el modelo no
lo hace. Finanzas confirmó el 01/09/2026 que se reproduce el modelo y que la
diferencia se reporta como discrepancia. Ver la regla 005 de
`docs/modelo-economico/reglas-no-documentadas.md`.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

Serie = tuple[float, ...]

ANOS_MAXIMOS = 60


class ErrorHorizonte(ValueError):
    """El horizonte o una serie alineada a él son inválidos."""


@dataclass(frozen=True)
class Horizonte:
    """Ventana de evaluación del caso, en años calendario consecutivos.

    El horizonte no lleva año de valuación propio: el descuento del modelo
    corporativo toma el primer año como período cero. Separar ambos conceptos
    invitaría a desalinear una serie respecto de su factor de descuento, que es
    la clase de error que un contraste por indicadores no detecta.
    """

    primer_ano: int
    anos: int

    def __post_init__(self) -> None:
        if self.anos < 1:
            raise ErrorHorizonte(f"El horizonte necesita al menos un ano, recibido {self.anos}.")
        if self.anos > ANOS_MAXIMOS:
            raise ErrorHorizonte(
                f"Horizonte de {self.anos} anos por encima del maximo de {ANOS_MAXIMOS}. "
                "Un horizonte mayor casi siempre es un error de carga de la plantilla."
            )
        if not 1900 <= self.primer_ano <= 2200:
            raise ErrorHorizonte(f"Primer ano fuera de rango razonable: {self.primer_ano}.")

    @property
    def anos_calendario(self) -> tuple[int, ...]:
        return tuple(self.primer_ano + i for i in range(self.anos))

    def serie(self, valores: Iterable[float], *, nombre: str) -> Serie:
        """Valida una serie contra el horizonte y la congela.

        Rechaza longitudes distintas y valores no finitos. Un `nan` que entra
        aquí se propaga hasta el NPV y allí ya no se puede atribuir a su
        origen, así que se detiene en la frontera.
        """
        serie = tuple(float(v) for v in valores)
        if len(serie) != self.anos:
            raise ErrorHorizonte(
                f"La serie {nombre!r} trae {len(serie)} valores y el horizonte tiene "
                f"{self.anos} anos."
            )
        for i, v in enumerate(serie):
            if not math.isfinite(v):
                raise ErrorHorizonte(
                    f"La serie {nombre!r} tiene un valor no finito en el ano "
                    f"{self.anos_calendario[i]}."
                )
        return serie

    def ceros(self) -> Serie:
        """Serie nula del largo del horizonte, para unidades que no participan."""
        return tuple(0.0 for _ in range(self.anos))

    def factores_descuento(self, tasa: float) -> Serie:
        """Factores de descuento a fin de año, uno por año del horizonte."""
        if tasa <= -1:
            raise ErrorHorizonte(f"Tasa de descuento invalida: {tasa}.")
        return tuple(1.0 / (1.0 + tasa) ** t for t in range(self.anos))


def anos_con_dato(serie: Sequence[float]) -> tuple[int, ...]:
    """Posiciones con valor distinto de cero.

    Finanzas fijó el 01/09/2026 el criterio de participación: una unidad entra
    en el caso en los años en que tiene datos. No hay interruptor que la
    active, de modo que la ventana de participación se deriva de la serie y no
    puede contradecirla.
    """
    return tuple(i for i, v in enumerate(serie) if v != 0.0)
