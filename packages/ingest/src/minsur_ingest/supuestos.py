"""Las dos plantillas de supuestos: el comité de precios y todo lo demás.

Son **dos archivos separados y con dueños distintos**, y esa separación no es de
comodidad. El comité de precios es dato maestro: lo aprueba y lo sube Finanzas, y
quien modela solo elige qué comité usa para su análisis. El resto de los
supuestos son del caso. Mezclarlos en un archivo dejaría a cualquiera cambiando
un precio aprobado sin que nadie lo advierta.

La estructura sigue a la hoja `Supuestos` del libro, con sus etiquetas y sus
unidades de medida. Tres diferencias, todas deliberadas:

- **El comité de precios no tiene ocho ranuras.** El libro reserva ocho juegos y
  elige uno con un selector; la plataforma versiona, que es lo mismo sin el
  límite ni las ranuras rotuladas `xxx`.
- **La recuperación del complejo va por unidad**, no por los grupos `SR + B2` y
  `NZ + SRP` del libro. Es la regla de oro del complejo.
- **La depreciación va por unidad**, que es lo que pide la desviación `D-04`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from minsur_engine.horizonte import Horizonte, Serie
from minsur_ingest.incidencias import Incidencia
from minsur_ingest.sinonimos import normalizar

SECCION = None


@dataclass(frozen=True)
class FilaDeSupuesto:
    """Una fila de una plantilla de supuestos."""

    etiqueta: str
    medida: str | None
    """`None` marca una fila de sección, que no lleva datos."""

    campo: str = ""
    calculada: bool = False
    """Si el sistema la rehace para corroborar lo que el usuario cargó."""


def _es_seccion(fila: FilaDeSupuesto) -> bool:
    return fila.medida is SECCION


# --- Comité de precios: dato maestro que sube Finanzas -------------------------

FILAS_DE_PRECIOS = (
    FilaDeSupuesto("Precios", SECCION),
    FilaDeSupuesto("Sn", "$/t", "sn"),
    FilaDeSupuesto("Cu", "$/t", "cu"),
    # La plata se cotiza y se paga por onza troy, no por tonelada.
    FilaDeSupuesto("Ag", "$/oz", "ag"),
)

# --- Supuestos del caso, comunes a todas las unidades -------------------------

FILAS_DE_SUPUESTOS = (
    FilaDeSupuesto("Terminos Comerciales", SECCION),
    FilaDeSupuesto("Premio Sn", "$/t", "premio_sn"),
    FilaDeSupuesto("Pagable sobre concentrado de Sn", "%", "pagable_sn"),
    FilaDeSupuesto("Merma", "%", "merma"),
    FilaDeSupuesto("Deduccion Minima Cu", "%", "deduccion_minima_cu"),
    FilaDeSupuesto("Deduccion Minima Ag", "g/t", "deduccion_minima_ag"),
    FilaDeSupuesto("Factor Metal Pagable Cu", "%", "factor_pagable_cu"),
    FilaDeSupuesto("Factor Metal Pagable Ag", "%", "factor_pagable_ag"),
    # El libro las deriva de la ley del concentrado, la deduccion minima y el
    # factor pagable. Se piden igual y se corroboran.
    FilaDeSupuesto("Ley Pagable Cu", "%", "ley_pagable_cu", calculada=True),
    FilaDeSupuesto("Ley Pagable Ag", "g/t", "ley_pagable_ag", calculada=True),
    FilaDeSupuesto("Maquila", "$/t", "maquila"),
    FilaDeSupuesto("Refinacion Cu", "$/t", "refinacion_cu"),
    FilaDeSupuesto("Refinacion Ag", "$/t", "refinacion_ag", calculada=True),
    FilaDeSupuesto("Penalidades Cu", "$/t", "penalidades_cu"),
    FilaDeSupuesto("Penalidades Ag", "$/t", "penalidades_ag"),
    FilaDeSupuesto("Otros Supuestos", SECCION),
    FilaDeSupuesto("Costo de Transporte de Concentrado", "$/t conc", "transporte"),
    FilaDeSupuesto("Costo de Fundicion", "$/tmf", "costo_de_fundicion"),
    FilaDeSupuesto("Gasto de Ventas Sn Refinado", "$/tmf", "gasto_de_ventas_sn_refinado"),
    FilaDeSupuesto("Gasto de Ventas Conc. Sn", "$/t conc", "gasto_de_ventas_conc_sn"),
    FilaDeSupuesto("Gasto de Ventas Conc. Cu", "$/t conc", "gasto_de_ventas_conc_cu"),
    FilaDeSupuesto("Capacidad Maxima del Complejo", "t", "capacidad_del_complejo"),
    FilaDeSupuesto("Gasto Exploraciones", "$", "exploraciones"),
    FilaDeSupuesto("Gastos Financieros Netos", "$", "gastos_financieros"),
    FilaDeSupuesto("Otros Flujo Operativo", "$", "otros_flujo_operativo"),
    FilaDeSupuesto("Planilla sobre Cash Cost", "%", "planilla_sobre_cash_cost"),
    FilaDeSupuesto("Rango de Ajuste de Capex", "%", "ajuste_de_capex"),
    FilaDeSupuesto("Reguladores", SECCION),
    # El libro los lleva ano a ano y decrecientes, no como una tasa fija.
    FilaDeSupuesto("Contribucion a OEFA", "%", "oefa"),
    FilaDeSupuesto("Contribucion a OSINERGMIN", "%", "osinergmin"),
)

# --- Supuestos de cada unidad -------------------------------------------------

FILAS_POR_UNIDAD = (
    FilaDeSupuesto("Depreciacion", SECCION),
    FilaDeSupuesto("Depreciacion Tributaria", "k$", "depreciacion_tributaria"),
    FilaDeSupuesto("Depreciacion Financiera", "k$", "depreciacion_financiera"),
    FilaDeSupuesto("Complejo", SECCION),
    FilaDeSupuesto("Recuperacion de Sn en el complejo", "%", "recuperacion_en_el_complejo"),
)

CON_DATO_DE_PRECIOS = tuple(f for f in FILAS_DE_PRECIOS if not _es_seccion(f))
CON_DATO_DE_SUPUESTOS = tuple(f for f in FILAS_DE_SUPUESTOS if not _es_seccion(f))
CON_DATO_POR_UNIDAD = tuple(f for f in FILAS_POR_UNIDAD if not _es_seccion(f))


@dataclass(frozen=True)
class ComiteDePrecios:
    """Un juego de precios aprobado, con su identificación.

    Es dato maestro y por eso lleva nombre y fecha: una corrida registra qué
    comité usó, no "el vigente". Publicar uno nuevo no reescribe evaluaciones
    pasadas.
    """

    nombre: str
    aprobado_el: str
    horizonte: Horizonte
    sn: Serie = ()
    cu: Serie = ()
    ag: Serie = ()


@dataclass(frozen=True)
class SupuestosDelCaso:
    """Lo que la plantilla de supuestos aporta, sin interpretar todavía."""

    comunes: dict[str, Serie] = field(default_factory=dict)
    por_unidad: dict[str, dict[str, Serie]] = field(default_factory=dict)
    """Por nombre de pestaña, en el orden en que llegaron."""


def armar_filas(
    definicion: Sequence[FilaDeSupuesto],
    filas: Sequence[tuple[str, Serie]],
    incidencias: list[Incidencia],
    *,
    hoja: str,
) -> dict[str, Serie]:
    """Recorre en paralelo la estructura esperada y la de la hoja.

    Una etiqueta que no es la que toca detiene la lectura de esa pestaña y se
    reporta: si la secuencia se rompe, seguir leyendo asignaría cada serie al
    concepto de al lado y el caso saldría plausible y equivocado.
    """
    campos: dict[str, Serie] = {}
    if not filas:
        return campos
    for esperada, (etiqueta, serie) in zip(definicion, filas, strict=False):
        if normalizar(etiqueta) != normalizar(esperada.etiqueta):
            incidencias.append(
                Incidencia(
                    hoja,
                    etiqueta,
                    f"se esperaba {esperada.etiqueta!r} y hay {etiqueta!r}. La plantilla de "
                    "supuestos tiene una estructura fija y esta pestana se aparta de ella.",
                )
            )
            return campos
        campos[esperada.campo] = serie
    if len(filas) != len(definicion):
        incidencias.append(
            Incidencia(
                hoja,
                "-",
                f"la pestana trae {len(filas)} filas de datos y la estructura estandar tiene "
                f"{len(definicion)}.",
            )
        )
    return campos
