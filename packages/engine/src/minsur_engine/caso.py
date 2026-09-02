"""El caso: todo lo que hace falta para evaluar un proyecto, y nada más.

Es la entrada del motor. Reúne las estructuras que cada bloque definió por su
cuenta —el capital de `capex`, los costos de `cash_cost`, los metales de
`ventas`, las escalas de `tributos`— y añade lo que ninguno necesitaba solo: el
horizonte común, las unidades productivas y los datos del caso.

**Un caso no nombra proyectos.** Declara unidades productivas con su tipo y sus
series. Que una se llame Nazareth o Proyecto X no cambia una línea del cálculo,
y esa es exactamente la propiedad que el modelo de referencia no tiene: donde el
libro precablea 48 casos en 1 870 columnas, aquí hay una lista.

**Los datos maestros no viven en el caso.** Parámetros corporativos, tasas de
depreciación y escalas tributarias los mantiene MINSUR (`R-32`) y una corrida
registra qué versión usó. Van juntos en `DatosMaestros` para que esa versión sea
una sola cosa y no siete campos sueltos que puedan mezclarse.

Ver [modelo-estandar.md](../../../../docs/modelo-economico/modelo-estandar.md).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from minsur_engine.capex import CapitalDeUnidad
from minsur_engine.depreciacion import TasasDeDepreciacion
from minsur_engine.horizonte import Horizonte, Serie
from minsur_engine.parametros import ParametrosCorporativos
from minsur_engine.tributos import EscalaProgresiva

TIPOS_DE_UNIDAD = ("mina", "fundicion")
"""Solo hay dos: la que saca y trata mineral, y la que recibe concentrado.

El libro no tiene unidades de tipo preconcentración, concentradora ni relavera.
La preconcentración y la concentradora son **etapas de la planta** de una mina, y
la relavera es el **origen** de su mineral: B2 tiene su sub-bloque `Mina` con
mineral extraído y ley igual que San Rafael, porque se extrae de un depósito de
relaves ya cerrado y desde ahí sigue la cadena normal.
"""

ORIGENES = ("yacimiento", "relave")
ETAPAS = ("preconcentracion", "concentradora")


class ErrorCaso(ValueError):
    """El caso está mal formado y no se puede evaluar."""


@dataclass(frozen=True)
class CorrienteDeMineral:
    """Un tonelaje con la ley de cada metal que lleva.

    El libro escribe cada corriente como dos filas contiguas: el tonelaje y,
    debajo, su ley. Las etiquetas de todas las leyes son iguales —`Ley Sn`— y lo
    único que las distingue es esa vecindad. Aquí van juntas porque separarlas es
    lo que deja una ley huérfana sin que nadie lo note.
    """

    toneladas: Serie
    leyes: Mapping[str, Serie] = field(default_factory=dict)


@dataclass(frozen=True)
class ConcentradoDeMetal:
    """Lo que la planta produce para un metal.

    Una unidad polimetálica declara uno por metal: el libro lleva `Concentrado
    Producido Sn` y `Concentrado Producido Cu` como filas distintas.
    """

    toneladas: Serie
    ley: Serie
    recuperacion: Serie = ()
    toneladas_finas: Serie = ()


@dataclass(frozen=True)
class ProduccionDeUnidad:
    """Series de producción de una unidad, alineadas al horizonte del caso.

    Los dos primeros campos son los que el flujo consume. El resto describe la
    cadena metalúrgica completa —de la mina al concentrado— y existe para que el
    corroborador pueda recalcular lo que el usuario cargó y avisar si no cuadra.
    Todos son opcionales: una unidad sin preconcentración no declara lo que no
    tiene.
    """

    mineral_tratado: Serie
    """Base del cash cost unitario. Es `Mineral Tratado Total (Cash Cost)`."""

    concentrado_producido: Serie
    """Lo que la unidad entrega a la fundición del complejo."""

    metal_refinado_vendido: Serie = ()
    """Contenido fino que se vende ya refinado, en tmf."""

    metal_en_concentrado_vendido: Serie = ()
    """Contenido fino que se vende dentro del concentrado, en tmf."""

    capacidad_de_tratamiento: Serie = ()
    """Solo en unidades de fundición: el tope que acota lo alimentado."""

    # --- La cadena, para corroborar ---

    extraido: CorrienteDeMineral | None = None
    """Sub-bloque `Mina`: lo que sale del yacimiento o del depósito de relaves."""

    tratado_en_preconcentracion: CorrienteDeMineral | None = None
    preconcentrado_a_concentradora: CorrienteDeMineral | None = None
    directo_a_concentradora: CorrienteDeMineral | None = None
    tratado_total: CorrienteDeMineral | None = None
    """`Mineral Tratado Total en Concentradora`: preconcentrado más directo."""

    leyes_del_tratado: Mapping[str, Serie] = field(default_factory=dict)
    """Ley de `mineral_tratado`, que el libro repite bajo la fila de cash cost."""

    concentrados: Mapping[str, ConcentradoDeMetal] = field(default_factory=dict)
    """Concentrado producido por metal."""

    # --- Solo en la unidad de fundición ---

    alimentacion_recibida: Mapping[str, CorrienteDeMineral] = field(default_factory=dict)
    """Concentrado que entrega cada unidad de origen, con su ley.

    El libro lleva un par de filas por unidad —`Concentrado Alimentado SR` y su
    ley— y no una sola fila agregada: sin eso no se sabe de dónde viene lo que
    entra al complejo, y la ley promedio de alimentación no se puede recalcular.
    """

    recuperacion_por_grupo: Mapping[str, Serie] = field(default_factory=dict)
    """Recuperación de la fundición por grupo de unidades de origen.

    No hay una sola: el libro distingue `Recuperación Sn SR + B2` de
    `Recuperación Sn NZ + SRP`. Qué criterio agrupa está consultado a Finanzas.
    """


@dataclass(frozen=True)
class UnidadProductiva:
    """Una mina, una planta o una fundición, con todo lo suyo."""

    nombre: str
    tipo: str
    produccion: ProduccionDeUnidad
    costos: Mapping[str, Serie] = field(default_factory=dict)
    """Conceptos de costo operativo. La lista es abierta: acuerdo 6 del 27/08/2026."""

    capital: CapitalDeUnidad | None = None

    origen: str = "yacimiento"
    """De dónde sale el mineral. `relave` es una relavera cerrada que se reprocesa."""

    etapas: tuple[str, ...] = ("concentradora",)
    """Etapas de la planta, en orden. Determinan qué filas tiene la unidad."""

    entrega_a: str | None = None
    """Unidad que recibe su concentrado. Vacío significa que lo vende directo."""

    alias: tuple[str, ...] = ()
    """Abreviaturas con que el libro nombra la unidad: `SR`, `SRP`, `NZ`."""

    def __post_init__(self) -> None:
        if not self.nombre.strip():
            raise ErrorCaso("Una unidad productiva sin nombre no se puede identificar.")
        if self.tipo not in TIPOS_DE_UNIDAD:
            raise ErrorCaso(
                f"{self.nombre}: tipo {self.tipo!r} desconocido. Use {', '.join(TIPOS_DE_UNIDAD)}."
            )
        if self.origen not in ORIGENES:
            raise ErrorCaso(
                f"{self.nombre}: origen {self.origen!r} desconocido. Use {', '.join(ORIGENES)}."
            )
        desconocidas = [e for e in self.etapas if e not in ETAPAS]
        if desconocidas:
            raise ErrorCaso(
                f"{self.nombre}: etapa(s) {', '.join(desconocidas)} desconocida(s). "
                f"Use {', '.join(ETAPAS)}."
            )
        if self.capital is not None and self.capital.unidad != self.nombre:
            raise ErrorCaso(
                f"El capital declarado pertenece a {self.capital.unidad!r} y la unidad se llama "
                f"{self.nombre!r}. Cruzar capitales entre unidades rompe el desglose por mina."
            )

    @property
    def es_fundicion(self) -> bool:
        return self.tipo == "fundicion"


@dataclass(frozen=True)
class TerminosComerciales:
    """Precios y condiciones de venta del caso, por año.

    El estaño refinado se vende al precio más un premio; el estaño en
    concentrado, al precio afectado por el factor de metal pagable. Son los dos
    caminos de ingreso que la hoja `Ventas` distingue.
    """

    precio_metal_refinado: Serie
    premio_metal_refinado: Serie
    precio_metal_en_concentrado: Serie
    factor_metal_pagable: Serie
    ajustes: Serie = ()
    """Ajustes finales de la línea de venta, positivos o negativos."""


@dataclass(frozen=True)
class DatosComunes:
    """Lo que es del caso y no de una unidad."""

    gastos_administrativos: Serie
    gestion_social: Serie = ()
    otros_gastos: Serie = ()
    estudios: Serie = ()
    exploraciones: Serie = ()
    predios: Serie = ()
    intereses: Serie = ()
    otros_flujo: Serie = ()
    fletes_por_tonelada: Serie = ()
    gasto_de_ventas_por_tonelada: Serie = ()
    dias_por_cobrar: Serie = ()
    dias_por_pagar: Serie = ()
    cuentas_de_capital_trabajo_activas: bool = True
    """Reproduce el interruptor `Control!$G$21` del libro."""

    saldo_inicial_de_perdidas: float = 0.0
    capacidad_para_intensidad: float = 0.0
    """Denominador de la intensidad de capital. Cero significa que no se calcula."""


@dataclass(frozen=True)
class DatosMaestros:
    """La versión de datos maestros con la que se calcula una corrida."""

    parametros: ParametrosCorporativos
    tasas_tributarias: TasasDeDepreciacion
    tasas_financieras: TasasDeDepreciacion
    escala_regalia: EscalaProgresiva
    escala_iem: EscalaProgresiva
    tasa_igv: float = 0.18

    @property
    def version(self) -> str:
        return self.parametros.version_datos_maestros


@dataclass(frozen=True)
class Caso:
    """Un proyecto a evaluar, sea cual sea su nombre."""

    nombre: str
    horizonte: Horizonte
    unidades: tuple[UnidadProductiva, ...]
    terminos: TerminosComerciales
    datos_comunes: DatosComunes

    def __post_init__(self) -> None:
        if not self.unidades:
            raise ErrorCaso(
                f"El caso {self.nombre!r} no declara unidades productivas. Sin al menos una no hay "
                "produccion que evaluar."
            )
        nombres = [u.nombre for u in self.unidades]
        repetidos = {n for n in nombres if nombres.count(n) > 1}
        if repetidos:
            raise ErrorCaso(
                f"El caso {self.nombre!r} repite la unidad {sorted(repetidos)}. El desglose por "
                "mina exige nombres unicos."
            )
        if sum(1 for u in self.unidades if u.es_fundicion) > 1:
            raise ErrorCaso(
                f"El caso {self.nombre!r} declara mas de una fundicion. El tope de capacidad se "
                "aplica sobre el concentrado del complejo y no sabria a cual acotar."
            )
        conocidas = set(nombres)
        for unidad in self.unidades:
            if unidad.entrega_a is not None and unidad.entrega_a not in conocidas:
                raise ErrorCaso(
                    f"{unidad.nombre} entrega su concentrado a {unidad.entrega_a!r}, que el caso "
                    f"{self.nombre!r} no declara. Un destino inexistente pierde la produccion "
                    "sin que el flujo lo acuse."
                )

    @property
    def fundicion(self) -> UnidadProductiva | None:
        return next((u for u in self.unidades if u.es_fundicion), None)

    @property
    def unidades_mineras(self) -> tuple[UnidadProductiva, ...]:
        return tuple(u for u in self.unidades if not u.es_fundicion)
