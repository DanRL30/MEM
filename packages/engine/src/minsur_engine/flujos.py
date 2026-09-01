"""Flujo económico: EBITDA ajustado, flujo operativo y flujo de inversiones.

Reproduce la estructura de la hoja `FC NZ`, que arma el flujo en tres escalones
y no en uno:

    EBITDA ajustado   ventas menos cash cost, fletes, gastos de venta,
                      administrativos, gestion social, otros gastos y
                      participacion de trabajadores
    Flujo operativo   EBITDA mas variacion de capital de trabajo, menos
                      impuestos, intereses y otros
    Flujo economico   flujo operativo mas flujo de inversiones

**La participación de trabajadores está en el EBITDA, no en los impuestos.** El
libro la resta antes de llegar al EBITDA ajustado, que es lo que el asterisco de
su etiqueta advierte. Colocarla con los tributos daría el mismo flujo económico
y un EBITDA distinto, y el contraste N2 lo detectaría.

**Los signos se declaran aquí y no se heredan.** En la hoja todo llega con el
signo puesto y las líneas se suman; un costo cargado en positivo por error pasa
desapercibido. En este módulo los ingresos y los egresos son magnitudes
positivas y el signo lo pone la fórmula, de modo que un egreso negativo es un
error detectable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from minsur_engine.horizonte import Horizonte, Serie


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

    @property
    def flujo_economico(self) -> float:
        return self.flujo_operativo + self.flujo_de_inversiones


@dataclass(frozen=True)
class FlujoDelCaso:
    """Series anuales del flujo, que es lo que consumen los indicadores."""

    anos: tuple[FlujoAnual, ...] = field(default_factory=tuple)

    @property
    def ebitda_ajustado(self) -> Serie:
        return tuple(a.ebitda_ajustado for a in self.anos)

    @property
    def flujo_operativo(self) -> Serie:
        return tuple(a.flujo_operativo for a in self.anos)

    @property
    def flujo_de_inversiones(self) -> Serie:
        return tuple(a.flujo_de_inversiones for a in self.anos)

    @property
    def flujo_economico(self) -> Serie:
        return tuple(a.flujo_economico for a in self.anos)


def flujo_del_ano(
    operativos: ComponentesOperativos, inversiones: ComponentesDeInversion
) -> FlujoAnual:
    return FlujoAnual(
        ebitda_ajustado=operativos.ebitda_ajustado,
        flujo_operativo=operativos.flujo_operativo,
        flujo_de_inversiones=inversiones.flujo_de_inversiones,
    )


def flujo_del_caso(
    horizonte: Horizonte,
    operativos: list[ComponentesOperativos],
    inversiones: list[ComponentesDeInversion],
) -> FlujoDelCaso:
    """Arma el flujo del horizonte completo."""
    if len(operativos) != horizonte.anos or len(inversiones) != horizonte.anos:
        raise ErrorFlujos(
            f"El horizonte tiene {horizonte.anos} anos y llegan {len(operativos)} de operacion y "
            f"{len(inversiones)} de inversion."
        )
    return FlujoDelCaso(
        anos=tuple(flujo_del_ano(o, i) for o, i in zip(operativos, inversiones, strict=True))
    )
