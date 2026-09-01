"""Capital de trabajo: cuentas por cobrar, por pagar y el IGV que no cuenta.

Reproduce el bloque de la hoja `Otros`, filas 57 a 84. Tiene tres
particularidades que no se deducen de la teoría y que hay que leer del libro.

**El año comercial es de 360 días.** Las cuentas por cobrar salen de
`ventas x dias / 360`, no de 365. Sobre una cartera de cuarenta días la
diferencia ronda el 1,4 % del saldo, muy por encima de la tolerancia de N1.

**El saldo se recupera en el último año de producción.** La variación anual es
la diferencia de saldos, salvo en el ejercicio en que la unidad deja de
producir: ahí se suma además el saldo entero, porque la cartera se cobra y las
deudas se pagan. El libro lo resuelve comparando la bandera de año con
producción del ejercicio con la del siguiente.

**El IGV se calcula y se anula.** El libro construye todo el bloque —IGV de
ventas, de compras, crédito acumulado y pago efectivo— y después lo multiplica
por cero al llevarlo al flujo. Coincide con lo que la hoja oculta `Inputs`
anota como «Var. IGV en WK: no se consideró». Se reproduce el comportamiento y
queda registrado como regla 014: el motor calcula el bloque y lo deja fuera del
flujo, de modo que activarlo el día que Finanzas lo pida sea cambiar una
bandera y no reconstruir el cálculo.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from minsur_engine.horizonte import Horizonte, Serie

DIAS_DEL_ANO_COMERCIAL = 360.0


class ErrorCapitalTrabajo(ValueError):
    """Los datos del capital de trabajo no son consistentes."""


@dataclass(frozen=True)
class SaldosDeCapitalTrabajo:
    """Saldos y variaciones de un ejercicio a otro."""

    saldos: Serie
    variaciones: Serie


def saldo_por_dias(base: Serie, dias: Serie) -> Serie:
    """Saldo de una cuenta a partir de su base anual y sus días de rotación."""
    if len(base) != len(dias):
        raise ErrorCapitalTrabajo(f"La base trae {len(base)} valores y los dias {len(dias)}.")
    for i, d in enumerate(dias):
        if d < 0.0:
            raise ErrorCapitalTrabajo(f"Dias negativos en la posicion {i}: {d}.")
    return tuple(b * d / DIAS_DEL_ANO_COMERCIAL for b, d in zip(base, dias, strict=True))


def variacion_de_cuenta(saldos: Serie, produce: Sequence[bool], *, es_por_cobrar: bool) -> Serie:
    """Variación anual del saldo, con recuperación en el último año productivo.

    Las cuentas por cobrar entran al flujo con signo contrario a las de pagar:
    un aumento de la cartera consume caja y un aumento de la deuda la libera.
    """
    if len(saldos) != len(produce):
        raise ErrorCapitalTrabajo(
            f"Los saldos traen {len(saldos)} valores y la bandera de produccion {len(produce)}."
        )
    signo = -1.0 if es_por_cobrar else 1.0
    variaciones: list[float] = []
    for i, saldo in enumerate(saldos):
        anterior = saldos[i - 1] if i > 0 else 0.0
        siguiente_produce = produce[i + 1] if i + 1 < len(produce) else False
        variacion = signo * (saldo - anterior)
        if produce[i] and not siguiente_produce:
            # Ultimo ejercicio con produccion: la cuenta se liquida entera.
            variacion += signo * -saldo
        variaciones.append(variacion)
    return tuple(variaciones)


def igv(base_local: Serie, tasa: float) -> Serie:
    """IGV de una base de ventas o compras locales."""
    if not 0.0 <= tasa < 1.0:
        raise ErrorCapitalTrabajo(f"Tasa de IGV fuera de rango: {tasa}.")
    return tuple(b * tasa for b in base_local)


def credito_y_pago_de_igv(igv_ventas: Serie, igv_compras: Serie) -> tuple[Serie, Serie]:
    """Crédito fiscal acumulado y pago efectivo de IGV, año a año.

    Cuando el IGV de compras supera al de ventas, la diferencia se acumula como
    crédito y no se paga; cuando hay crédito acumulado suficiente, se consume
    antes de pagar.
    """
    if len(igv_ventas) != len(igv_compras):
        raise ErrorCapitalTrabajo("Las series de IGV de ventas y compras no coinciden en largo.")
    credito: list[float] = []
    pagos: list[float] = []
    acumulado = 0.0
    for venta, compra in zip(igv_ventas, igv_compras, strict=True):
        diferencia = venta - compra
        if diferencia < 0.0:
            acumulado -= diferencia
            pago = diferencia
        elif acumulado - diferencia > 0.0:
            acumulado -= diferencia
            pago = 0.0
        else:
            pago = acumulado - diferencia
            acumulado = 0.0
        credito.append(acumulado)
        pagos.append(pago)
    return tuple(credito), tuple(pagos)


def variacion_de_capital_trabajo(
    horizonte: Horizonte,
    *,
    por_cobrar: Serie,
    por_pagar: Serie,
    otros: Serie | None = None,
    variacion_igv: Serie | None = None,
    cuentas_activas: bool = True,
) -> Serie:
    """Variación del capital de trabajo que entra al flujo operativo.

    `cuentas_activas` reproduce el interruptor `Control!$G$21` del libro, que
    apaga las cuentas comerciales dejando el resto del bloque intacto.

    `variacion_igv` es cero en el modelo vigente: el libro la calcula y la
    multiplica por cero (regla 014). Se acepta como parámetro para que
    encenderla sea un cambio de dato y no de código.
    """
    ceros = horizonte.ceros()
    otros = otros if otros is not None else ceros
    variacion_igv = variacion_igv if variacion_igv is not None else ceros
    for nombre, serie in (
        ("por cobrar", por_cobrar),
        ("por pagar", por_pagar),
        ("otros", otros),
        ("IGV", variacion_igv),
    ):
        if len(serie) != horizonte.anos:
            raise ErrorCapitalTrabajo(
                f"La serie {nombre!r} trae {len(serie)} valores y el horizonte tiene "
                f"{horizonte.anos} anos."
            )

    factor = 1.0 if cuentas_activas else 0.0
    return tuple(
        variacion_igv[i] + (por_cobrar[i] + por_pagar[i] + otros[i]) * factor
        for i in range(horizonte.anos)
    )
