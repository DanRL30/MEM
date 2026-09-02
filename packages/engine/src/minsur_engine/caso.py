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
from dataclasses import dataclass, field, fields

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
class ProduccionDeUnidad:
    """Las series de producción de una unidad, en el orden del libro.

    **La estructura es fija y siempre la misma.** Una unidad sin preconcentración
    deja esas series en cero; no declara una forma distinta. Es lo que permite
    que un proyecto que hoy no existe use la misma plantilla y el mismo motor.

    Cuatro campos son **calculados**: el mineral directo, el tratado total, el
    tratado para cash cost y la producción de concentrado, cada uno con su ley.
    Se cargan igual que los demás y el motor los rehace para avisar si no
    cuadran; nunca los sustituye.
    """

    mineral_tratado: Serie
    """`Mineral Tratado Total (Cash Cost)`. Base del cash cost unitario."""

    concentrado_producido: Serie = ()
    """`Producción Concentrado`. Lo que la unidad entrega al complejo."""

    # --- Mina ---
    mineral_extraido: Serie = ()
    ley_de_cabeza: Serie = ()

    # --- Planta ---
    tratado_en_preconcentracion: Serie = ()
    ley_de_entrada: Serie = ()
    preconcentrado: Serie = ()
    ley_del_preconcentrado: Serie = ()
    directo: Serie = ()
    ley_del_directo: Serie = ()
    tratado_total: Serie = ()
    ley_del_tratado_total: Serie = ()
    ley_del_cash_cost: Serie = ()
    toneladas_finas: Serie = ()
    ley_del_concentrado: Serie = ()
    recuperacion: Serie = ()

    # --- Concentrado de cobre ---
    concentrado_de_cu: Serie = ()
    ley_cu: Serie = ()
    ley_ag: Serie = ()
    """Ley de plata en onzas troy por tonelada, no en porcentaje."""

    # --- Solo en la unidad del complejo ---
    metal_refinado_vendido: Serie = ()
    metal_en_concentrado_vendido: Serie = ()
    capacidad_de_tratamiento: Serie = ()
    """Tope que acota lo alimentado al complejo. Es un supuesto, no producción."""


def campos_con_dato(produccion: ProduccionDeUnidad) -> frozenset[str]:
    """Campos que traen al menos un valor distinto de cero.

    Una fila entera en cero significa que el concepto **no aplica a esta
    unidad**, y la plataforma no la muestra: en un caso sin cobre ni plata, las
    filas de cobre y plata sobran en pantalla aunque la plantilla las traiga.

    Es la misma idea que `anos_con_dato` aplicada a las filas en vez de a los
    años, y vive en el motor para que la API y la interfaz decidan lo mismo. Si
    cada pantalla lo resolviera por su cuenta, acabarían mostrando cosas
    distintas del mismo caso.

    **Vacío y todo ceros son lo mismo aquí.** Una serie que no se llenó y una
    que se llenó con ceros dicen ambas que el concepto no aplica; distinguirlas
    obligaría al usuario a saber cuál de las dos escribió.
    """
    con_dato = set()
    for campo in fields(produccion):
        valor = getattr(produccion, campo.name)
        if isinstance(valor, tuple) and any(valor):
            con_dato.add(campo.name)
    return frozenset(con_dato)


@dataclass(frozen=True)
class UnidadProductiva:
    """Una mina, una planta o una fundición, con todo lo suyo."""

    nombre: str
    tipo: str
    produccion: ProduccionDeUnidad
    costos: Mapping[str, Serie] = field(default_factory=dict)
    """Conceptos de costo operativo. La lista es abierta: acuerdo 6 del 27/08/2026."""

    gastos: Mapping[str, Serie] = field(default_factory=dict)
    """Gastos de la unidad: administrativos, sociales, prediales y de estudios.

    Van aparte de los costos porque no son cash cost y no siguen su camino: unos
    entran al flujo operativo, otros al de inversiones y otros solo rebajan la
    base imponible. La lista es cerrada, a diferencia de la de costos.
    """

    fraccion_gestion_social_deducible: Serie = ()
    """Parte de la gestión social que admite la base imponible. Vacío es entera."""

    capital: CapitalDeUnidad | None = None

    origen: str = "yacimiento"
    """De dónde sale el mineral. `relave` es una relavera cerrada que se reprocesa."""

    etapas: tuple[str, ...] = ("concentradora",)
    """Etapas de la planta, en orden. Determinan qué filas tiene la unidad."""

    entrega_a: str | None = None
    """Unidad que recibe su concentrado. Vacío significa que lo vende directo."""

    alias: tuple[str, ...] = ()
    """Abreviaturas con que el libro nombra la unidad: `SR`, `SRP`, `NZ`."""

    recuperacion_del_complejo: Mapping[str, Mapping[str, Serie]] = field(default_factory=dict)
    """Solo en la unidad del complejo: su recuperación por origen y por metal.

    No hay una sola para todo el complejo: el libro distingue la de un grupo de
    unidades de la de otro y las toma de la hoja `Supuestos`. **Es un supuesto,
    no una fila de producción**, y por eso no cuelga de `ProduccionDeUnidad`:
    vive aquí hasta que exista la plantilla de supuestos.
    """

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
class MetalDelConcentrado:
    """Un metal pagable dentro del concentrado que se vende sin refinar.

    La ley pagable del cobre va en fracción y la de la plata en gramos por
    tonelada, que es como las lleva el libro; `en_onzas_troy` avisa de cuál es
    cuál, porque la plata se cotiza y se paga por onza.
    """

    nombre: str
    ley_pagable: Serie
    precio: Serie
    cargo_de_refinacion: Serie
    """RC, en dólares por tonelada neta de concentrado."""

    en_onzas_troy: bool = False


@dataclass(frozen=True)
class TerminosDelConcentrado:
    """Condiciones de venta del concentrado polimetálico, por año.

    Es el tercer camino de ingreso del libro, junto al estaño refinado y al
    estaño en concentrado: un embarque se valoriza por su contenido pagable y se
    le descuentan maquila y refinación.
    """

    merma: Serie = ()
    maquila_por_tonelada: Serie = ()
    penalidades_por_tonelada: Serie = ()
    metales: tuple[MetalDelConcentrado, ...] = ()


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

    concentrado: TerminosDelConcentrado | None = None
    """Condiciones del concentrado polimetálico. `None` si el caso no lo vende."""


@dataclass(frozen=True)
class DatosComunes:
    """Lo que es del caso y no de una unidad."""

    gastos_administrativos: Serie
    gestion_social: Serie = ()
    otros_gastos: Serie = ()
    estudios: Serie = ()
    exploraciones: Serie = ()
    predios: Serie = ()
    planilla_sobre_cash_cost: Serie = ()
    """Tasa con que el libro deriva la planilla del cash cost de cada unidad."""

    intereses: Serie = ()
    otros_flujo: Serie = ()
    fletes_por_tonelada: Serie = ()
    gasto_de_ventas_por_tonelada: Serie = ()
    dias_por_cobrar: Serie = ()
    dias_por_pagar: Serie = ()
    osinergmin: Serie = ()
    oefa: Serie = ()
    """Aportes reguladores, año a año.

    En el libro no son tasas fijas: van decrecientes los primeros ejercicios y
    después se estabilizan. MINSUR confirmó el 01/09/2026 que es deliberado
    —tienen mejor información sobre los años próximos— y por eso viven en los
    supuestos del caso y no en los parámetros corporativos, que son la tasa de
    referencia. Vacío significa que se usa esa tasa.
    """

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
