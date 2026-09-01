"""Depreciación tributaria y financiera, calculada por mina.

Es el bloque más denso del libro: 58 767 fórmulas, y la desviación acordada
`D-04` obliga además a calcularlo **separado por mina** en todos los casos, no
solo en los que el libro lo hace.

## La cuota, tal como la escribe el libro

Cada año de inversión abre su propio cronograma, y la cuota de cada ejercicio
sale de esta fórmula, leída de la fila 132 en adelante:

    IF(base - acumulado > base * tasa,  base * tasa,  base - acumulado)

Es depreciación lineal sobre el valor original, con la particularidad de que
**la última cuota se ajusta al saldo**: cuando lo que queda por depreciar es
menor que la cuota lineal, se deprecia el resto y el activo queda en cero. Sin
ese ajuste, el último ejercicio arrastra un residuo que el contraste detecta
como una diferencia pequeña y persistente.

## La depreciación no corre antes de producir

La fila que consolida la depreciación de maquinaria la condiciona a que haya
producción acumulada:

    IF(SUM(produccion hasta el ano) = 0, 0, ...)

Un activo construido antes del arranque no deprecia hasta que la unidad
produce. Reproducirlo importa en los proyectos con años de construcción, que
son justamente los que la plataforma va a evaluar.

## Dos juegos de tasas, no dos métodos

La tributaria y la financiera comparten el mecanismo y difieren en las tasas y
en qué activos entran. Por eso aquí hay una función y no dos: el juego de tasas
es un parámetro.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from minsur_engine.capex import NATURALEZAS, CapitalDeUnidad
from minsur_engine.horizonte import Horizonte, Serie


class ErrorDepreciacion(ValueError):
    """Las tasas o las bases de depreciación no son consistentes."""


@dataclass(frozen=True)
class TasasDeDepreciacion:
    """Tasa anual por naturaleza contable, en tanto por uno.

    `no_depreciable` no aparece: su tasa es cero por definición y declararla
    invitaría a cambiarla.
    """

    maquinaria: float
    instalaciones: float
    edificaciones: float

    def __post_init__(self) -> None:
        for nombre in ("maquinaria", "instalaciones", "edificaciones"):
            tasa = getattr(self, nombre)
            if not 0.0 < tasa <= 1.0:
                raise ErrorDepreciacion(
                    f"La tasa de {nombre} vale {tasa} y se espera una fraccion mayor que 0 y "
                    "hasta 1. Una tasa del 10 % se escribe 0.10."
                )

    def de(self, naturaleza: str) -> float:
        if naturaleza == "no_depreciable":
            return 0.0
        if naturaleza not in NATURALEZAS:
            raise ErrorDepreciacion(f"Naturaleza {naturaleza!r} desconocida.")
        tasa: float = getattr(self, naturaleza)
        return tasa


def cuota(base: float, tasa: float, acumulado: float) -> float:
    """Cuota de un ejercicio, con la última ajustada al saldo pendiente."""
    pendiente = base - acumulado
    if pendiente <= 0.0:
        return 0.0
    lineal = base * tasa
    return lineal if pendiente > lineal else pendiente


def cronograma_de_inversion(base: float, tasa: float, ejercicios: int) -> Serie:
    """Cuotas que genera una inversión desde el ejercicio en que se realiza."""
    if ejercicios < 0:
        raise ErrorDepreciacion(f"Numero de ejercicios negativo: {ejercicios}.")
    cuotas: list[float] = []
    acumulado = 0.0
    for _ in range(ejercicios):
        actual = cuota(base, tasa, acumulado)
        cuotas.append(actual)
        acumulado += actual
    return tuple(cuotas)


def depreciar(horizonte: Horizonte, inversiones: Serie, tasa: float) -> Serie:
    """Depreciación anual de una serie de inversiones.

    Cada año de inversión abre su cronograma y los cronogramas se superponen,
    que es exactamente la forma triangular que tiene la hoja: una fila por año
    de inversión y una suma en diagonal.
    """
    if len(inversiones) != horizonte.anos:
        raise ErrorDepreciacion(
            f"La serie de inversiones trae {len(inversiones)} valores y el horizonte tiene "
            f"{horizonte.anos} anos."
        )
    total = [0.0] * horizonte.anos
    for ano, base in enumerate(inversiones):
        if base == 0.0:
            continue
        for desplazamiento, valor in enumerate(
            cronograma_de_inversion(base, tasa, horizonte.anos - ano)
        ):
            total[ano + desplazamiento] += valor
    return tuple(total)


def depreciacion_de_unidad(
    horizonte: Horizonte,
    capital: CapitalDeUnidad,
    tasas: TasasDeDepreciacion,
    *,
    produccion: Serie | None = None,
) -> Serie:
    """Depreciación de una unidad, sumando sus naturalezas contables.

    Con `produccion`, aplica la condición del libro: no hay depreciación en los
    años previos al primero con producción acumulada.
    """
    total = [0.0] * horizonte.anos
    for naturaleza in NATURALEZAS:
        tasa = tasas.de(naturaleza)
        if tasa == 0.0:
            continue
        inversiones = capital.naturaleza(naturaleza, horizonte)
        for i, valor in enumerate(depreciar(horizonte, inversiones, tasa)):
            total[i] += valor

    if produccion is None:
        return tuple(total)
    return _sin_depreciar_antes_de_producir(horizonte, tuple(total), produccion)


def depreciacion_por_mina(
    horizonte: Horizonte,
    capitales: Sequence[CapitalDeUnidad],
    tasas: TasasDeDepreciacion,
    *,
    produccion: Mapping[str, Serie] | None = None,
) -> dict[str, Serie]:
    """Depreciación separada por unidad, que es lo que exige la desviación `D-04`.

    MINSUR pidió expresamente que el cálculo sea por mina en todos los casos,
    incluso donde el modelo de referencia consolida. Devolver el desglose y no
    el total es lo que hace esa desviación verificable: el agregado se obtiene
    sumando, pero el detalle no se puede recuperar de un agregado.
    """
    series = produccion or {}
    return {
        capital.unidad: depreciacion_de_unidad(
            horizonte, capital, tasas, produccion=series.get(capital.unidad)
        )
        for capital in capitales
    }


def total_depreciado(horizonte: Horizonte, por_mina: Mapping[str, Serie]) -> Serie:
    """Suma del desglose por mina, para las líneas que consolidan."""
    if not por_mina:
        return horizonte.ceros()
    return tuple(sum(valores) for valores in zip(*por_mina.values(), strict=True))


def _sin_depreciar_antes_de_producir(
    horizonte: Horizonte, depreciacion: Serie, produccion: Serie
) -> Serie:
    if len(produccion) != horizonte.anos:
        raise ErrorDepreciacion(
            f"La serie de produccion trae {len(produccion)} valores y el horizonte tiene "
            f"{horizonte.anos} anos."
        )
    acumulada = 0.0
    resultado: list[float] = []
    for i, valor in enumerate(depreciacion):
        acumulada += produccion[i]
        resultado.append(valor if acumulada != 0.0 else 0.0)
    return tuple(resultado)
