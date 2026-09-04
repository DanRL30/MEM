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
- **La recuperación de la refinería va por unidad**, no por los grupos `SR + B2` y
  `NZ + SRP` del libro. Es la regla de oro de la refinería.
- **La depreciación va por unidad**, que es lo que pide la desviación `D-04`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from minsur_engine.capex import clasificar_por_etapa
from minsur_engine.caso import (
    Caso,
    MetalDelConcentrado,
    TerminosDelConcentrado,
    UnidadProductiva,
)
from minsur_engine.horizonte import Horizonte, Serie, anos_con_dato
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

    constante: bool = False
    """Si es un solo valor y no una serie.

    Una tasa de depreciación o un saldo de reservas no cambian de año a año: se
    escriben una vez y rigen todo el horizonte. La plantilla les deja una sola
    celda para que nadie tenga que repetir el mismo numero cuarenta veces, ni se
    pregunte que significa cambiarlo a la mitad.
    """


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
    FilaDeSupuesto("Maquila", "$/t", "maquila"),
    # El libro escribe el cargo del cobre como `0,02 x 2204,62`: la tarifa es el
    # dato y la conversion de libra a tonelada la hace el motor (regla 021). El
    # cargo queda como fila calculada, para corroborar lo que se cargue.
    FilaDeSupuesto("Tarifa de Refinacion Cu", "$/lb", "tarifa_refinacion_cu"),
    FilaDeSupuesto("Refinacion Cu", "$/t", "refinacion_cu", calculada=True),
    FilaDeSupuesto("Tarifa de Refinacion Ag", "$/oz", "tarifa_refinacion_ag"),
    FilaDeSupuesto("Penalidades Cu", "$/t", "penalidades_cu"),
    FilaDeSupuesto("Penalidades Ag", "$/t", "penalidades_ag"),
    # Fila 25 de la hoja `Ventas`, una de las dos unicas celdas tecleadas de esa
    # hoja. La 26 esta rotulada `xxx` y no se pide: es ranura reservada.
    FilaDeSupuesto("Ajustes de Venta", "$", "ajustes_de_venta"),
    FilaDeSupuesto("Otros Supuestos", SECCION),
    FilaDeSupuesto("Costo de Transporte de Concentrado", "$/t conc", "transporte"),
    FilaDeSupuesto("Gasto de Ventas Sn Refinado", "$/tmf", "gasto_de_ventas_sn_refinado"),
    FilaDeSupuesto("Gasto de Ventas Conc. Sn", "$/t conc", "gasto_de_ventas_conc_sn"),
    FilaDeSupuesto("Gasto de Ventas Conc. Cu", "$/t conc", "gasto_de_ventas_conc_cu"),
    FilaDeSupuesto("Capacidad Maxima de la Refineria", "t", "capacidad_de_la_refineria"),
    FilaDeSupuesto("Gasto Exploraciones", "$", "exploraciones"),
    FilaDeSupuesto("Gastos Financieros Netos", "$", "gastos_financieros"),
    FilaDeSupuesto("Otros Flujo Operativo", "$", "otros_flujo_operativo"),
    FilaDeSupuesto("Planilla sobre Cash Cost", "%", "planilla_sobre_cash_cost"),
    FilaDeSupuesto("Rango de Ajuste de Capex", "%", "ajuste_de_capex"),
    FilaDeSupuesto("Tasas de Depreciacion", SECCION),
    # Son datos maestros que mantiene MINSUR (`R-32`). Declararlas aqui las
    # sobrescribe **solo para este caso**, igual que ya ocurre con los aportes
    # reguladores: vacias, rige la version de datos maestros de la corrida.
    FilaDeSupuesto("Maquinaria, Equipos y Vehiculos", "%", "tasa_maquinaria", constante=True),
    FilaDeSupuesto("Instalaciones y Equipos Diversos", "%", "tasa_instalaciones", constante=True),
    FilaDeSupuesto("Edificaciones y Construcciones", "%", "tasa_edificaciones", constante=True),
    FilaDeSupuesto("Estudios", "%", "tasa_estudios", constante=True),
    FilaDeSupuesto("No Depreciable", "%", "tasa_no_depreciable", constante=True),
    FilaDeSupuesto("Parametros Corporativos", SECCION),
    # Mismo trato que las tasas de depreciacion: son dato maestro de MINSUR
    # (`R-32`) y declararlos aqui los sobrescribe **solo para este caso**.
    # Vacios, rige la version de datos maestros que la corrida registra en su
    # terna, que es lo que permite comparar dos casos.
    FilaDeSupuesto("Tasa de Descuento", "%", "tasa_descuento", constante=True),
    FilaDeSupuesto(
        "Participacion de Trabajadores", "%", "participacion_trabajadores", constante=True
    ),
    FilaDeSupuesto("Impuesto a la Renta", "%", "impuesto_renta", constante=True),
    FilaDeSupuesto("Regalia Minima sobre Ventas", "%", "regalia_minima", constante=True),
    FilaDeSupuesto("Fondo de Jubilacion Minera", "%", "fondo_jubilacion_minera", constante=True),
    FilaDeSupuesto(
        "Limite de Arrastre de Perdidas", "%", "limite_arrastre_de_perdidas", constante=True
    ),
    FilaDeSupuesto("Reguladores", SECCION),
    # El libro los lleva ano a ano y decrecientes, no como una tasa fija.
    FilaDeSupuesto("Contribucion a OEFA", "%", "oefa"),
    FilaDeSupuesto("Contribucion a OSINERGMIN", "%", "osinergmin"),
    # El libro trae estas dos de otro libro, para las unidades en marcha, y
    # calcula las de los proyectos con una tarifa por tonelada. No se puede
    # enlazar un libro ajeno: se piden como dato. Es la regla 054.
    FilaDeSupuesto("Gasto de Ventas y Fletes de Unidades en Marcha", SECCION),
    FilaDeSupuesto("Gasto de Ventas Sn Refinado LOM", "$", "gasto_de_ventas_lom"),
    FilaDeSupuesto("Fletes Concentrado LOM", "$", "fletes_lom"),
    # Lo que el libro teclea dentro de la hoja `Otros`. Las cinco constantes se
    # escriben una vez y rigen todo el horizonte, igual que las tasas de
    # depreciacion: es la regla 047.
    FilaDeSupuesto("Capital de Trabajo", SECCION),
    FilaDeSupuesto("Otros Egresos", "$", "otros_egresos"),
    FilaDeSupuesto("Otras Cuentas por Cobrar", "$", "otras_cuentas_por_cobrar"),
    FilaDeSupuesto("Otras Cuentas por Pagar", "$", "otras_cuentas_por_pagar"),
    FilaDeSupuesto("Dias de Cuentas por Cobrar", "dias", "dias_por_cobrar", constante=True),
    FilaDeSupuesto("Dias de Cuentas por Pagar", "dias", "dias_por_pagar", constante=True),
    FilaDeSupuesto("Dias del Ano Comercial", "dias", "dias_del_ano_comercial", constante=True),
    FilaDeSupuesto("Tasa de IGV", "%", "tasa_igv", constante=True),
    FilaDeSupuesto(
        "Porcentaje de Ventas de Exportacion",
        "%",
        "porcentaje_de_ventas_de_exportacion",
        constante=True,
    ),
    FilaDeSupuesto(
        "Porcentaje de Compras Locales", "%", "porcentaje_de_compras_locales", constante=True
    ),
)

# --- Supuestos de cada unidad -------------------------------------------------

FILAS_POR_UNIDAD = (
    FilaDeSupuesto("Depreciacion", SECCION),
    # El libro las llama `Proyeccion SAP`: es la depreciacion ya contabilizada de
    # los activos que existen antes del primer ano del caso, y la trae por unidad
    # y por via. No sale de ninguna inversion del caso.
    FilaDeSupuesto("Proyeccion SAP Tributaria", "k$", "proyeccion_tributaria"),
    FilaDeSupuesto("Proyeccion SAP Financiera", "k$", "proyeccion_financiera"),
    # La via financiera agota el capital contra las reservas. Declararlas las
    # convierte en dato; dejarlas vacias las convierte en calculo.
    FilaDeSupuesto("Reservas", "kt", "reservas", constante=True),
    # Recursos que pasan a reserva, ano a ano: es lo que permite el acuerdo 9 de
    # la minuta del 27/08/2026. A diferencia de las reservas, no es un saldo.
    FilaDeSupuesto("Conversion de Recursos", "kt", "conversion_de_recursos"),
    # Hasta cuantos ejercicios con produccion el capital de esta unidad es
    # inicial. **Vacio significa unidad base**, y entonces su capital depreciable
    # es sostenimiento siempre, produzca o no: es la regla `060`, y no es una
    # puerta por produccion aplicada a todas por igual. El libro usa uno en un
    # proyecto y dos en otro sin justificarlo, de modo que aqui no hay valor por
    # defecto que proponer: lo declara el caso.
    FilaDeSupuesto(
        "Umbral de Capital Inicial", "anos", "umbral_de_capital_inicial", constante=True
    ),
    FilaDeSupuesto("Refineria", SECCION),
    FilaDeSupuesto("Recuperacion de Sn en la refineria", "%", "recuperacion_en_la_refineria"),
    # Uno si el costo de refinar el concentrado de esta unidad ya esta en los
    # conceptos del bloque de la refineria; cero, o vacio, si va por la tarifa
    # por tonelada fina. Es la regla `079`, y una sola celda: no cambia por ano.
    FilaDeSupuesto(
        "Costo Directo en la Refineria",
        "fraccion",
        "costo_directo_en_la_refineria",
        constante=True,
    ),
    FilaDeSupuesto("Concentrado", SECCION),
    # Las tres salen de la ley del concentrado de esta unidad, de modo que van
    # con ella y no en la pestana comun: dos minas con distinta ley de cobre no
    # caben en una fila unica. El libro las declara una vez porque hoy solo una
    # unidad vende concentrado polimetalico.
    FilaDeSupuesto("Ley Pagable Cu", "%", "ley_pagable_cu", calculada=True),
    # La de plata no se corrobora: la formula del libro le aplica un factor cien
    # sobre una ley en onzas por tonelada. Es la regla 045, consultada.
    FilaDeSupuesto("Ley Pagable Ag", "g/t", "ley_pagable_ag"),
    FilaDeSupuesto("Refinacion Ag", "$/t", "refinacion_ag", calculada=True),
    FilaDeSupuesto("Gastos", SECCION),
    # El libro escribe la fila deducible como copia de la gestion social y en
    # dos escenarios la afecta por una fraccion. Sin declarar, es entera.
    FilaDeSupuesto(
        "Fraccion Deducible de la Gestion Social", "%", "fraccion_gestion_social_deducible"
    ),
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


def aplicar(caso: Caso, supuestos: SupuestosDelCaso, comite: ComiteDePrecios | None = None) -> Caso:
    """Vuelca los supuestos y el comité de precios sobre un caso ya leído.

    Es la costura entre las tres plantillas. La de producción trae las series de
    cada unidad; esta trae lo que vale cada cosa y cómo se liquida. Sin este
    paso, la producción se lee y no se puede vender.

    **Las pestañas por unidad se asocian por orden**, igual que en producción: la
    primera es la primera unidad del caso.
    """
    comunes = supuestos.comunes
    terminos = replace(
        caso.terminos,
        precio_metal_refinado=comite.sn if comite else caso.terminos.precio_metal_refinado,
        premio_metal_refinado=comunes.get("premio_sn", caso.terminos.premio_metal_refinado),
        precio_metal_en_concentrado=(
            comite.sn if comite else caso.terminos.precio_metal_en_concentrado
        ),
        factor_metal_pagable=comunes.get("pagable_sn", caso.terminos.factor_metal_pagable),
        ajustes=comunes.get("ajustes_de_venta", caso.terminos.ajustes),
        concentrado=_terminos_del_concentrado(comunes, comite),
    )
    unidades = _con_supuestos(caso, supuestos)
    return replace(
        caso,
        terminos=terminos,
        unidades=unidades,
        datos_comunes=replace(
            caso.datos_comunes,
            fletes_por_tonelada=comunes.get("transporte", caso.datos_comunes.fletes_por_tonelada),
            gasto_de_ventas_por_tonelada=comunes.get(
                "gasto_de_ventas_conc_sn", caso.datos_comunes.gasto_de_ventas_por_tonelada
            ),
            exploraciones=comunes.get("exploraciones", caso.datos_comunes.exploraciones),
            planilla_sobre_cash_cost=comunes.get(
                "planilla_sobre_cash_cost", caso.datos_comunes.planilla_sobre_cash_cost
            ),
            ajuste_de_capex=comunes.get("ajuste_de_capex", caso.datos_comunes.ajuste_de_capex),
            intereses=comunes.get("gastos_financieros", caso.datos_comunes.intereses),
            otros_flujo=comunes.get("otros_flujo_operativo", caso.datos_comunes.otros_flujo),
            osinergmin=comunes.get("osinergmin", ()),
            oefa=comunes.get("oefa", ()),
            tasas_declaradas=_tasas_declaradas(comunes),
            gasto_de_ventas_lom=comunes.get(
                "gasto_de_ventas_lom", caso.datos_comunes.gasto_de_ventas_lom
            ),
            fletes_lom=comunes.get("fletes_lom", caso.datos_comunes.fletes_lom),
            otros_egresos=comunes.get("otros_egresos", caso.datos_comunes.otros_egresos),
            otras_cuentas_por_cobrar=comunes.get(
                "otras_cuentas_por_cobrar", caso.datos_comunes.otras_cuentas_por_cobrar
            ),
            otras_cuentas_por_pagar=comunes.get(
                "otras_cuentas_por_pagar", caso.datos_comunes.otras_cuentas_por_pagar
            ),
            dias_por_cobrar=_repetida(
                comunes.get("dias_por_cobrar", ()),
                caso.horizonte,
                caso.datos_comunes.dias_por_cobrar,
            ),
            dias_por_pagar=_repetida(
                comunes.get("dias_por_pagar", ()),
                caso.horizonte,
                caso.datos_comunes.dias_por_pagar,
            ),
            tasa_igv=_escalar(comunes.get("tasa_igv", ()), caso.datos_comunes.tasa_igv),
            dias_del_ano_comercial=_escalar(
                comunes.get("dias_del_ano_comercial", ()),
                caso.datos_comunes.dias_del_ano_comercial,
            ),
            parametros_declarados=_parametros_declarados(comunes),
            porcentaje_de_ventas_de_exportacion=_escalar(
                comunes.get("porcentaje_de_ventas_de_exportacion", ()),
                caso.datos_comunes.porcentaje_de_ventas_de_exportacion,
            ),
            porcentaje_de_compras_locales=_escalar(
                comunes.get("porcentaje_de_compras_locales", ()),
                caso.datos_comunes.porcentaje_de_compras_locales,
            ),
        ),
    )


def _terminos_del_concentrado(
    comunes: dict[str, Serie], comite: ComiteDePrecios | None
) -> TerminosDelConcentrado | None:
    """Condiciones del concentrado de cobre, con la plata que viaja dentro."""
    if comite is None:
        return None
    return TerminosDelConcentrado(
        merma=comunes.get("merma", ()),
        maquila_por_tonelada=comunes.get("maquila", ()),
        metales=(
            MetalDelConcentrado(
                nombre="Cu",
                # La ley pagable la declara cada unidad; lo que llega aqui son
                # las condiciones del contrato, que son del caso.
                ley_pagable=(),
                precio=comite.cu,
                # Vacio deja que el motor lo derive de la tarifa por libra, que
                # es la regla `021`. En blanco la fila llega en ceros, y darla
                # por declarada apagaba el calculo y dejaba el cargo en cero.
                cargo_de_refinacion=_declarada(comunes.get("refinacion_cu", ())),
                deduccion_minima=comunes.get("deduccion_minima_cu", ()),
                factor_pagable=comunes.get("factor_pagable_cu", ()),
                tarifa_de_refinacion=comunes.get("tarifa_refinacion_cu", ()),
                penalidades_por_tonelada=comunes.get("penalidades_cu", ()),
            ),
            # La plata se cotiza por onza troy y su ley pagable viene en gramos
            # por tonelada: la conversion la hace `liquidar_concentrado`.
            MetalDelConcentrado(
                nombre="Ag",
                ley_pagable=(),
                precio=comite.ag,
                cargo_de_refinacion=(),
                en_onzas_troy=True,
                deduccion_minima=comunes.get("deduccion_minima_ag", ()),
                factor_pagable=comunes.get("factor_pagable_ag", ()),
                tarifa_de_refinacion=comunes.get("tarifa_refinacion_ag", ()),
                penalidades_por_tonelada=comunes.get("penalidades_ag", ()),
            ),
        ),
    )


def _con_supuestos(caso: Caso, supuestos: SupuestosDelCaso) -> tuple[UnidadProductiva, ...]:
    """Reparte por orden los supuestos de cada unidad.

    Dos cosas no van donde parece. La **capacidad** es de la refinería y no de una
    mina, y la **recuperación** de cada origen tambien: cuelga de la refinería,
    indexada por la unidad que entrega, porque es la refinería quien refina. Que
    haya una por origen y no una comun es la regla de oro.
    """
    de_cada_pestana = list(supuestos.por_unidad.values())
    recuperaciones: dict[str, Mapping[str, Serie]] = {}
    propios_de: dict[str, dict[str, Serie]] = {}
    mineras = 0
    for unidad in caso.unidades:
        if unidad.es_refineria:
            continue
        propios = de_cada_pestana[mineras] if mineras < len(de_cada_pestana) else {}
        mineras += 1
        propios_de[unidad.nombre] = propios
        serie = propios.get("recuperacion_en_la_refineria", ())
        if serie:
            recuperaciones[unidad.nombre] = {"Sn": serie}

    capacidad = supuestos.comunes.get("capacidad_de_la_refineria", ())
    con_supuestos = tuple(
        replace(
            unidad,
            recuperacion_en_la_refineria=recuperaciones,
            produccion=replace(unidad.produccion, capacidad_de_tratamiento=capacidad),
        )
        if unidad.es_refineria
        else replace(
            unidad,
            fraccion_gestion_social_deducible=propios_de[unidad.nombre].get(
                "fraccion_gestion_social_deducible", unidad.fraccion_gestion_social_deducible
            ),
            proyeccion_tributaria=propios_de[unidad.nombre].get(
                "proyeccion_tributaria", unidad.proyeccion_tributaria
            ),
            proyeccion_financiera=propios_de[unidad.nombre].get(
                "proyeccion_financiera", unidad.proyeccion_financiera
            ),
            reservas=_reservas(propios_de[unidad.nombre], unidad.reservas),
            conversion_de_recursos=propios_de[unidad.nombre].get(
                "conversion_de_recursos", unidad.conversion_de_recursos
            ),
            ley_pagable_declarada=_por_metal(
                propios_de[unidad.nombre], {"Cu": "ley_pagable_cu", "Ag": "ley_pagable_ag"}
            ),
            refinacion_declarada=_por_metal(propios_de[unidad.nombre], {"Ag": "refinacion_ag"}),
            costo_directo_en_la_refineria=_bandera(
                propios_de[unidad.nombre].get("costo_directo_en_la_refineria", ())
            ),
            umbral_de_capital_inicial=_umbral(
                propios_de[unidad.nombre], unidad.umbral_de_capital_inicial
            ),
        )
        for unidad in caso.unidades
    )
    return tuple(_con_la_etapa_al_dia(caso.horizonte, unidad) for unidad in con_supuestos)


def _con_la_etapa_al_dia(horizonte: Horizonte, unidad: UnidadProductiva) -> UnidadProductiva:
    """Reclasifica el capital si el umbral que decide su etapa acaba de cambiar.

    `minsur_ingest.capex.aplicar` clasifica el capital al leer el libro, y esa
    clasificacion depende del umbral de capital inicial, que llega en **otro**
    libro. Cargados en el orden habitual —capex antes que supuestos— el capital
    quedaba clasificado con el umbral todavia vacio, de modo que el de un
    proyecto salia entero a sostenimiento y el `Capex Inicial` del flujo valia
    cero. Ningun error lo acusaba: las dos clasificaciones seguian cuadrando
    entre si, porque la que estaba mal era la derivada.

    Rehacerla aqui, en vez de reordenar las cargas, es lo que hace que el
    resultado no dependa de en que orden se suban los libros: el siguiente
    supuesto que gobierne un calculo derivado no vuelve a abrir este hueco.
    """
    if unidad.capital is None:
        return unidad
    etapas = clasificar_por_etapa(
        horizonte,
        unidad.capital.por_naturaleza,
        anos_activos=anos_con_dato(unidad.produccion.mineral_tratado),
        umbral_inicial=unidad.umbral_de_capital_inicial,
    )
    if etapas == dict(unidad.capital.por_etapa):
        return unidad
    return replace(unidad, capital=replace(unidad.capital, por_etapa=etapas))


def _bandera(serie: Serie) -> bool:
    """Una celda constante que vale uno o cero, leida como bandera.

    La plantilla no tiene casilla de verificacion: sus celdas son numericas y
    validadas como tales. Un uno es si y cualquier otra cosa, incluido el vacio,
    es no.
    """
    return bool(serie) and serie[0] == 1.0


def _declarada(serie: Serie) -> Serie:
    """Una serie que el usuario escribio, o vacia si no escribio nada.

    **Una fila en blanco no llega vacia: llega en ceros**, porque la lectura
    recorre las celdas del horizonte y una celda sin valor vale cero. Comprobar
    solo que la serie exista da por declarada una fila que nadie lleno, y en los
    campos donde vacio significa «calculalo tu» eso apaga el calculo y deja el
    cero. Es la misma convencion que las reservas y el umbral de capital
    inicial: se mira el contenido, no la presencia.

    Con ello un cero escrito a proposito tampoco se distingue de la celda vacia,
    que es el precio conocido de esta convencion en toda la plantilla.
    """
    return serie if any(serie) else ()


def _por_metal(propios: dict[str, Serie], campos: Mapping[str, str]) -> dict[str, Serie]:
    """Series que la unidad declara para cada metal del concentrado.

    Una fila vacia no se guarda: declararla la convierte en dato y dejarla vacia
    deja que el motor la calcule, que es la misma distincion de las reservas.
    """
    declaradas = {}
    for metal, campo in campos.items():
        serie = _declarada(propios.get(campo, ()))
        if serie:
            declaradas[metal] = serie
    return declaradas


PARAMETROS_CORPORATIVOS = (
    "tasa_descuento",
    "participacion_trabajadores",
    "impuesto_renta",
    "regalia_minima",
    "fondo_jubilacion_minera",
    "limite_arrastre_de_perdidas",
)
"""Los que un caso puede sobrescribir. Llevan el nombre del campo del motor."""


def _parametros_declarados(comunes: dict[str, Serie]) -> dict[str, float]:
    """Parametros corporativos que el caso declara, y solo esos."""
    declarados: dict[str, float] = {}
    for campo in PARAMETROS_CORPORATIVOS:
        valor = _constante(comunes.get(campo, ()))
        if valor is not None:
            declarados[campo] = valor
    return declarados


TASAS_DE_DEPRECIACION = {
    "tasa_maquinaria": "maquinaria",
    "tasa_instalaciones": "instalaciones",
    "tasa_edificaciones": "edificaciones",
    "tasa_estudios": "estudios",
    "tasa_no_depreciable": "no_depreciable",
}
"""Campo de la plantilla y componente del motor al que sobrescribe."""


def _tasas_declaradas(comunes: dict[str, Serie]) -> dict[str, float]:
    """Tasas de depreciación que el caso declara, y solo esas.

    Lo que no se declara no se toca: rige la version de datos maestros con la
    que se corre. Declarar una sola sobrescribe una sola, de modo que media
    plantilla llena no arrastra las otras cuatro a cero.
    """
    declaradas: dict[str, float] = {}
    for campo, componente in TASAS_DE_DEPRECIACION.items():
        valor = _constante(comunes.get(campo, ()))
        if valor is not None:
            declaradas[componente] = valor
    return declaradas


def _repetida(serie: Serie, horizonte: Horizonte, respaldo: Serie) -> Serie:
    """Difunde al horizonte un valor que se escribe una vez.

    Los dias de rotacion son un solo numero en el libro y `saldo_por_dias`
    consume una serie. Sin declarar, se conserva lo que el caso ya tuviera.
    """
    valor = _constante(serie)
    if valor is None:
        return respaldo
    return tuple(valor for _ in range(horizonte.anos))


def _escalar(serie: Serie, respaldo: float) -> float:
    """Valor unico de una fila constante, o lo que el caso ya tuviera."""
    valor = _constante(serie)
    return respaldo if valor is None else valor


def _constante(serie: Serie) -> float | None:
    """Primer valor de una fila que se escribe una vez y rige todo el horizonte."""
    for valor in serie:
        if valor:
            return valor
    return None


def _umbral(propios: dict[str, Serie], declarado: int | None) -> int | None:
    """Umbral de capital inicial de una unidad, si la plantilla lo declara.

    Es una cuenta de ejercicios, de modo que se redondea al entero: la celda es
    numerica y nada impide escribir 1,5, que no significa nada. **Una fila vacia
    no es un umbral de cero: es una unidad base**, y las dos cosas dan capital
    distinto, porque el de una unidad base es sostenimiento siempre.

    Un cero escrito a proposito no se distingue de la celda vacia, que es la
    misma convencion de las reservas: la plantilla no tiene forma de separarlos
    y el motor lo lee como unidad base. La diferencia solo importaria en un
    proyecto cuyo capital fuera inicial unicamente antes de su primer ejercicio
    productivo, que el modelo de referencia no contiene.
    """
    valor = _constante(propios.get("umbral_de_capital_inicial", ()))
    return round(valor) if valor is not None else declarado


def _reservas(propios: dict[str, Serie], declaradas: float | None) -> float | None:
    """Reservas de apertura de una unidad, si la plantilla las declara.

    Es un saldo, no una serie: el libro lo lee una vez y lo rueda. Se toma el
    primer valor que la fila traiga, de modo que da igual en que ejercicio se
    escriba. **Una fila vacia no son cero reservas: es que se calculan** a partir
    de lo que la unidad extrae en el horizonte.
    """
    return _constante(propios.get("reservas", ())) or declaradas
