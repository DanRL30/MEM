"""Flujo económico: EBITDA ajustado, flujo operativo y flujo de inversiones.

Reproduce la hoja `FC NZ`, que arma el flujo en tres escalones y no en uno:

    EBITDA ajustado   ventas menos cash cost, fletes, gastos de venta,
                      administrativos, gestion social, otros gastos y
                      participacion de trabajadores
    Flujo operativo   EBITDA mas variacion de capital de trabajo, menos
                      impuestos, intereses y otros
    Flujo economico   flujo operativo mas flujo de inversiones, **devolviendo
                      los intereses**

**La participación de trabajadores está en el EBITDA, no en los impuestos.** El
libro la resta antes de llegar al EBITDA ajustado, que es lo que el asterisco de
su etiqueta advierte. Colocarla con los tributos daría el mismo flujo económico
y un EBITDA distinto, y el contraste N2 lo detectaría.

**El flujo económico es anterior al financiamiento.** `FC NZ!35` es
`27 + 33 - 25`: el flujo operativo ya descontó los intereses y esta línea los
devuelve, de modo que el resultado no depende de cómo se financie el proyecto.
Hasta el 04/09/2026 el motor los dejaba dentro, y no se veía porque los intereses
valen cero en todos los casos del arnés. Es la regla `095`.

**Los signos se declaran aquí y no se heredan.** En la hoja todo llega con el
signo puesto y las líneas se suman; un costo cargado en positivo por error pasa
desapercibido. En este módulo los ingresos y los egresos son magnitudes
positivas y el signo lo pone la fórmula, de modo que un egreso negativo es un
error detectable. El bloque que se publica sí lleva el signo del libro: es lo
que hace que cada total sea literalmente la suma de las filas que tiene encima.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from minsur_engine.horizonte import Horizonte, Serie
from minsur_engine.indicadores import factores_de_descuento


class ErrorFlujos(ValueError):
    """Los componentes del flujo no son consistentes."""


@dataclass(frozen=True)
class ComponentesOperativos:
    """Líneas del flujo operativo de un año. Todas en magnitud positiva."""

    ventas: float
    cash_cost: float
    fletes: float = 0.0
    gasto_de_ventas: float = 0.0
    gasto_administrativo: float = 0.0
    gestion_social: float = 0.0
    otros_gastos: float = 0.0
    participacion_trabajadores: float = 0.0
    impuestos: float = 0.0
    intereses: float = 0.0
    otros: float = 0.0
    variacion_capital_trabajo: float = 0.0
    """Única línea que puede ser negativa: es una variación, no una magnitud."""

    def __post_init__(self) -> None:
        for nombre in (
            "ventas",
            "cash_cost",
            "fletes",
            "gasto_de_ventas",
            "gasto_administrativo",
            "gestion_social",
            "otros_gastos",
            "participacion_trabajadores",
            "impuestos",
            "intereses",
            "otros",
        ):
            valor: float = getattr(self, nombre)
            if valor < 0.0:
                raise ErrorFlujos(
                    f"{nombre} vale {valor}. Las lineas del flujo se declaran en magnitud "
                    "positiva y el signo lo pone la formula; solo la variacion de capital de "
                    "trabajo admite negativos."
                )

    @property
    def ebitda_ajustado(self) -> float:
        """EBITDA después de participación de trabajadores, como en el libro."""
        return self.ventas - (
            self.cash_cost
            + self.fletes
            + self.gasto_de_ventas
            + self.gasto_administrativo
            + self.gestion_social
            + self.otros_gastos
            + self.participacion_trabajadores
        )

    @property
    def flujo_operativo(self) -> float:
        return (
            self.ebitda_ajustado
            + self.variacion_capital_trabajo
            - (self.impuestos + self.intereses + self.otros)
        )


@dataclass(frozen=True)
class ComponentesDeInversion:
    """Líneas del flujo de inversiones de un año, en magnitud positiva."""

    capex_inicial: float = 0.0
    capex_sostenimiento: float = 0.0
    estudios: float = 0.0
    exploraciones: float = 0.0
    predios: float = 0.0
    otros: float = 0.0
    """Sin fila propia en el libro, cuyo total suma cinco. Se declara y suma."""

    @property
    def flujo_de_inversiones(self) -> float:
        """Siempre negativo o cero: una inversión sale de caja."""
        return -(
            self.capex_inicial
            + self.capex_sostenimiento
            + self.estudios
            + self.exploraciones
            + self.predios
            + self.otros
        )


@dataclass(frozen=True)
class FlujoAnual:
    ebitda_ajustado: float
    flujo_operativo: float
    flujo_de_inversiones: float
    intereses: float = 0.0
    """Se guarda porque el flujo económico los devuelve: `FC NZ!35`."""

    @property
    def flujo_economico(self) -> float:
        return self.flujo_operativo + self.flujo_de_inversiones + self.intereses


@dataclass(frozen=True)
class Banderas:
    """`FC NZ!6`, `!8` y `!10`, las banderas de periodo del caso.

    **Las filas `7` y `9` no se reproducen.** `Periodo pre-operativo` son treinta
    y seis ceros tecleados que no lee ninguna celda del libro, y `Ano cierre` se
    calcula comparando la depreciacion contra un umbral incrustado en su propia
    formula y tampoco lo lee nadie. Son dos filas muertas dentro de la hoja del
    caso, y es la regla `092`.
    """

    periodo_proyecto: Serie
    """`6`. El ejercicio dentro del horizonte, contado desde cero."""

    periodo_con_gastos: Serie
    """`8`. Uno cuando hay costo operativo. La hoja `Otros` la usa para sujetar
    la servidumbre, que es lo unico que la consume fuera de esta hoja."""

    periodo_operativo: Serie
    """`10`. Uno cuando alguna unidad produce."""


@dataclass(frozen=True)
class FlujoDelCaso:
    """La hoja `FC NZ` entera, con el signo del libro.

    Hasta el 04/09/2026 de sus veinte lineas salian cuatro: las tres del
    `FlujoAnual` y el economico derivado. Las diecisiete de entrada se componian
    dentro de `corrida.calcular` y morian ahi, de modo que una discrepancia en el
    flujo no se podia atribuir a la fila que la causaba.
    """

    anos: tuple[FlujoAnual, ...] = field(default_factory=tuple)
    banderas: Banderas | None = None

    ventas: Serie = ()
    cash_cost: Serie = ()
    participaciones: Serie = ()
    fletes: Serie = ()
    gasto_de_ventas: Serie = ()
    gasto_administrativo: Serie = ()
    gestion_social: Serie = ()
    otros_gastos: Serie = ()
    """`14:21`, los ocho conceptos que cierran en el EBITDA ajustado."""

    variacion_capital_trabajo: Serie = ()
    impuestos: Serie = ()
    intereses: Serie = ()
    otros: Serie = ()
    """`23:26`, lo que va del EBITDA al flujo operativo."""

    capex_inicial: Serie = ()
    capex_sostenimiento: Serie = ()
    estudios: Serie = ()
    exploraciones: Serie = ()
    predios: Serie = ()
    """`28:32`, las cinco lineas de inversion."""

    ano: Serie = ()
    factor_de_descuento: Serie = ()
    flujo_descontado: Serie = ()
    """`38:40`. El libro teclea un cero en el factor del primer ejercicio y suma
    el NPV desde el segundo; el motor descuenta desde el primero. Es la regla
    `062`, consultada a Finanzas y sin respuesta."""

    @property
    def ebitda_ajustado(self) -> Serie:
        """`22`."""
        return tuple(a.ebitda_ajustado for a in self.anos)

    @property
    def flujo_operativo(self) -> Serie:
        """`27`."""
        return tuple(a.flujo_operativo for a in self.anos)

    @property
    def flujo_de_inversiones(self) -> Serie:
        """`33`."""
        return tuple(a.flujo_de_inversiones for a in self.anos)

    @property
    def flujo_economico(self) -> Serie:
        """`35`."""
        return tuple(a.flujo_economico for a in self.anos)

    @property
    def sumandos_del_ebitda(self) -> tuple[Serie, ...]:
        """Las ocho filas `14:21` que la `22` suma, con el signo del libro."""
        return (
            self.ventas,
            self.cash_cost,
            self.participaciones,
            self.fletes,
            self.gasto_de_ventas,
            self.gasto_administrativo,
            self.gestion_social,
            self.otros_gastos,
        )

    @property
    def sumandos_del_operativo(self) -> tuple[Serie, ...]:
        """Las cinco filas `22:26` que la `27` suma."""
        return (
            self.ebitda_ajustado,
            self.variacion_capital_trabajo,
            self.impuestos,
            self.intereses,
            self.otros,
        )

    @property
    def sumandos_de_inversiones(self) -> tuple[Serie, ...]:
        """Las cinco filas `28:32` que la `33` suma."""
        return (
            self.capex_inicial,
            self.capex_sostenimiento,
            self.estudios,
            self.exploraciones,
            self.predios,
        )


def flujo_del_ano(
    operativos: ComponentesOperativos, inversiones: ComponentesDeInversion
) -> FlujoAnual:
    return FlujoAnual(
        ebitda_ajustado=operativos.ebitda_ajustado,
        flujo_operativo=operativos.flujo_operativo,
        flujo_de_inversiones=inversiones.flujo_de_inversiones,
        intereses=operativos.intereses,
    )


def flujo_del_caso(
    horizonte: Horizonte,
    operativos: list[ComponentesOperativos],
    inversiones: list[ComponentesDeInversion],
    *,
    tasa_descuento: float = 0.0,
    produce: Sequence[bool] = (),
) -> FlujoDelCaso:
    """Arma el flujo del horizonte completo, fila a fila y con el signo del libro.

    `tasa_descuento` y `produce` tienen valor por defecto para que quien solo
    quiera las cuatro lineas del flujo -el contraste contra el modelo, que
    alimenta esta funcion con las filas del propio libro- no tenga que
    inventarlos. Sin tasa, el factor de descuento sale en uno.
    """
    if len(operativos) != horizonte.anos or len(inversiones) != horizonte.anos:
        raise ErrorFlujos(
            f"El horizonte tiene {horizonte.anos} anos y llegan {len(operativos)} de operacion y "
            f"{len(inversiones)} de inversion."
        )
    if produce and len(produce) != horizonte.anos:
        raise ErrorFlujos(
            f"La bandera de produccion trae {len(produce)} valores y el horizonte tiene "
            f"{horizonte.anos} anos."
        )
    anos = tuple(flujo_del_ano(o, i) for o, i in zip(operativos, inversiones, strict=True))
    factores = factores_de_descuento(tasa_descuento, horizonte.anos)
    economico = tuple(a.flujo_economico for a in anos)
    return FlujoDelCaso(
        anos=anos,
        banderas=Banderas(
            periodo_proyecto=tuple(float(t) for t in range(horizonte.anos)),
            periodo_con_gastos=tuple(1.0 if o.cash_cost > 0.0 else 0.0 for o in operativos),
            periodo_operativo=tuple(
                1.0 if produce and produce[i] else 0.0 for i in range(horizonte.anos)
            ),
        ),
        ventas=_linea(operativos, "ventas", ingreso=True),
        cash_cost=_linea(operativos, "cash_cost"),
        participaciones=_linea(operativos, "participacion_trabajadores"),
        fletes=_linea(operativos, "fletes"),
        gasto_de_ventas=_linea(operativos, "gasto_de_ventas"),
        gasto_administrativo=_linea(operativos, "gasto_administrativo"),
        gestion_social=_linea(operativos, "gestion_social"),
        otros_gastos=_linea(operativos, "otros_gastos"),
        variacion_capital_trabajo=_linea(operativos, "variacion_capital_trabajo", ingreso=True),
        impuestos=_linea(operativos, "impuestos"),
        intereses=_linea(operativos, "intereses"),
        otros=_linea(operativos, "otros"),
        capex_inicial=_linea(inversiones, "capex_inicial"),
        capex_sostenimiento=_linea(inversiones, "capex_sostenimiento"),
        estudios=_linea(inversiones, "estudios"),
        exploraciones=_linea(inversiones, "exploraciones"),
        predios=_linea(inversiones, "predios"),
        ano=tuple(float(t) for t in range(horizonte.anos)),
        factor_de_descuento=factores,
        flujo_descontado=tuple(f * d for f, d in zip(economico, factores, strict=True)),
    )


def _linea(componentes: Sequence[object], campo: str, *, ingreso: bool = False) -> Serie:
    """Transpone un campo de los componentes a serie, con el signo del libro.

    Los componentes llevan magnitudes positivas y la hoja lleva los egresos en
    negativo. La variacion de capital de trabajo pasa como viene: ya es una
    variacion con signo.
    """
    signo = 1.0 if ingreso else -1.0
    valores: list[float] = []
    for componente in componentes:
        valor: float = getattr(componente, campo)
        valores.append(signo * valor)
    return tuple(valores)
