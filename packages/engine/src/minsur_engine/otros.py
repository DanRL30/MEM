"""La hoja `Otros`: egresos, tributos pagados y capital de trabajo.

Reproduce las 93 filas de la hoja con el signo del libro. Las bandas 6 a 41 van
en signo de caja -negativas-, y el bloque de compras las devuelve a positivo
porque construye la base de las cuentas por pagar y del IGV de compras. Asi cada
total es literalmente la suma de las filas que tiene encima, que es el mismo
criterio con que `impuestos.py` expone su hoja y lo que hace contrastable el
bloque en N1.

**No recalcula lo que ya tiene modulo.** Las filas 57 a 84 las produce
`capital_trabajo.py`, la 31 y las 36 a 41 salen de `impuestos.py` y las 6 a 13
del cash cost. Este modulo es dueno de lo que no tenia ninguno: el gasto de
ventas -15 a 20-, los fletes -22 a 26-, los otros gastos -28 a 34- y la bolsa de
egresos -43 a 55-.

**La regalia se parte por el signo de la utilidad operativa.** `Otros!33` la
lleva a los otros gastos cuando `Impuestos!20` es negativa y `Otros!37` a los
tributos cuando es positiva. Es la misma cifra, `Impuestos!25`, reclasificada
por resultado del ejercicio: en perdida manda la regalia minima sobre ventas y
el libro la trata como gasto de operacion en vez de como tributo. Las dos
condiciones son estrictas, de modo que con utilidad exactamente cero no la
recoge ninguna de las dos. Se reproduce y se reporta: es la regla `080`.

**La bolsa de egresos suma once conceptos, no doce.** El libro no lleva la
gestion social en su bloque de compras y el motor la sumaba: engordaba el saldo
de cuentas por pagar y la base del IGV de compras sin que nada lo acusara. Es la
regla `081`, alineada al modelo el 04/09/2026 por decision del Project Manager,
con el mismo criterio con que se resolvio la `059`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from minsur_engine.capital_trabajo import BloqueDeIgv, SaldosDeCapitalTrabajo
from minsur_engine.horizonte import Horizonte, Serie
from minsur_engine.impuestos import BloqueDeImpuestos


class ErrorHojaOtros(ValueError):
    """Las series de la hoja `Otros` no cuadran con el horizonte."""


@dataclass(frozen=True)
class GastoDeVentas:
    """`Otros!15-20`, en signo de caja."""

    lom: Serie
    """`16`. Viene de otro libro y se pide como dato: es la regla `054`."""

    sobre_concentrado: Serie
    """`17-19` consolidadas. El libro las abre por destino; ver `calcular`."""

    total: Serie
    """`20`."""


@dataclass(frozen=True)
class Fletes:
    """`Otros!22-26`, en signo de caja."""

    lom: Serie
    """`23`. Viene de otro libro y se pide como dato: es la regla `054`."""

    sobre_concentrado: Serie
    """`24-25` consolidadas."""

    total: Serie
    """`26`."""


@dataclass(frozen=True)
class OtrosGastos:
    """`Otros!28-34`, en signo de caja."""

    donaciones: Serie
    """`29`."""

    servidumbre: Serie
    """`30`, sujeta a la bandera `Periodo con gastos` de `FC NZ!8`."""

    reguladores_y_fondo: Serie
    """`31`, que es `Impuestos!17` mas `!18` mas `!19`."""

    otros: Serie
    """`32`, tecleada en las 36 columnas: es la regla `049`."""

    regalia: Serie
    """`33`, la regalia de los ejercicios en perdida. Es la regla `080`."""

    total: Serie
    """`34`."""


@dataclass(frozen=True)
class PagoDeImpuestos:
    """`Otros!36-41`, en signo de caja.

    La fila `40`, rotulada `xxx`, es la tercera ranura reservada del libro tras
    `InputsCapex!10` y `Ventas!26`. No se reproduce -es la regla `048`- y el
    total suma sin ella, que es lo mismo que hace el libro con su cero.
    """

    regalia: Serie
    """`37`, la regalia de los ejercicios con utilidad. Es la regla `080`."""

    impuesto_especial: Serie
    """`38`."""

    impuesto_a_la_renta: Serie
    """`39`."""

    total: Serie
    """`41`, `Pago Impuestos`."""


@dataclass(frozen=True)
class BolsaDeEgresos:
    """`Otros!43-55`. Aqui el signo se invierte: es la base de compras.

    No vuelve al flujo -cada componente llega por su propia linea- y sirve para
    dos cosas: el saldo de cuentas por pagar y el IGV de compras.
    """

    opex: Serie
    gastos_administrativos: Serie
    fletes: Serie
    gasto_de_ventas: Serie
    donaciones: Serie
    otros_egresos: Serie
    servidumbre: Serie
    """`50`, entera y sin la bandera del flujo: es la regla `059`."""

    estudios: Serie
    planilla: Serie
    capex: Serie
    """`53`. Lo que separa esta base del costo operativo, y es la regla `052`."""

    exploraciones: Serie
    bolsa: Serie
    """`55`, `Bolsa Egresos`."""

    @property
    def conceptos(self) -> tuple[Serie, ...]:
        """Las once filas que la `55` suma, en el orden del libro."""
        return (
            self.opex,
            self.gastos_administrativos,
            self.fletes,
            self.gasto_de_ventas,
            self.donaciones,
            self.otros_egresos,
            self.servidumbre,
            self.estudios,
            self.planilla,
            self.capex,
            self.exploraciones,
        )


@dataclass(frozen=True)
class BloqueDeOtros:
    """La hoja `Otros` entera, banda a banda y con el signo del libro."""

    cash_cost_por_unidad: dict[str, Serie]
    """`7-12`, una fila por unidad y en signo de caja."""

    cash_cost: Serie
    """`13`, `Total Cash Cost`."""

    gasto_de_ventas: GastoDeVentas
    fletes: Fletes
    otros_gastos: OtrosGastos
    pago_de_impuestos: PagoDeImpuestos
    compras: BolsaDeEgresos
    igv: BloqueDeIgv
    """`59-66`. Llega al flujo multiplicado por cero: es la regla `014`."""

    por_cobrar: SaldosDeCapitalTrabajo
    """`72-73`."""

    por_pagar: SaldosDeCapitalTrabajo
    """`79-80`."""

    dias_por_cobrar: Serie
    """`71`."""

    dias_por_pagar: Serie
    """`78`."""

    dias_del_ano_comercial: float
    """`E70` y `E77`, fuera de la rejilla de ejercicios."""

    otras_por_cobrar: Serie
    """`82`, tecleada. Es un saldo, no una variacion: es la regla `050`."""

    otras_por_pagar: Serie
    """`83`, tecleada."""

    variacion: Serie
    """`84`, la fila que entra al flujo operativo."""

    porcentaje_de_ventas_de_exportacion: Serie
    """`87`, una semilla que el libro copia al horizonte: es la regla `047`."""

    porcentaje_de_compras_locales: Serie
    """`88`, la otra semilla."""

    produce: Serie
    """`90`, la bandera que decide en que ejercicio se liquidan las cuentas.

    Uno en los ejercicios en que alguna unidad tiene datos. El libro la rotula
    con el nombre de una unidad concreta; aqui se deriva de todas, que es el
    criterio que Finanzas fijo el 01/09/2026. Es la regla `086`.
    """

    predios: Serie
    """`93`, en signo de caja."""


def bolsa_de_egresos(
    horizonte: Horizonte,
    *,
    opex: Serie,
    gastos_administrativos: Serie,
    fletes: Serie,
    gasto_de_ventas: Serie,
    donaciones: Serie,
    otros_egresos: Serie,
    servidumbre: Serie,
    estudios: Serie,
    planilla: Serie,
    capex: Serie,
    exploraciones: Serie,
) -> BolsaDeEgresos:
    """`Otros!43-55`: todo lo que el caso desembolsa en el ejercicio.

    Once conceptos y su cierre, en el orden del libro y en positivo. Incluye el
    capital, que es lo que la separa de la suma de gastos operativos: dejarlo
    fuera mueve la variacion del capital de trabajo por encima de la tolerancia
    de N1 justo en el ano de mayor desembolso. Es la regla `052`.

    **La gestion social no esta, y hasta el 04/09/2026 si estaba.** El libro no
    la lleva en este bloque; sumarla engordaba el saldo de cuentas por pagar y
    la base del IGV de compras. Es la regla `081`.
    """
    conceptos = (
        opex,
        gastos_administrativos,
        fletes,
        gasto_de_ventas,
        donaciones,
        otros_egresos,
        servidumbre,
        estudios,
        planilla,
        capex,
        exploraciones,
    )
    return BolsaDeEgresos(
        opex=opex,
        gastos_administrativos=gastos_administrativos,
        fletes=fletes,
        gasto_de_ventas=gasto_de_ventas,
        donaciones=donaciones,
        otros_egresos=otros_egresos,
        servidumbre=servidumbre,
        estudios=estudios,
        planilla=planilla,
        capex=capex,
        exploraciones=exploraciones,
        bolsa=_sumadas(horizonte, *conceptos),
    )


def calcular(
    horizonte: Horizonte,
    *,
    cash_cost_por_unidad: Mapping[str, Serie],
    cash_cost: Serie,
    gasto_de_ventas_lom: Serie,
    gasto_de_ventas_sobre_concentrado: Serie,
    fletes_lom: Serie,
    fletes_sobre_concentrado: Serie,
    donaciones: Serie,
    servidumbre_del_flujo: Serie,
    otros_gastos: Serie,
    impuestos: BloqueDeImpuestos,
    compras: BolsaDeEgresos,
    igv: BloqueDeIgv,
    por_cobrar: SaldosDeCapitalTrabajo,
    por_pagar: SaldosDeCapitalTrabajo,
    dias_por_cobrar: Serie,
    dias_por_pagar: Serie,
    dias_del_ano_comercial: float,
    otras_por_cobrar: Serie,
    otras_por_pagar: Serie,
    variacion: Serie,
    porcentaje_de_ventas_de_exportacion: float,
    porcentaje_de_compras_locales: float,
    produce: Sequence[bool],
    predios: Serie,
) -> BloqueDeOtros:
    """Arma la hoja `Otros` a partir de lo que ya calcularon los demas bloques.

    **El gasto de ventas y los fletes van consolidados donde el libro abre una
    linea por destino.** La tarifa se aplica al concentrado alimentado del
    conjunto, y repartirla por unidad daria filas que no suman su total en
    cuanto la refineria sature. La linea `LOM` si va aparte: viene de otro libro
    y se pide como dato, que es la regla `054`.

    **Los reguladores llegan ya negados.** `Impuestos!17` y `!18` son
    `-ventas x tasa` y la `!19` viene negada de su bloque, de modo que `Otros!31`
    los copia sin cambiar el signo, igual que hace el libro con su `SUM`.
    """
    regalias = impuestos.regalias
    sin_utilidad, con_utilidad = _regalia_partida(
        regalias.utilidad_operativa, regalias.regalia_mayor
    )
    banda_de_gastos = (
        _negada(donaciones),
        _negada(servidumbre_del_flujo),
        _sumadas(horizonte, regalias.osinergmin, regalias.oefa, regalias.fondo_de_jubilacion),
        _negada(otros_gastos),
        sin_utilidad,
    )
    banda_tributaria = (
        con_utilidad,
        _negada(regalias.impuesto_especial),
        _negada(impuestos.impuesto_a_la_renta.impuesto_a_la_renta),
    )
    del_gasto_de_ventas = (_negada(gasto_de_ventas_lom), _negada(gasto_de_ventas_sobre_concentrado))
    del_flete = (_negada(fletes_lom), _negada(fletes_sobre_concentrado))
    return BloqueDeOtros(
        cash_cost_por_unidad={
            nombre: _negada(serie) for nombre, serie in cash_cost_por_unidad.items()
        },
        cash_cost=_negada(cash_cost),
        gasto_de_ventas=GastoDeVentas(
            lom=del_gasto_de_ventas[0],
            sobre_concentrado=del_gasto_de_ventas[1],
            total=_sumadas(horizonte, *del_gasto_de_ventas),
        ),
        fletes=Fletes(
            lom=del_flete[0],
            sobre_concentrado=del_flete[1],
            total=_sumadas(horizonte, *del_flete),
        ),
        otros_gastos=OtrosGastos(
            donaciones=banda_de_gastos[0],
            servidumbre=banda_de_gastos[1],
            reguladores_y_fondo=banda_de_gastos[2],
            otros=banda_de_gastos[3],
            regalia=banda_de_gastos[4],
            total=_sumadas(horizonte, *banda_de_gastos),
        ),
        pago_de_impuestos=PagoDeImpuestos(
            regalia=banda_tributaria[0],
            impuesto_especial=banda_tributaria[1],
            impuesto_a_la_renta=banda_tributaria[2],
            total=_sumadas(horizonte, *banda_tributaria),
        ),
        compras=compras,
        igv=igv,
        por_cobrar=por_cobrar,
        por_pagar=por_pagar,
        dias_por_cobrar=dias_por_cobrar,
        dias_por_pagar=dias_por_pagar,
        dias_del_ano_comercial=dias_del_ano_comercial,
        otras_por_cobrar=otras_por_cobrar,
        otras_por_pagar=otras_por_pagar,
        variacion=variacion,
        porcentaje_de_ventas_de_exportacion=_constante(
            porcentaje_de_ventas_de_exportacion, horizonte
        ),
        porcentaje_de_compras_locales=_constante(porcentaje_de_compras_locales, horizonte),
        produce=tuple(1.0 if activo else 0.0 for activo in produce),
        predios=_negada(predios),
    )


# --- Piezas -------------------------------------------------------------------


def _regalia_partida(utilidad: Serie, regalia: Serie) -> tuple[Serie, Serie]:
    """`Otros!33` y `!37`: la misma regalia, repartida por el signo del resultado.

    Las dos condiciones del libro son estrictas -`<0` y `>0`-, de modo que con
    utilidad operativa exactamente cero la regalia no cae en ninguno de los dos
    bloques y desaparece de la hoja. Se reproduce y se reporta sin corregirlo:
    es la regla `080`.
    """
    if len(utilidad) != len(regalia):
        raise ErrorHojaOtros(
            f"La utilidad operativa trae {len(utilidad)} valores y la regalia {len(regalia)}."
        )
    sin_utilidad = tuple(-r if u < 0.0 else 0.0 for u, r in zip(utilidad, regalia, strict=True))
    con_utilidad = tuple(-r if u > 0.0 else 0.0 for u, r in zip(utilidad, regalia, strict=True))
    return sin_utilidad, con_utilidad


def _sumadas(horizonte: Horizonte, *series: Serie) -> Serie:
    """Suma posicional de las filas de una banda."""
    for posicion, serie in enumerate(series):
        if len(serie) != horizonte.anos:
            raise ErrorHojaOtros(
                f"La serie en la posicion {posicion} trae {len(serie)} valores y el horizonte "
                f"tiene {horizonte.anos} anos."
            )
    return tuple(sum(serie[i] for serie in series) for i in range(horizonte.anos))


def _negada(serie: Serie) -> Serie:
    """El resto del motor lleva los egresos en positivo; la hoja, en negativo."""
    return tuple(-valor for valor in serie)


def _constante(valor: float, horizonte: Horizonte) -> Serie:
    """Una semilla que el libro copia a las 36 columnas: la regla `047`."""
    return (valor,) * horizonte.anos
