"""Indicadores: NPV, TIR, payback y capital intensity.

Los cuatro salen del flujo económico y del factor de descuento, y los cuatro son
lo que el contraste N3 verifica. Sus tolerancias propuestas son estrechas —NPV
0,1 % o US$ 50 000, TIR 5 puntos básicos, payback 0,1 año— así que los detalles
de convención pesan más aquí que en ningún otro módulo.

**El descuento es a fin de año**, `1/(1+r)^t` con `t` entero desde cero. El
estándar corporativo pide mitad de año y el modelo no lo hace; Finanzas
confirmó el 01/09/2026 que se reproduce el modelo y que la diferencia queda
reportada. Es la regla 005.

**La TIR se calcula por bisección y no con la iteración de Excel.** Excel
resuelve la TIR partiendo de una semilla y puede converger a raíces distintas
según esa semilla. La bisección sobre un intervalo con cambio de signo es
determinista: dos corridas de la misma serie dan el mismo número, que es la
condición del sellado. Si la serie no tiene cambio de signo, no hay TIR y el
módulo lo dice en lugar de devolver un valor.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

TOLERANCIA_TIR = 1e-12
ITERACIONES_MAXIMAS = 200
TASA_MAXIMA_BUSCADA = 10.0


class ErrorIndicadores(ValueError):
    """El flujo no permite calcular el indicador pedido."""


@dataclass(frozen=True)
class Payback:
    """Año en que el flujo acumulado cruza a positivo."""

    anos: float
    """Fracción de años hasta la recuperación, interpolada dentro del ejercicio."""

    alcanzado: bool
    """Falso cuando el flujo nunca llega a recuperarse dentro del horizonte."""


def factores_de_descuento(tasa: float, anos: int) -> tuple[float, ...]:
    """Factores a fin de año, uno por ejercicio del horizonte."""
    if tasa <= -1.0:
        raise ErrorIndicadores(f"Tasa de descuento invalida: {tasa}.")
    if anos < 0:
        raise ErrorIndicadores(f"Numero de anos negativo: {anos}.")
    return tuple(1.0 / (1.0 + tasa) ** t for t in range(anos))


def npv(flujo: Sequence[float], tasa: float) -> float:
    """Valor presente neto del flujo económico, descontado a fin de año."""
    factores = factores_de_descuento(tasa, len(flujo))
    return sum(f * d for f, d in zip(flujo, factores, strict=True))


def tir(flujo: Sequence[float]) -> float:
    """Tasa interna de retorno, por bisección sobre el NPV.

    Busca el cambio de signo en un intervalo amplio y lo reduce hasta la
    tolerancia. Es más lento que el método de Excel y no depende de una semilla.
    """
    if not flujo:
        raise ErrorIndicadores("El flujo esta vacio.")
    if all(v >= 0.0 for v in flujo) or all(v <= 0.0 for v in flujo):
        raise ErrorIndicadores(
            "El flujo no cambia de signo, asi que no tiene TIR. Un proyecto sin desembolso o sin "
            "retorno no la define."
        )

    inferior, superior = -0.9999, TASA_MAXIMA_BUSCADA
    npv_inferior, npv_superior = npv(flujo, inferior), npv(flujo, superior)
    if npv_inferior * npv_superior > 0.0:
        raise ErrorIndicadores(
            "No se encontro cambio de signo del NPV entre -99,99 % y 1000 %. La serie puede tener "
            "varias raices o ninguna en ese rango."
        )

    for _ in range(ITERACIONES_MAXIMAS):
        medio = (inferior + superior) / 2.0
        npv_medio = npv(flujo, medio)
        if abs(npv_medio) < TOLERANCIA_TIR or (superior - inferior) < TOLERANCIA_TIR:
            return medio
        if npv_inferior * npv_medio < 0.0:
            superior = medio
        else:
            inferior, npv_inferior = medio, npv_medio
    return (inferior + superior) / 2.0


def payback(flujo: Sequence[float]) -> Payback:
    """Payback simple, con interpolación lineal dentro del año de cruce."""
    return _payback_sobre(list(flujo))


def payback_descontado(flujo: Sequence[float], tasa: float) -> Payback:
    """Payback sobre el flujo ya descontado a fin de año."""
    factores = factores_de_descuento(tasa, len(flujo))
    return _payback_sobre([f * d for f, d in zip(flujo, factores, strict=True)])


def capital_intensity(capex_total: float, capacidad_anual: float) -> float:
    """Capital por unidad de capacidad instalada.

    La definición exacta —qué capital y contra qué capacidad— la fija el
    estándar corporativo y está pendiente de confirmar con Finanzas. Hasta
    entonces el módulo hace la división y no elige por su cuenta qué entra en
    cada término.
    """
    if capacidad_anual <= 0.0:
        raise ErrorIndicadores(
            f"Capacidad anual invalida: {capacidad_anual}. Sin capacidad no hay intensidad de "
            "capital que calcular."
        )
    return capex_total / capacidad_anual


def _payback_sobre(flujo: list[float]) -> Payback:
    acumulado = 0.0
    for i, valor in enumerate(flujo):
        anterior = acumulado
        acumulado += valor
        if acumulado >= 0.0 and anterior < 0.0:
            # Interpolacion dentro del ejercicio: que fraccion del ano hizo
            # falta para cubrir lo que quedaba por recuperar.
            fraccion = -anterior / valor if valor != 0.0 else 0.0
            return Payback(anos=i + fraccion, alcanzado=True)
    return Payback(anos=float(len(flujo)), alcanzado=False)
