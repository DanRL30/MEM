"""Producción: agregación de leyes y restricción de capacidad de fundición.

Las series de producción son datos del caso, no resultados: el libro
corporativo las tiene como valores dentro de la banda de cada caso. Lo que sí
calcula, y este módulo reproduce, son tres reglas que se leyeron directamente
de sus fórmulas.

**La ley agregada es un promedio ponderado por tonelaje**, no una media de las
leyes anuales. El libro lo resuelve con `SUMPRODUCT(tonelaje, ley) / SUM(tonelaje)`.
La distinción no es sutil: con producción variable a lo largo del horizonte,
una media simple y una ponderada difieren muy por encima de la tolerancia de
N1. La ley del concentrado se pondera por la producción de concentrado y no por
el mineral tratado, que es una excepción fácil de pasar por alto.

**El complejo tiene un cuello de botella.** Todas las unidades entregan
concentrado a la fundición, y la fundición tiene una capacidad máxima. El libro
la escribía como el número 90 000 dentro de la fórmula; Finanzas confirmó el
01/09/2026 que es capacidad de planta y que el usuario debe poder cambiarla, de
modo que aquí es un dato del caso. Ver la regla 002 de
`docs/modelo-economico/reglas-no-documentadas.md`.

La forma original era `(suma) + IF(suma > 90000, 90000 - suma, 0)`, que es
`min(suma, capacidad)` escrito de manera indirecta, con su complementaria
`IF(suma > 90000, suma - 90000, 0)` para el excedente. Se reproduce el
resultado, no la redacción.
"""

from __future__ import annotations

from collections.abc import Sequence

from minsur_engine.horizonte import Horizonte, Serie


class ErrorProduccion(ValueError):
    """Las series de producción no son consistentes entre sí."""


def ley_agregada(tonelajes: Sequence[float], leyes: Sequence[float]) -> float:
    """Ley media del horizonte, ponderada por tonelaje.

    Con tonelaje total nulo devuelve 0. Es el comportamiento del libro, que
    envuelve estas divisiones en `IFERROR`, y Finanzas confirmó el 01/09/2026
    que cero es el resultado esperado y que una indeterminación no debe detener
    el cálculo (regla 008).
    """
    if len(tonelajes) != len(leyes):
        raise ErrorProduccion(
            f"El tonelaje trae {len(tonelajes)} valores y la ley {len(leyes)}; "
            "la ponderacion exige la misma longitud."
        )
    total = sum(tonelajes)
    if total == 0.0:
        return 0.0
    return sum(t * ley for t, ley in zip(tonelajes, leyes, strict=True)) / total


def alimentacion_a_fundicion(horizonte: Horizonte, aportes: Sequence[Serie]) -> Serie:
    """Concentrado que las unidades entregan a la fundición, año a año.

    Cada unidad aporta su serie. El libro las suma explícitamente, una celda
    por unidad, porque el número de unidades está fijado por la banda; aquí la
    suma es sobre las que el caso declare, que es lo que permite que un
    proyecto nuevo se sume sin tocar el motor.
    """
    for i, aporte in enumerate(aportes):
        if len(aporte) != horizonte.anos:
            raise ErrorProduccion(
                f"El aporte {i} trae {len(aporte)} valores y el horizonte tiene "
                f"{horizonte.anos} anos."
            )
    if not aportes:
        return horizonte.ceros()
    return tuple(sum(valores) for valores in zip(*aportes, strict=True))


def tratamiento_limitado(alimentado: Serie, capacidad: Serie) -> Serie:
    """Concentrado efectivamente tratado, acotado por la capacidad de cada año."""
    _verificar_capacidad(alimentado, capacidad)
    return tuple(min(a, c) for a, c in zip(alimentado, capacidad, strict=True))


def excedente_por_capacidad(alimentado: Serie, capacidad: Serie) -> Serie:
    """Concentrado que la capacidad deja fuera. Cero cuando no hay restricción."""
    _verificar_capacidad(alimentado, capacidad)
    return tuple(max(a - c, 0.0) for a, c in zip(alimentado, capacidad, strict=True))


def _verificar_capacidad(alimentado: Serie, capacidad: Serie) -> None:
    if len(alimentado) != len(capacidad):
        raise ErrorProduccion(
            f"El alimentado trae {len(alimentado)} valores y la capacidad {len(capacidad)}."
        )
    for i, c in enumerate(capacidad):
        if c < 0.0:
            raise ErrorProduccion(f"Capacidad negativa en la posicion {i}: {c}.")
