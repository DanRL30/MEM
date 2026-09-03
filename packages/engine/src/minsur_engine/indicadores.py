"""Indicadores: NPV, TIR, payback y capital intensity.

Los cuatro salen del flujo económico y del factor de descuento, y los cuatro son
lo que el contraste N3 verifica. Sus tolerancias propuestas son estrechas —NPV
0,1 % o US$ 50 000, TIR 5 puntos básicos, payback 0,1 año— así que los detalles
de convención pesan más aquí que en ningún otro módulo.

**El descuento es a fin de año**, `1/(1+r)^t` con `t` entero desde cero. El
estándar corporativo pide mitad de año y el modelo no lo hace; Finanzas
confirmó el 01/09/2026 que se reproduce el modelo y que la diferencia queda
reportada. Es la regla 005.

**La TIR se calcula por barrido y bisección, no con la iteración de Excel.**
Excel parte de una semilla y puede converger a raíces distintas según cuál sea.
Aquí el intervalo se recorre entero en pasos fijos, se detecta cada cambio de
signo del NPV y cada uno se reduce por bisección: dos corridas de la misma serie
dan el mismo número, que es la condición del sellado. Y se entrega **solo cuando
el caso tiene desembolso inicial y la raíz es no negativa**; en cualquier otro
supuesto el módulo dice que no hay TIR en lugar de devolver un número que no
describe una rentabilidad.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

TOLERANCIA_TIR = 1e-12
ITERACIONES_MAXIMAS = 200
TASA_MINIMA_BUSCADA = -0.9999
TASA_MAXIMA_BUSCADA = 10.0
# Ancho del paso con que se recorre el intervalo buscando cambios de signo.
# Dos raices separadas por menos de medio punto porcentual quedan fuera de su
# resolucion, y ninguna evaluacion del servicio las produce.
PASO_DEL_BARRIDO = 0.005


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
    """Tasa interna de retorno, por barrido y bisección sobre el NPV.

    Se entrega **solo cuando el caso abre con desembolso y la raíz es no
    negativa**. Un flujo que abre en positivo describe una operación en marcha y
    no una inversión: cruza el eje únicamente en el tramo profundamente
    negativo, y esa raíz no es una rentabilidad. El libro llega a lo mismo por
    otro camino —su `IRR` no converge y el `IFERROR` escribe un guion—, de modo
    que ahí las dos herramientas coinciden en no dar el indicador. Lo decidió el
    Project Manager el 03/09/2026, y lo registra el ADR 0011.

    El intervalo se recorre entero en vez de corchetearse con sus extremos:
    mirar solo los bordes deja fuera la raíz de un proyecto que abre con
    desembolso y cierra con un ejercicio negativo, donde el NPV es negativo en
    los dos extremos y positivo en medio.

    Entre varias raíces no negativas se entrega la menor, que es la primera tasa
    a la que el proyecto deja de crear valor.
    """
    if not flujo:
        raise ErrorIndicadores("El flujo esta vacio.")
    if all(v >= 0.0 for v in flujo) or all(v <= 0.0 for v in flujo):
        raise ErrorIndicadores(
            "El flujo no cambia de signo, asi que no tiene TIR. Un proyecto sin desembolso o sin "
            "retorno no la define."
        )

    if not _abre_con_desembolso(flujo):
        raise ErrorIndicadores(
            "El flujo abre en positivo: es una operacion en marcha y no una inversion, de modo que "
            "no tiene TIR. Es lo mismo que responde el libro con el guion de su `IFERROR`."
        )

    no_negativas = [raiz for raiz in _raices_del_npv(flujo) if raiz >= 0.0]
    if not no_negativas:
        raise ErrorIndicadores(
            "El NPV no cruza cero en ninguna tasa no negativa entre 0 % y 1000 %. La raiz quedaria "
            "por debajo de cero y no describe una rentabilidad: lo que vale el caso lo dice el NPV."
        )
    return no_negativas[0]


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


def _abre_con_desembolso(flujo: Sequence[float]) -> bool:
    """Si el primer ejercicio con movimiento es una salida de caja."""
    return next((valor for valor in flujo if valor != 0.0), 0.0) < 0.0


def _raices_del_npv(flujo: Sequence[float]) -> list[float]:
    """Raíces del NPV dentro del intervalo buscado, de menor a mayor."""
    pasos = int((TASA_MAXIMA_BUSCADA - TASA_MINIMA_BUSCADA) / PASO_DEL_BARRIDO)
    raices: list[float] = []
    # Cada tasa se reconstruye desde su indice en vez de acumular el paso:
    # acumularlo arrastra el error de coma flotante y mueve la rejilla, con lo
    # que dos corridas de la misma serie podrian no dar el mismo numero.
    tasa = TASA_MINIMA_BUSCADA
    valor = npv(flujo, tasa)
    for i in range(1, pasos + 1):
        siguiente = min(TASA_MINIMA_BUSCADA + i * PASO_DEL_BARRIDO, TASA_MAXIMA_BUSCADA)
        valor_siguiente = npv(flujo, siguiente)
        if valor == 0.0:
            raices.append(tasa)
        elif _cambian_de_signo(valor, valor_siguiente):
            raices.append(_raiz_en(flujo, tasa, siguiente))
        tasa, valor = siguiente, valor_siguiente
    if valor == 0.0:
        raices.append(tasa)
    return raices


def _cambian_de_signo(anterior: float, siguiente: float) -> bool:
    # Se comparan los signos y no el producto: cerca del -100 % el NPV alcanza
    # magnitudes que al multiplicarse desbordan y dejan el producto en inf.
    return (anterior > 0.0) != (siguiente > 0.0)


def _raiz_en(flujo: Sequence[float], inferior: float, superior: float) -> float:
    """Reduce por bisección un intervalo que ya encierra un cambio de signo."""
    npv_inferior = npv(flujo, inferior)
    for _ in range(ITERACIONES_MAXIMAS):
        medio = (inferior + superior) / 2.0
        npv_medio = npv(flujo, medio)
        if abs(npv_medio) < TOLERANCIA_TIR or (superior - inferior) < TOLERANCIA_TIR:
            return medio
        if _cambian_de_signo(npv_inferior, npv_medio):
            superior = medio
        else:
            inferior, npv_inferior = medio, npv_medio
    return (inferior + superior) / 2.0


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
