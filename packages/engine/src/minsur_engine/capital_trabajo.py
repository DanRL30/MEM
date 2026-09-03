"""Capital de trabajo: cuentas por cobrar, por pagar y el IGV que no cuenta.

Reproduce el bloque de la hoja `Otros`, filas 57 a 84. Tiene tres
particularidades que no se deducen de la teoría y que hay que leer del libro.

**El año comercial es de 360 días.** Las cuentas por cobrar salen de
`ventas x dias / 360`, no de 365. Sobre una cartera de cuarenta días la
diferencia ronda el 1,4 % del saldo, muy por encima de la tolerancia de N1.

**El saldo se recupera en el último año de producción, y en un año sin
producción la cuenta no se mueve.** El libro compara la bandera de año con
producción del ejercicio con la del siguiente y **multiplica el resultado
entero por la bandera del ejercicio**. De ahí salen tres comportamientos: un
año productivo seguido de otro mueve la diferencia de saldos; el último de una
racha suma además el saldo entero, porque la cartera se cobra y las deudas se
pagan; y un año sin producción no mueve nada. Ese tercer caso es el que impide
que una parada intermedia recupere el saldo dos veces, y es la regla 053.

**El IGV se calcula y se anula.** El libro construye todo el bloque —IGV de
ventas, de compras, crédito acumulado y pago efectivo— y después lo multiplica
por cero al llevarlo al flujo. Coincide con lo que la hoja oculta `Inputs`
anota como «Var. IGV en WK: no se consideró». Se reproduce tal cual, y el cero
es `PESO_DEL_IGV_EN_EL_FLUJO`: el bloque se calcula, se informa y llega al
flujo multiplicado por cero, que es lo que hace el modelo. Es la regla 014.

**La base de las cuentas por pagar es la bolsa de egresos, no el costo
operativo.** El libro suma en su fila de adiciones el opex, los gastos
administrativos, los fletes, el gasto de ventas, las donaciones, la
servidumbre, los estudios, la planilla, el **capex**, las exploraciones y los
otros egresos. Con el saldo en `base x dias / 360`, dejar fuera el capital del
primer ejercicio mueve la variación muy por encima de la tolerancia de N1, y
justo en el año de mayor desembolso. Es la regla 052.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from minsur_engine.horizonte import Horizonte, Serie

DIAS_DEL_ANO_COMERCIAL = 360.0
"""El ano comercial del libro, y el valor por defecto cuando el caso calla."""

PESO_DEL_IGV_EN_EL_FLUJO = 0.0
"""Factor con que la variación de IGV entra al flujo, `Otros!66`.

El libro escribe `-(credito - credito anterior) x 0`. El cero está aquí y no
disperso por el cálculo: el día que Finanzas confirme que el IGV cuenta, es
esta línea la que cambia. Es la regla 014, todavía sin confirmar.
"""


class ErrorCapitalTrabajo(ValueError):
    """Los datos del capital de trabajo no son consistentes."""


@dataclass(frozen=True)
class SaldosDeCapitalTrabajo:
    """Saldos y variaciones de un ejercicio a otro."""

    saldos: Serie
    variaciones: Serie


def saldo_por_dias(
    base: Serie, dias: Serie, *, dias_del_ano: float = DIAS_DEL_ANO_COMERCIAL
) -> Serie:
    """Saldo de una cuenta a partir de su base anual y sus días de rotación.

    El año comercial llega como dato y no escrito en la fórmula: el libro divide
    entre 360 y quien trabaje sobre 365 no tendría que tocar el motor para
    decirlo. Sin declarar, son los 360 del libro.
    """
    if len(base) != len(dias):
        raise ErrorCapitalTrabajo(f"La base trae {len(base)} valores y los dias {len(dias)}.")
    if dias_del_ano <= 0.0:
        raise ErrorCapitalTrabajo(
            f"El ano comercial vale {dias_del_ano} y se espera un numero de dias positivo."
        )
    for i, d in enumerate(dias):
        if d < 0.0:
            raise ErrorCapitalTrabajo(f"Dias negativos en la posicion {i}: {d}.")
    return tuple(b * d / dias_del_ano for b, d in zip(base, dias, strict=True))


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
        if not produce[i]:
            # El libro multiplica la fila entera por la bandera del ejercicio:
            # un ano sin produccion no mueve la cuenta. Sin esto, la parada
            # recupera el saldo una segunda vez y el ciclo no cierra en cero.
            variaciones.append(0.0)
            continue
        anterior = saldos[i - 1] if i > 0 else 0.0
        siguiente_produce = produce[i + 1] if i + 1 < len(produce) else False
        variacion = signo * (saldo - anterior)
        if not siguiente_produce:
            # Ultimo ejercicio de la racha: la cuenta se liquida entera.
            variacion += signo * -saldo
        variaciones.append(variacion)
    return tuple(variaciones)


def cuenta(
    base: Serie,
    dias: Serie,
    produce: Sequence[bool],
    *,
    es_por_cobrar: bool,
    dias_del_ano: float = DIAS_DEL_ANO_COMERCIAL,
) -> SaldosDeCapitalTrabajo:
    """Saldo y variación de una cuenta comercial, `Otros!72-73` y `!79-80`.

    Devuelve las dos filas y no solo la variación: el saldo es una línea propia
    del libro, y sin él una discrepancia no se puede atribuir al saldo o al
    delta.
    """
    saldos = saldo_por_dias(base, dias, dias_del_ano=dias_del_ano)
    return SaldosDeCapitalTrabajo(
        saldos=saldos,
        variaciones=variacion_de_cuenta(saldos, produce, es_por_cobrar=es_por_cobrar),
    )


@dataclass(frozen=True)
class BloqueDeIgv:
    """El bloque de IGV de la hoja `Otros`, filas 59 a 66."""

    ventas_gravadas: Serie
    compras_gravadas: Serie
    igv_de_ventas: Serie
    igv_de_compras: Serie
    credito_acumulado: Serie
    pago_efectivo: Serie

    @property
    def variacion_para_el_flujo(self) -> Serie:
        """`Otros!66`: la variación del crédito, multiplicada por cero.

        La aritmética se hace entera y el resultado es cero por el peso, no
        porque el término se haya dejado fuera. Es la diferencia entre
        reproducir el libro y omitir el bloque.
        """
        variaciones: list[float] = []
        for i, acumulado in enumerate(self.credito_acumulado):
            anterior = self.credito_acumulado[i - 1] if i > 0 else 0.0
            variaciones.append(-(acumulado - anterior) * PESO_DEL_IGV_EN_EL_FLUJO)
        return tuple(variaciones)


def bloque_de_igv(
    horizonte: Horizonte,
    *,
    ventas: Serie,
    bolsa_de_egresos: Serie,
    tasa: float,
    porcentaje_de_ventas: float,
    porcentaje_de_compras: float,
) -> BloqueDeIgv:
    """Rehace las filas 59 a 66 de la hoja `Otros`.

    La base de ventas es la venta del año por su porcentaje y la de compras, la
    bolsa de egresos por el suyo. El libro rotula la primera `IGV Ventas
    Locales` y la calcula sobre el porcentaje de exportación, que es la
    discrepancia registrada como regla 051: se reproduce el cálculo y se reporta
    el rótulo.
    """
    if len(ventas) != horizonte.anos or len(bolsa_de_egresos) != horizonte.anos:
        raise ErrorCapitalTrabajo(
            f"Las bases del IGV traen {len(ventas)} y {len(bolsa_de_egresos)} valores y el "
            f"horizonte tiene {horizonte.anos} anos."
        )
    gravadas_ventas = tuple(v * porcentaje_de_ventas for v in ventas)
    gravadas_compras = tuple(c * porcentaje_de_compras for c in bolsa_de_egresos)
    de_ventas = igv(gravadas_ventas, tasa)
    de_compras = igv(gravadas_compras, tasa)
    credito, pagos = credito_y_pago_de_igv(de_ventas, de_compras)
    return BloqueDeIgv(
        ventas_gravadas=gravadas_ventas,
        compras_gravadas=gravadas_compras,
        igv_de_ventas=de_ventas,
        igv_de_compras=de_compras,
        credito_acumulado=credito,
        pago_efectivo=pagos,
    )


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
    otras_por_cobrar: Serie | None = None,
    otras_por_pagar: Serie | None = None,
    variacion_igv: Serie | None = None,
    cuentas_activas: bool = True,
) -> Serie:
    """Variación del capital de trabajo que entra al flujo operativo, `Otros!84`.

    `cuentas_activas` reproduce el interruptor `Control!$G$21` del libro, que
    apaga las cuentas comerciales dejando el IGV intacto: el interruptor va
    dentro del paréntesis y la variación de IGV, fuera.

    **Las dos cuentas otras son saldos y se suman junto a dos variaciones.** Es
    lo que escribe el libro y no se corrige: queda registrado como regla 050.
    Van separadas y no fundidas en un solo término porque el libro las lleva en
    dos filas, y sumarlas impediría atribuir una diferencia a una de las dos.
    """
    ceros = horizonte.ceros()
    otras_por_cobrar = otras_por_cobrar if otras_por_cobrar is not None else ceros
    otras_por_pagar = otras_por_pagar if otras_por_pagar is not None else ceros
    variacion_igv = variacion_igv if variacion_igv is not None else ceros
    for nombre, serie in (
        ("por cobrar", por_cobrar),
        ("por pagar", por_pagar),
        ("otras por cobrar", otras_por_cobrar),
        ("otras por pagar", otras_por_pagar),
        ("IGV", variacion_igv),
    ):
        if len(serie) != horizonte.anos:
            raise ErrorCapitalTrabajo(
                f"La serie {nombre!r} trae {len(serie)} valores y el horizonte tiene "
                f"{horizonte.anos} anos."
            )

    factor = 1.0 if cuentas_activas else 0.0
    return tuple(
        variacion_igv[i]
        + (por_cobrar[i] + por_pagar[i] + otras_por_cobrar[i] + otras_por_pagar[i]) * factor
        for i in range(horizonte.anos)
    )
