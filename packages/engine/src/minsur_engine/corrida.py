"""La corrida: encadena los once bloques y produce los indicadores.

Es el único módulo que conoce el orden del cálculo. Los demás resuelven su
línea sin saber quién los llama, que es lo que permite probarlos por separado y
localizar una discrepancia en un archivo.

El orden reproduce la cadena del libro:

    produccion --> ventas --> costos --> capital --> depreciacion --> impuestos
        --> capital de trabajo --> flujo --> indicadores

Solo hay un ciclo en toda la cadena y está dentro de `impuestos`, resuelto en
forma cerrada según el [ADR 0009](../../../../docs/adr/0009-resolucion-de-la-circularidad-tributaria.md).
Entre bloques la dirección nunca se invierte.

**La corrida guarda las series intermedias, no solo los indicadores.** Es lo que
hace posible el contraste N1, que compara bloque a bloque y año a año. Verificar
únicamente el NPV es metodológicamente inválido: dos errores compensatorios dan
un NPV correcto sobre un modelo roto.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from minsur_engine import (
    capital_trabajo,
    impuestos as impuestos_,
    otros as otros_,
    refineria,
)
from minsur_engine.capex import (
    CapitalDeUnidad,
    capex_de_etapa,
    capex_de_sostenimiento,
    capex_total,
    desglosar_por_etapa_y_naturaleza,
)
from minsur_engine.cash_cost import (
    DONACIONES,
    ESTUDIOS_CAPITALIZABLES,
    ESTUDIOS_DE_GASTO,
    EXPLORACIONES,
    GASTOS_ADMINISTRATIVOS,
    GESTION_SOCIAL,
    GESTION_SOCIAL_DEDUCIBLE,
    PLANILLA,
    PREDIOS,
    SERVIDUMBRES,
    CostoDeUnidad,
    cash_cost_por_unidad,
    cash_cost_total,
    parte_deducible,
    planilla,
)
from minsur_engine.caso import (
    Caso,
    DatosMaestros,
    MetalDelConcentrado,
    UnidadProductiva,
    campos_con_dato,
)
from minsur_engine.corroboracion import Discrepancia, corroborar
from minsur_engine.depreciacion import (
    COMPONENTES_POR_AGOTAMIENTO,
    Agotamiento,
    DetalleDeDepreciacionDeUnidad,
    TasasDeDepreciacion,
    cosechas_por_etapa_y_componente,
    depreciacion_por_etapa_y_componente,
    depreciacion_por_mina,
    por_unidad,
    total_depreciado,
    trazar_agotamiento,
)
from minsur_engine.flujos import (
    ComponentesDeInversion,
    ComponentesOperativos,
    FlujoDelCaso,
    flujo_del_caso,
)
from minsur_engine.horizonte import Horizonte, Serie, anos_con_dato
from minsur_engine.indicadores import (
    Payback,
    capital_intensity,
    npv,
    payback,
    payback_descontado,
    tir,
)
from minsur_engine.parametros import ParametrosCorporativos
from minsur_engine.refineria import BloqueDeLaRefineria
from minsur_engine.ventas import (
    LiquidacionConcentrado,
    MetalPagable,
    cargo_de_refinacion_de_la_plata,
    cargo_de_refinacion_del_cobre,
    ley_pagable,
    liquidar_concentrado,
    venta_de_metal_en_concentrado,
    venta_de_metal_refinado,
    venta_total,
)


class ErrorCorrida(ValueError):
    """La corrida no se puede completar con los datos del caso."""


@dataclass(frozen=True)
class Indicadores:
    """Lo que el contraste N3 verifica."""

    npv: float
    tir: float | None
    """None cuando el flujo no cambia de signo y la tasa no está definida."""

    payback: Payback
    payback_descontado: Payback
    capital_intensity: float | None


@dataclass(frozen=True)
class _Ventas:
    """La venta del año y su desglose por unidad y por camino."""

    total: Serie
    concentrado_liquidado_por_unidad: dict[str, Serie]
    por_unidad: dict[str, Serie]
    por_camino: dict[str, Serie]
    volumen_pagable_por_unidad: dict[str, dict[str, Serie]]
    liquidaciones_por_unidad: dict[str, tuple[LiquidacionConcentrado, ...]]
    """El embarque de cada ejercicio, entero, para las unidades que liquidan.

    De el salian solo el valor neto y el volumen pagable, y con ellos la hoja
    del libro llega sin derivacion: no se puede decir si una diferencia viene de
    las toneladas, de la ley pagable o de los cargos. Se guarda el objeto y no
    sus lineas sueltas porque la liquidacion es una sola cosa.
    """

    volumenes_del_estano: dict[str, Serie]
    """Las series con que el libro deriva sus dos lineas de venta de estano.

    Son del conjunto y no de una unidad: el volumen refinado sale de la
    refineria, el del excedente tambien, y el precio, el premio y el factor son
    terminos del caso. El libro las escribe una sola vez por el mismo motivo.
    """


@dataclass(frozen=True)
class _CashCost:
    """El cash cost del caso y lo que aporta cada unidad."""

    total: Serie
    por_unidad: dict[str, Serie]


@dataclass(frozen=True)
class _Gastos:
    """El bloque de gastos, consolidado y con lo que aporta cada unidad.

    Los estudios se llevan por partida doble a propósito: `estudios` es la
    salida de caja completa y `estudios_deducibles` la parte que rebaja la base
    imponible. La diferencia son los capitalizables, que el libro deprecia en
    vez de deducir.
    """

    administrativos: Serie
    gestion_social: Serie
    gestion_social_deducible: Serie
    donaciones: Serie
    planilla: Serie
    predios: Serie
    """`InputsOpex!176`, y nada mas. Va al flujo de inversiones."""

    servidumbres: Serie
    """`InputsOpex!177`, que el libro lleva aparte de los predios y a otros
    tres sitios: la base imponible, la bolsa de egresos y el flujo operativo."""

    estudios: Serie
    estudios_deducibles: Serie
    exploraciones: Serie
    por_unidad: dict[str, dict[str, Serie]]


@dataclass(frozen=True)
class Corrida:
    """Resultado completo de evaluar un caso con una versión de datos maestros."""

    caso: Caso
    version_datos_maestros: str
    ventas: Serie
    cash_cost: Serie
    refineria: BloqueDeLaRefineria
    """El bloque de la refinería, entero y calculado componente a componente."""

    cash_cost_por_unidad: dict[str, Serie]
    """Costo operativo de cada unidad, sin agrupar.

    El libro consolida y la plataforma no: una diferencia contra el modelo tiene
    que poder atribuirse a un origen. Es la misma regla de oro de la refinería.
    """

    gastos_por_unidad: dict[str, dict[str, Serie]]
    """Gastos de cada unidad, con las dos filas que el motor deriva.

    `Planilla` y `Gestión Social Deducible` aparecen aquí junto a lo cargado
    porque el libro las muestra en el mismo bloque, y verlas separadas de su
    origen no diria de donde salen.
    """

    concentrado_liquidado_por_unidad: dict[str, Serie]
    """Valor neto del concentrado polimetalico que liquida cada unidad."""

    ventas_por_unidad: dict[str, Serie]
    """Lo que vende cada unidad, sin agrupar."""

    ventas_por_camino: dict[str, Serie]
    liquidaciones_por_unidad: dict[str, tuple[LiquidacionConcentrado, ...]]
    """La liquidacion del concentrado polimetalico, embarque a embarque.

    Es la mitad de la hoja `Ventas` del libro, y hasta ahora se calculaba y se
    descartaba: de las treinta filas con que deriva el valor neto salia solo el
    resultado.
    """

    volumenes_del_estano: dict[str, Serie]
    """Volumenes, precios, premio y factor con que se derivan las dos lineas de
    venta de estano. Son del caso, no de una unidad."""
    """Las cuatro lineas de venta del libro, antes de totalizarlas.

    El estano refinado, el estano en concentrado, el concentrado polimetalico y
    los ajustes finales. Una diferencia contra el modelo cae en una de las
    cuatro, y verlas sumadas obliga a buscarla en las cuatro a la vez.
    """

    volumen_pagable_por_unidad: dict[str, dict[str, Serie]]
    """Contenido pagable de cada metal, por unidad: toneladas de cobre y onzas
    troy de plata. Es la mitad observable del bloque N1 de metal pagable."""

    campos_con_dato_por_unidad: dict[str, frozenset[str]]
    """Filas que cada unidad llena de verdad.

    Una fila entera en cero significa que el concepto no aplica y la
    plataforma no la muestra. Se decide aqui para que la API y la interfaz
    no lleguen a conclusiones distintas del mismo caso.
    """

    otros: otros_.BloqueDeOtros
    """La hoja `Otros` entera, fila a fila y con el signo del libro.

    Hasta el 04/09/2026 de sus 93 filas salian cinco: la bolsa de egresos,
    las dos cuentas comerciales, el bloque de IGV y la variacion. El resto se
    calculaba dentro de `calcular` y moria ahi, de modo que una discrepancia
    en el capital de trabajo no se podia atribuir a la fila que la causaba.
    """

    mineral_tratado_por_unidad: dict[str, Serie]

    anos_activos_por_unidad: dict[str, tuple[int, ...]]
    """Años calendario en que cada unidad produce.

    Es la salida calculada que sustituye a las filas `Ano con produccion` del
    libro. Finanzas fijó el 01/09/2026 que la participación se deriva de los
    datos, así que ponerla como entrada crearía un campo que puede contradecir
    a las series.
    """

    discrepancias: tuple[Discrepancia, ...]
    """Lo que el recálculo no pudo corroborar. Viaja con la corrida al congelarse."""

    capex: Serie
    capital_por_unidad: tuple[CapitalDeUnidad, ...]
    """El capital que entro al calculo, unidad a unidad y ya ajustado.

    No es `caso.unidades[*].capital`: ese es el declarado, y el que se deprecia
    y llega al flujo lleva aplicada la banda de precision del estimado -la regla
    `033`-. Presentar el declarado junto a un flujo calculado con el ajustado
    descuadraria la hoja sin que nada lo acusara.
    """

    depreciacion_tributaria_por_mina: dict[str, Serie]
    depreciacion_financiera_por_mina: dict[str, Serie]

    capital_cruzado_por_unidad: dict[str, dict[str, dict[str, Serie]]]
    """El capital ajustado, cruzado etapa por naturaleza, unidad a unidad.

    Es el corte con que el libro abre tanto el bloque derivado de `InputsCapex`
    como el resumen de cada bloque de `Depreciacion`. Se guarda una vez porque lo
    consumen las dos hojas, y derivarlo dos veces las deja mostrando cortes
    distintos del mismo dinero en cuanto una de las dos derivaciones cambie.
    """

    detalle_de_depreciacion: dict[str, DetalleDeDepreciacionDeUnidad]
    """La hoja `Depreciacion` entera, unidad a unidad y con las dos vias.

    Lleva el resumen por etapa, el triangulo de cosechas de cada linea y la tabla
    con que la via financiera deriva su cuota. No se puede recomponer desde el
    total, que es la misma razon por la que la depreciacion va separada por mina.
    """

    depreciacion_tributaria_por_componente: dict[str, dict[str, Serie]]
    depreciacion_financiera_por_componente: dict[str, dict[str, Serie]]
    """La misma depreciacion, abierta por componente contable.

    El libro consolida los equipos de computo con la maquinaria y la plataforma
    no: un proyecto nuevo puede traer componentes que hoy no existen, y una
    depreciacion que llega sumada no se puede volver a separar. Lleva ademas la
    proyeccion ya contabilizada, que no sale de ninguna inversion del caso.
    """
    impuestos: impuestos_.BloqueDeImpuestos
    """La hoja `Impuestos` entera, fila a fila y con el signo del libro."""

    flujo: FlujoDelCaso
    indicadores: Indicadores

    @property
    def regalias(self) -> Serie:
        return self.impuestos.regalias.regalia_mayor

    @property
    def impuesto_renta(self) -> Serie:
        return self.impuestos.impuesto_a_la_renta.impuesto_a_la_renta

    @property
    def participacion_trabajadores(self) -> Serie:
        return self.impuestos.renta.participacion_trabajadores

    # Las cinco lineas de la hoja `Otros` que la corrida ya publicaba antes de
    # guardarla entera. Siguen llegando por su nombre para no obligar a la API,
    # al tablero y al contraste a aprender una ruta nueva por un cambio que no
    # es suyo.
    @property
    def bolsa_de_egresos(self) -> Serie:
        return self.otros.compras.bolsa

    @property
    def cuentas_por_cobrar(self) -> capital_trabajo.SaldosDeCapitalTrabajo:
        return self.otros.por_cobrar

    @property
    def cuentas_por_pagar(self) -> capital_trabajo.SaldosDeCapitalTrabajo:
        return self.otros.por_pagar

    @property
    def igv(self) -> capital_trabajo.BloqueDeIgv:
        return self.otros.igv

    @property
    def variacion_capital_trabajo(self) -> Serie:
        return self.otros.variacion


def calcular(caso: Caso, maestros: DatosMaestros) -> Corrida:
    """Evalúa un caso de punta a punta."""
    horizonte = caso.horizonte
    parametros = _con_parametros_declarados(
        maestros.parametros, caso.datos_comunes.parametros_declarados
    )

    bloque = _bloque_de_la_refineria(caso)
    resultado_de_ventas = _ventas(caso, bloque)
    ventas = resultado_de_ventas.total
    resultado_de_costos = _cash_cost(caso)
    cash_cost = resultado_de_costos.total
    gastos = _gastos(caso, resultado_de_costos.por_unidad)
    capital = _capital_ajustado(caso)

    produccion_por_unidad = {
        u.nombre: _serie(u.produccion.mineral_tratado, horizonte, f"{u.nombre}/tratado")
        for u in caso.unidades
    }
    # La regla 013 no deja correr la depreciacion antes del primer ano con
    # produccion, y solo se aplica a las unidades que producen. Una refineria o
    # una relavera de deposito no lo hacen nunca por diseno, de modo que la
    # puerta les anularia el escudo fiscal entero en vez de retrasarlo.
    con_produccion = {u.nombre: produccion_por_unidad[u.nombre] for u in caso.unidades if u.produce}
    # El estudio capitalizable no es una fila del capital: llega por los gastos y
    # el libro lo deprecia igual, en las dos vias.
    capitalizados = {
        nombre: cargados.get(ESTUDIOS_CAPITALIZABLES, ())
        for nombre, cargados in gastos.por_unidad.items()
    }
    tributarias = _con_lo_declarado(maestros.tasas_tributarias, caso.datos_comunes.tasas_declaradas)
    financieras = _con_lo_declarado(maestros.tasas_financieras, caso.datos_comunes.tasas_declaradas)
    # El cruce etapa por naturaleza del capital que de verdad se deprecia. La
    # etapa la decide el ano, de modo que las cosechas de dos etapas son
    # disjuntas y depreciarlas por separado da el mismo total.
    umbrales = {u.nombre: u.umbral_de_capital_inicial for u in caso.unidades}
    cruces = {
        unidad.unidad: desglosar_por_etapa_y_naturaleza(
            horizonte,
            unidad.por_naturaleza,
            anos_activos=anos_con_dato(produccion_por_unidad.get(unidad.unidad, ())),
            umbral_inicial=umbrales.get(unidad.unidad),
        )
        for unidad in capital
    }
    detalle_tributario = depreciacion_por_mina(
        horizonte,
        capital,
        tributarias,
        produccion=con_produccion,
        proyecciones={u.nombre: u.proyeccion_tributaria for u in caso.unidades},
        estudios=capitalizados,
        cruces=cruces,
    )
    # La via financiera agota contra las reservas en vez de depreciar lineal, y
    # por eso lleva el agotamiento que la tributaria no necesita.
    detalle_financiero = depreciacion_por_mina(
        horizonte,
        capital,
        financieras,
        produccion=con_produccion,
        agotamientos={u.nombre: _agotamiento(u, horizonte) for u in caso.unidades},
        proyecciones={u.nombre: u.proyeccion_financiera for u in caso.unidades},
        estudios=capitalizados,
        cruces=cruces,
    )
    depreciacion_tributaria = por_unidad(horizonte, detalle_tributario)
    depreciacion_financiera = por_unidad(horizonte, detalle_financiero)
    agotamientos = {u.nombre: _agotamiento(u, horizonte) for u in caso.unidades}
    detalle_de_la_hoja = _detalle_de_depreciacion(
        horizonte,
        capital,
        cruces,
        tributarias,
        financieras,
        con_produccion,
        agotamientos,
        capitalizados,
        {u.nombre: u.proyeccion_tributaria for u in caso.unidades},
        {u.nombre: u.proyeccion_financiera for u in caso.unidades},
    )

    comunes = caso.datos_comunes
    # El libro calcula el flete y el gasto de venta de los proyectos con una
    # tarifa por tonelada y trae de otro libro los de las unidades en marcha.
    # Las dos series conviven, que es la regla 054.
    # Las dos mitades viven separadas y no fundidas: son dos filas del libro,
    # y la hoja `Otros` las muestra una encima de otra porque una es dato y la
    # otra sale de una tarifa. Sumadas, una diferencia no se puede atribuir.
    fletes_lom = _serie(comunes.fletes_lom, horizonte, "fletes LOM")
    fletes_del_concentrado = _por_tonelada(
        comunes.fletes_por_tonelada, bloque.concentrado_alimentado, horizonte
    )
    fletes = _sumadas(fletes_del_concentrado, fletes_lom)
    gasto_de_ventas_lom = _serie(comunes.gasto_de_ventas_lom, horizonte, "gasto de ventas LOM")
    gasto_de_ventas_del_concentrado = _por_tonelada(
        comunes.gasto_de_ventas_por_tonelada, bloque.concentrado_alimentado, horizonte
    )
    gasto_de_ventas = _sumadas(gasto_de_ventas_del_concentrado, gasto_de_ventas_lom)
    administrativos = gastos.administrativos
    gestion_social = gastos.gestion_social
    otros_egresos = _serie(comunes.otros_egresos, horizonte, "otros egresos")
    # `Otros!30`: la servidumbre entra al flujo operativo por su importe entero,
    # pero solo en los ejercicios con gasto. El libro multiplica la fila por la
    # bandera `Periodo con gastos` de `FC NZ!8`, que vale uno cuando hay opex.
    servidumbre_del_flujo = tuple(
        gastos.servidumbres[i] if cash_cost[i] > 0.0 else 0.0 for i in range(horizonte.anos)
    )
    # La planilla es un gasto operativo derivado del cash cost de cada unidad, y
    # va donde el libro la deja: con los otros gastos del flujo operativo.
    otros_tecleados = _serie(comunes.otros_gastos, horizonte, "otros gastos")
    otros_gastos = tuple(
        otros_tecleados[i] + gastos.planilla[i] + gastos.donaciones[i] + servidumbre_del_flujo[i]
        for i in range(horizonte.anos)
    )
    # `Impuestos!16` y `!38` no leen la fila anterior: leen `Otros!49` y `!50`,
    # que son los otros egresos y la servidumbre entera, sin la bandera. Es la
    # regla `059`, y por eso las dos series existen por separado.
    otros_gastos_deducibles = tuple(
        otros_egresos[i] + gastos.servidumbres[i] for i in range(horizonte.anos)
    )
    estudios = gastos.estudios
    exploraciones = gastos.exploraciones
    predios = gastos.predios
    intereses = _serie(comunes.intereses, horizonte, "intereses")
    otros_flujo = _serie(comunes.otros_flujo, horizonte, "otros")
    tasa_osinergmin, tasa_oefa = _reguladores_por_aporte(caso, parametros)
    reguladores = tuple(tasa_osinergmin[i] + tasa_oefa[i] for i in range(horizonte.anos))

    bloque_de_impuestos = impuestos_.calcular(
        horizonte,
        ventas=ventas,
        cash_cost=cash_cost,
        fletes=fletes,
        gasto_de_ventas=gasto_de_ventas,
        administrativos=administrativos,
        estudios_deducibles=gastos.estudios_deducibles,
        gestion_social_deducible=gastos.gestion_social_deducible,
        otros_gastos=otros_gastos_deducibles,
        tasa_osinergmin=tasa_osinergmin,
        tasa_oefa=tasa_oefa,
        depreciacion_financiera=total_depreciado(horizonte, depreciacion_financiera),
        depreciacion_tributaria=total_depreciado(horizonte, depreciacion_tributaria),
        exploraciones=exploraciones,
        escala_regalia=maestros.escala_regalia,
        escala_iem=maestros.escala_iem,
        tasa_regalia_ventas=parametros.regalia_minima,
        tasa_fondo_jubilacion=parametros.fondo_jubilacion_minera,
        tasa_participacion=parametros.participacion_trabajadores,
        tasa_impuesto_renta=parametros.impuesto_renta,
        limite_arrastre_de_perdidas=parametros.limite_arrastre_de_perdidas,
        saldo_inicial_de_perdidas=comunes.saldo_inicial_de_perdidas,
    )
    resultados = bloque_de_impuestos.por_ano

    total_capex = capex_total(horizonte, capital)
    compras = otros_.bolsa_de_egresos(
        horizonte,
        opex=cash_cost,
        gastos_administrativos=administrativos,
        fletes=fletes,
        gasto_de_ventas=gasto_de_ventas,
        donaciones=gastos.donaciones,
        otros_egresos=otros_egresos,
        servidumbre=gastos.servidumbres,
        estudios=gastos.estudios,
        planilla=gastos.planilla,
        capex=total_capex,
        exploraciones=exploraciones,
    )
    bolsa = compras.bolsa
    igv = capital_trabajo.bloque_de_igv(
        horizonte,
        ventas=ventas,
        bolsa_de_egresos=bolsa,
        tasa=comunes.tasa_igv,
        porcentaje_de_ventas=comunes.porcentaje_de_ventas_de_exportacion,
        porcentaje_de_compras=comunes.porcentaje_de_compras_locales,
    )
    produce = _produce(caso)
    cuentas = _capital_de_trabajo(caso, ventas=ventas, bolsa=bolsa, igv=igv, produce=produce)
    variacion_wk = cuentas.variacion
    hoja_otros = otros_.calcular(
        horizonte,
        cash_cost_por_unidad=resultado_de_costos.por_unidad,
        cash_cost=cash_cost,
        gasto_de_ventas_lom=gasto_de_ventas_lom,
        gasto_de_ventas_sobre_concentrado=gasto_de_ventas_del_concentrado,
        fletes_lom=fletes_lom,
        fletes_sobre_concentrado=fletes_del_concentrado,
        donaciones=gastos.donaciones,
        servidumbre_del_flujo=servidumbre_del_flujo,
        otros_gastos=otros_tecleados,
        impuestos=bloque_de_impuestos,
        compras=compras,
        igv=igv,
        por_cobrar=cuentas.por_cobrar,
        por_pagar=cuentas.por_pagar,
        dias_por_cobrar=_serie(comunes.dias_por_cobrar, horizonte, "dias por cobrar"),
        dias_por_pagar=_serie(comunes.dias_por_pagar, horizonte, "dias por pagar"),
        dias_del_ano_comercial=comunes.dias_del_ano_comercial,
        otras_por_cobrar=_serie(
            comunes.otras_cuentas_por_cobrar, horizonte, "otras cuentas por cobrar"
        ),
        otras_por_pagar=_serie(
            comunes.otras_cuentas_por_pagar, horizonte, "otras cuentas por pagar"
        ),
        variacion=variacion_wk,
        porcentaje_de_ventas_de_exportacion=comunes.porcentaje_de_ventas_de_exportacion,
        porcentaje_de_compras_locales=comunes.porcentaje_de_compras_locales,
        produce=produce,
        predios=predios,
    )

    operativos = [
        ComponentesOperativos(
            ventas=ventas[i],
            cash_cost=cash_cost[i],
            fletes=fletes[i],
            gasto_de_ventas=gasto_de_ventas[i],
            gasto_administrativo=administrativos[i],
            gestion_social=gestion_social[i],
            # Osinergmin, OEFA y el fondo de jubilacion minera van con los otros
            # gastos, no con los tributos: es donde el libro los coloca.
            otros_gastos=(
                otros_gastos[i] + ventas[i] * reguladores[i] + resultados[i].fondo_jubilacion_minera
            ),
            participacion_trabajadores=resultados[i].participacion_trabajadores,
            impuestos=(
                resultados[i].regalia
                + resultados[i].impuesto_especial_mineria
                + resultados[i].impuesto_renta
            ),
            intereses=intereses[i],
            otros=otros_flujo[i],
            variacion_capital_trabajo=variacion_wk[i],
        )
        for i in range(horizonte.anos)
    ]

    inicial = capex_de_etapa(horizonte, capital, "inicial")
    sostenimiento = capex_de_sostenimiento(horizonte, capital)
    inversiones = [
        ComponentesDeInversion(
            capex_inicial=inicial[i],
            capex_sostenimiento=sostenimiento[i],
            estudios=estudios[i],
            exploraciones=exploraciones[i],
            predios=predios[i],
        )
        for i in range(horizonte.anos)
    ]

    flujo = flujo_del_caso(horizonte, operativos, inversiones)

    return Corrida(
        caso=caso,
        version_datos_maestros=maestros.version,
        ventas=ventas,
        cash_cost=cash_cost,
        cash_cost_por_unidad=resultado_de_costos.por_unidad,
        gastos_por_unidad=gastos.por_unidad,
        refineria=bloque,
        concentrado_liquidado_por_unidad=resultado_de_ventas.concentrado_liquidado_por_unidad,
        ventas_por_unidad=resultado_de_ventas.por_unidad,
        ventas_por_camino=resultado_de_ventas.por_camino,
        liquidaciones_por_unidad=resultado_de_ventas.liquidaciones_por_unidad,
        volumenes_del_estano=resultado_de_ventas.volumenes_del_estano,
        volumen_pagable_por_unidad=resultado_de_ventas.volumen_pagable_por_unidad,
        otros=hoja_otros,
        campos_con_dato_por_unidad={u.nombre: campos_con_dato(u.produccion) for u in caso.unidades},
        mineral_tratado_por_unidad=produccion_por_unidad,
        anos_activos_por_unidad=_anos_activos(caso),
        discrepancias=corroborar(caso),
        capex=total_capex,
        capital_por_unidad=tuple(capital),
        depreciacion_tributaria_por_mina=depreciacion_tributaria,
        depreciacion_financiera_por_mina=depreciacion_financiera,
        capital_cruzado_por_unidad=cruces,
        detalle_de_depreciacion=detalle_de_la_hoja,
        depreciacion_tributaria_por_componente=detalle_tributario,
        depreciacion_financiera_por_componente=detalle_financiero,
        impuestos=bloque_de_impuestos,
        flujo=flujo,
        indicadores=_indicadores(caso, parametros.tasa_descuento, flujo, total_capex),
    )


# --- Bloques ------------------------------------------------------------------


def _bloque_de_la_refineria(caso: Caso) -> BloqueDeLaRefineria:
    """Rehace el bloque de la refinería desde lo que producen las minas.

    Cada unidad entra con su propia recuperacion y su aporte al refinado se
    calcula por separado: la regla de oro es que nada se agrupe. El libro lleva
    una `Recuperación Sn SR + B2` y otra `NZ + SRP`, y ahi esta el problema, que
    un proyecto nuevo no cabe en ningun grupo y una diferencia en el total no se
    puede atribuir a una unidad.
    """
    # La unidad se llama `planta` y no `refineria` porque el modulo homonimo esta
    # importado: la variable lo taparia y `refineria.calcular` dejaria de ser la
    # funcion del bloque para ser un atributo inexistente de la unidad.
    planta = caso.refineria
    recuperaciones = planta.recuperacion_en_la_refineria if planta is not None else {}
    terminos = caso.terminos
    componentes = [
        refineria.Componente(
            unidad=u.nombre,
            concentrado=u.produccion.concentrado_producido,
            ley=u.produccion.ley_del_concentrado,
            recuperacion=recuperaciones.get(u.nombre, {}).get("Sn", ()),
            margen=refineria.margen_de_refinar(
                caso.horizonte,
                u.produccion.ley_del_concentrado,
                recuperaciones.get(u.nombre, {}).get("Sn", ()),
                precio_refinado=terminos.precio_metal_refinado,
                premio=terminos.premio_metal_refinado,
                precio_en_concentrado=terminos.precio_metal_en_concentrado,
                factor_pagable=terminos.factor_metal_pagable,
            ),
        )
        for u in caso.unidades_mineras
    ]
    capacidad = planta.produccion.capacidad_de_tratamiento if planta is not None else ()
    return refineria.calcular(caso.horizonte, componentes, capacidad)


def _anos_activos(caso: Caso) -> dict[str, tuple[int, ...]]:
    """Años calendario en que cada unidad produce."""
    calendario = caso.horizonte.anos_calendario
    return {
        nombre: tuple(calendario[i] for i in posiciones)
        for nombre, posiciones in unidades_activas(caso).items()
    }


def _ventas(caso: Caso, bloque: BloqueDeLaRefineria) -> _Ventas:
    """Los tres caminos de ingreso que distingue el libro.

    El estaño refinado se vende a precio más premio; el estaño en concentrado, a
    precio por el factor pagable; y el concentrado polimetálico se liquida
    embarque a embarque, valorizando su contenido pagable y descontando maquila
    y refinación.

    El excedente de la refinería no se descarta: es concentrado que no llegó a
    refinarse y se vende como tal, por el camino del metal en concentrado.

    **Todo se guarda desglosado**, por unidad y por camino, y no solo su suma. El
    libro lleva las cuatro líneas separadas antes de totalizarlas, y sin ese
    desglose una diferencia contra el modelo no se puede atribuir ni a un origen
    ni a una vía de venta. Es la regla de oro de la refinería aplicada aquí.
    """
    horizonte = caso.horizonte
    terminos = caso.terminos
    precio_refinado = _serie(terminos.precio_metal_refinado, horizonte, "precio refinado")
    premio = _serie(terminos.premio_metal_refinado, horizonte, "premio")
    precio_concentrado = _serie(
        terminos.precio_metal_en_concentrado, horizonte, "precio en concentrado"
    )
    factor = _serie(terminos.factor_metal_pagable, horizonte, "factor de metal pagable")
    ajustes = _serie(terminos.ajustes, horizonte, "ajustes de venta")

    anos = horizonte.anos
    total = [0.0] * anos
    linea_refinado = [0.0] * anos
    linea_en_concentrado = [0.0] * anos
    linea_del_concentrado = [0.0] * anos
    liquidado: dict[str, Serie] = {}
    por_unidad: dict[str, Serie] = {}
    volumen_pagable: dict[str, dict[str, Serie]] = {}
    embarques: dict[str, tuple[LiquidacionConcentrado, ...]] = {}
    volumen_refinado_total = [0.0] * anos
    volumen_concentrado_total = [0.0] * anos
    for unidad in caso.unidades:
        # La refinería no declara su refinado: se calculo desde las minas. Una
        # unidad que vende directo si lo declara, porque no pasa por refineria.
        volumen_refinado = (
            bloque.refinado
            if unidad.es_refineria
            else _serie(
                unidad.produccion.metal_refinado_vendido, horizonte, f"{unidad.nombre}/refinado"
            )
        )
        volumen_concentrado = _serie(
            unidad.produccion.metal_en_concentrado_vendido,
            horizonte,
            f"{unidad.nombre}/en concentrado",
        )
        if unidad.es_refineria:
            volumen_concentrado = tuple(
                volumen_concentrado[i] + bloque.refinado_del_excedente[i] for i in range(anos)
            )

        for i in range(anos):
            volumen_refinado_total[i] += volumen_refinado[i]
            volumen_concentrado_total[i] += volumen_concentrado[i]

        liquidaciones = _liquidar_concentrado_de(caso, unidad)
        if liquidaciones is not None:
            liquidado[unidad.nombre] = tuple(x.valor_neto for x in liquidaciones)
            volumen_pagable[unidad.nombre] = _volumen_pagable(liquidaciones)
            embarques[unidad.nombre] = tuple(liquidaciones)

        propia = [0.0] * anos
        for i in range(anos):
            refinado = venta_de_metal_refinado(volumen_refinado[i], precio_refinado[i], premio[i])
            en_concentrado = venta_de_metal_en_concentrado(
                volumen_concentrado[i], precio_concentrado[i], factor[i]
            )
            liquidacion = None if liquidaciones is None else liquidaciones[i]
            propia[i] = venta_total(
                metal_refinado=refinado,
                metal_en_concentrado=en_concentrado,
                concentrado=liquidacion,
            )
            linea_refinado[i] += refinado
            linea_en_concentrado[i] += en_concentrado
            linea_del_concentrado[i] += 0.0 if liquidacion is None else liquidacion.valor_neto
            total[i] += propia[i]
        por_unidad[unidad.nombre] = tuple(propia)

    return _Ventas(
        total=tuple(total[i] + ajustes[i] for i in range(anos)),
        concentrado_liquidado_por_unidad=liquidado,
        por_unidad=por_unidad,
        por_camino={
            "Venta Sn Refinado": tuple(linea_refinado),
            "Venta Sn Concentrado": tuple(linea_en_concentrado),
            "Venta Cu + Ag": tuple(linea_del_concentrado),
            "Ajustes finales": ajustes,
        },
        volumen_pagable_por_unidad=volumen_pagable,
        liquidaciones_por_unidad=embarques,
        volumenes_del_estano={
            "Volumen Sn refinado": tuple(volumen_refinado_total),
            "Volumen Sn en concentrado": tuple(volumen_concentrado_total),
            "Precio Spot Sn": precio_refinado,
            "Premio Sn": premio,
            "Precio Spot Sn en concentrado": precio_concentrado,
            "Factor Metal Pagable": factor,
            "Ajustes finales": ajustes,
        },
    )


def _volumen_pagable(liquidaciones: list[LiquidacionConcentrado]) -> dict[str, Serie]:
    """Contenido pagable de cada metal, año a año.

    Es la línea `Volumen Pagable` del libro, que hasta ahora se calculaba dentro
    de la liquidación y no salía a ninguna parte. Es la mitad observable del
    bloque N1 de metal pagable: sin ella, una diferencia en el valor no se puede
    separar en cuánto es contenido y cuánto es precio.
    """
    nombres = [metal.nombre for metal in liquidaciones[0].metales] if liquidaciones else []
    return {
        nombre: tuple(x.metales[j].volumen_pagable for x in liquidaciones)
        for j, nombre in enumerate(nombres)
    }


def _liquidar_concentrado_de(
    caso: Caso, unidad: UnidadProductiva
) -> list[LiquidacionConcentrado] | None:
    """Liquida el concentrado polimetálico de una unidad, año a año.

    Devuelve `None` cuando no hay nada que liquidar: el caso no declara términos
    de concentrado, o la unidad no produce el concentrado comercial. Distinguir
    eso de una liquidación en cero importa, porque una venta nula y una venta
    que no existe se corrigen de formas distintas.
    """
    condiciones = caso.terminos.concentrado
    toneladas = unidad.produccion.concentrado_de_cu
    if condiciones is None or not toneladas:
        return None

    horizonte = caso.horizonte
    embarcado = _serie(toneladas, horizonte, f"{unidad.nombre}/concentrado de Cu")
    merma = _serie(condiciones.merma, horizonte, "merma")
    maquila = _serie(condiciones.maquila_por_tonelada, horizonte, "maquila")
    metales = [_metal_liquidable(caso, unidad, metal) for metal in condiciones.metales]

    return [
        liquidar_concentrado(
            toneladas_vendidas=embarcado[i],
            merma=merma[i],
            metales=[
                MetalPagable(
                    nombre=metal.nombre,
                    ley_pagable=ley[i],
                    precio=precio[i],
                    cargo_de_refinacion=cargo[i],
                    en_onzas_troy=metal.en_onzas_troy,
                    # El libro la lleva por tonelada de concentrado y la copia al
                    # total sin multiplicarla; aqui se multiplica por lo
                    # embarcado, que es lo que la tarifa dice cobrar.
                    penalidades=penalidad[i] * embarcado[i],
                )
                for metal, ley, precio, cargo, penalidad in metales
            ],
            maquila_por_tonelada=maquila[i],
        )
        for i in range(horizonte.anos)
    ]


def _metal_liquidable(
    caso: Caso, unidad: UnidadProductiva, metal: MetalDelConcentrado
) -> tuple[MetalDelConcentrado, Serie, Serie, Serie, Serie]:
    """Resuelve las cuatro series de un metal en el concentrado de una unidad."""
    horizonte = caso.horizonte
    ley = _ley_pagable_de(caso, unidad, metal)
    return (
        metal,
        ley,
        _serie(metal.precio, horizonte, f"precio de {metal.nombre}"),
        _refinacion_de(caso, unidad, metal, ley),
        _serie(metal.penalidades_por_tonelada, horizonte, f"penalidades de {metal.nombre}"),
    )


def _ley_pagable_de(caso: Caso, unidad: UnidadProductiva, metal: MetalDelConcentrado) -> Serie:
    """Ley pagable de un metal en el concentrado de una unidad.

    Manda lo que declare la unidad; detrás, lo que declare el caso; y si nadie la
    declara, se calcula desde la ley del concentrado con su deducción mínima y su
    factor pagable, que es la regla 023.

    **La de la plata no se calcula.** La fórmula del libro multiplica por cien
    una ley en onzas por tonelada: es la regla 045, consultada. Sin declarar y
    sin fórmula que aplicar queda en cero, y eso se ve en la corrida.
    """
    horizonte = caso.horizonte
    nombre = f"ley pagable de {metal.nombre}"
    declarada = unidad.ley_pagable_declarada.get(metal.nombre, ())
    if declarada:
        return _serie(declarada, horizonte, nombre)
    if metal.ley_pagable:
        return _serie(metal.ley_pagable, horizonte, nombre)

    ley = _ley_del_concentrado(unidad, metal.nombre)
    if metal.en_onzas_troy or not ley or not metal.factor_pagable:
        return horizonte.ceros()

    del_concentrado = _serie(ley, horizonte, f"ley de {metal.nombre}")
    deduccion = _serie(metal.deduccion_minima, horizonte, f"deduccion minima de {metal.nombre}")
    factor = _serie(metal.factor_pagable, horizonte, f"factor pagable de {metal.nombre}")
    return tuple(
        ley_pagable(del_concentrado[i], deduccion[i], factor[i]) for i in range(horizonte.anos)
    )


def _refinacion_de(
    caso: Caso, unidad: UnidadProductiva, metal: MetalDelConcentrado, ley: Serie
) -> Serie:
    """Cargo de refinación de un metal, en dólares por tonelada neta.

    Mismo orden que la ley pagable: lo declarado manda y lo que falte se calcula
    desde la tarifa. La del cobre va por libra y la de la plata por onza troy
    sobre la ley pagable, que son las reglas 021 y 022.
    """
    horizonte = caso.horizonte
    nombre = f"refinacion de {metal.nombre}"
    declarada = unidad.refinacion_declarada.get(metal.nombre, ())
    if declarada:
        return _serie(declarada, horizonte, nombre)
    if metal.cargo_de_refinacion:
        return _serie(metal.cargo_de_refinacion, horizonte, nombre)
    if not metal.tarifa_de_refinacion:
        return horizonte.ceros()

    tarifa = _serie(metal.tarifa_de_refinacion, horizonte, f"tarifa de {nombre}")
    if metal.en_onzas_troy:
        return tuple(
            cargo_de_refinacion_de_la_plata(ley[i], tarifa[i]) for i in range(horizonte.anos)
        )
    return tuple(cargo_de_refinacion_del_cobre(tarifa[i]) for i in range(horizonte.anos))


def _ley_del_concentrado(unidad: UnidadProductiva, metal: str) -> Serie:
    """Ley del metal en el concentrado comercial, tal como la carga producción."""
    if metal == "Cu":
        return unidad.produccion.ley_cu
    if metal == "Ag":
        return unidad.produccion.ley_ag
    return ()


def _reguladores_por_aporte(caso: Caso, parametros: ParametrosCorporativos) -> tuple[Serie, Serie]:
    """Osinergmin y OEFA de cada año, en tanto por uno sobre la venta.

    El libro no los lleva como tasa fija: van decrecientes los primeros
    ejercicios y después se estabilizan. MINSUR confirmó el 01/09/2026 que es
    deliberado, porque tienen mejor información sobre los años próximos. Si el
    caso no los declara se usa la tasa de los parámetros corporativos, que es la
    de referencia.

    **Van separados porque el libro los separa**: son las filas `Impuestos!17` y
    `!18`, cada una con su tasa de `Supuestos`. Sumarlos antes de tiempo deja el
    bloque con una fila donde la hoja tiene dos.
    """
    horizonte = caso.horizonte
    comunes = caso.datos_comunes
    if not comunes.osinergmin and not comunes.oefa:
        return (
            tuple(parametros.osinergmin for _ in range(horizonte.anos)),
            tuple(parametros.oefa for _ in range(horizonte.anos)),
        )
    return (
        _serie(comunes.osinergmin, horizonte, "osinergmin"),
        _serie(comunes.oefa, horizonte, "oefa"),
    )


def _cash_cost(caso: Caso) -> _CashCost:
    """Cash cost del caso, sumando las unidades año a año.

    Guarda además el desglose por unidad. Es la regla de oro aplicada al costo:
    un total agregado no se puede atribuir a un origen, y sin origen una
    diferencia contra el modelo no se localiza.
    """
    horizonte = caso.horizonte
    total = [0.0] * horizonte.anos
    por_unidad = {u.nombre: [0.0] * horizonte.anos for u in caso.unidades if u.costos}
    for i in range(horizonte.anos):
        unidades = [
            CostoDeUnidad(
                unidad=u.nombre,
                conceptos={
                    concepto: _serie(serie, horizonte, f"{u.nombre}/{concepto}")[i]
                    for concepto, serie in u.costos.items()
                },
            )
            for u in caso.unidades
            if u.costos
        ]
        total[i] = cash_cost_total(unidades)
        for nombre, costo in cash_cost_por_unidad(unidades).items():
            por_unidad[nombre][i] = costo
    return _CashCost(tuple(total), {n: tuple(v) for n, v in por_unidad.items()})


def _detalle_de_depreciacion(
    horizonte: Horizonte,
    capital: Sequence[CapitalDeUnidad],
    cruces: Mapping[str, Mapping[str, Mapping[str, Serie]]],
    tributarias: TasasDeDepreciacion,
    financieras: TasasDeDepreciacion,
    produccion: Mapping[str, Serie],
    agotamientos: Mapping[str, Agotamiento],
    estudios: Mapping[str, Serie],
    proyeccion_tributaria: Mapping[str, Serie],
    proyeccion_financiera: Mapping[str, Serie],
) -> dict[str, DetalleDeDepreciacionDeUnidad]:
    """Arma lo que la hoja del libro muestra de cada unidad, las dos vias.

    La bandera `Periodo con Produccion` sale de la propia produccion de la unidad
    y no de un campo aparte: es lo que la hoja escribe al cerrar cada bloque, y
    es la que separa las dos puertas -la tributaria acumula, la financiera no-.
    """
    detalle: dict[str, DetalleDeDepreciacionDeUnidad] = {}
    for unidad in capital:
        nombre = unidad.unidad
        cruce = cruces.get(nombre, {})
        propia = produccion.get(nombre)
        agotamiento = agotamientos.get(nombre)
        capitalizados = estudios.get(nombre, ())
        detalle[nombre] = DetalleDeDepreciacionDeUnidad(
            tributaria=depreciacion_por_etapa_y_componente(
                horizonte,
                cruce,
                tributarias,
                produccion=propia,
                estudios=capitalizados,
                proyeccion=proyeccion_tributaria.get(nombre, ()),
            ),
            financiera=depreciacion_por_etapa_y_componente(
                horizonte,
                cruce,
                financieras,
                produccion=propia,
                agotamiento=agotamiento,
                estudios=capitalizados,
                proyeccion=proyeccion_financiera.get(nombre, ()),
            ),
            cosechas_tributarias=cosechas_por_etapa_y_componente(
                horizonte, cruce, tributarias, produccion=propia, estudios=capitalizados
            ),
            cosechas_financieras=cosechas_por_etapa_y_componente(
                horizonte,
                cruce,
                financieras,
                produccion=propia,
                agotamiento=agotamiento,
                estudios=capitalizados,
            ),
            agotamiento=(
                trazar_agotamiento(horizonte, _agotable(horizonte, cruce), agotamiento)
                if agotamiento is not None and propia is not None
                else None
            ),
            periodo_con_produccion=tuple(
                1.0 if valor else 0.0 for valor in (propia or horizonte.ceros())
            ),
        )
    return detalle


def _agotable(horizonte: Horizonte, cruce: Mapping[str, Mapping[str, Serie]]) -> Serie:
    """El capital que la via financiera agota, sumado sobre las etapas.

    Es lo que el libro rotula `Capex (sin maquinarias)`: el capital de la unidad
    menos lo que se deprecia lineal. Aqui sale por la via contraria, sumando los
    componentes que si se agotan, que da lo mismo y no depende de que la resta
    del libro reste las filas correctas.
    """
    total = [0.0] * horizonte.anos
    for naturalezas in cruce.values():
        for componente in COMPONENTES_POR_AGOTAMIENTO:
            for i, valor in enumerate(naturalezas.get(componente, ())[: horizonte.anos]):
                total[i] += valor
    return tuple(total)


def _agotamiento(unidad: UnidadProductiva, horizonte: Horizonte) -> Agotamiento:
    """Con qué reservas se agota el capital de una unidad.

    **Declararlas las convierte en dato; dejarlas vacías las convierte en
    cálculo.** Una unidad en operación las trae de su plan de vida de mina; un
    proyecto todavía no las tiene, y entonces son lo que su propio plan extrae en
    el horizonte. Es la misma distinción que hace el libro, que las lee de otro
    libro para las unidades en marcha y las suma de la producción para los
    proyectos.
    """
    extraido = _serie(unidad.produccion.mineral_extraido, horizonte, f"{unidad.nombre}/extraido")
    declaradas = unidad.reservas
    return Agotamiento(
        extraido=extraido,
        reservas=declaradas if declaradas is not None else sum(extraido),
        conversion_de_recursos=_serie(
            unidad.conversion_de_recursos, horizonte, f"{unidad.nombre}/conversion"
        ),
    )


def _con_parametros_declarados(
    maestros: ParametrosCorporativos, declarados: Mapping[str, float]
) -> ParametrosCorporativos:
    """Parametros de la corrida: los del dato maestro, salvo los que el caso declare.

    Mismo criterio que con las tasas de depreciacion: se sobrescribe uno a uno y
    la version de datos maestros sigue viajando en la terna, de modo que la
    corrida deja constancia de sobre que base se declaro lo que se declaro.
    """
    if not declarados:
        return maestros

    def de(campo: str, maestro: float) -> float:
        return declarados.get(campo, maestro)

    return ParametrosCorporativos(
        version_datos_maestros=maestros.version_datos_maestros,
        tasa_descuento=de("tasa_descuento", maestros.tasa_descuento),
        participacion_trabajadores=de(
            "participacion_trabajadores", maestros.participacion_trabajadores
        ),
        impuesto_renta=de("impuesto_renta", maestros.impuesto_renta),
        regalia_minima=de("regalia_minima", maestros.regalia_minima),
        osinergmin=maestros.osinergmin,
        oefa=maestros.oefa,
        fondo_jubilacion_minera=de("fondo_jubilacion_minera", maestros.fondo_jubilacion_minera),
        limite_arrastre_de_perdidas=de(
            "limite_arrastre_de_perdidas", maestros.limite_arrastre_de_perdidas
        ),
    )


def _con_lo_declarado(
    maestras: TasasDeDepreciacion, declaradas: Mapping[str, float]
) -> TasasDeDepreciacion:
    """Tasas de la corrida: las del dato maestro, salvo las que el caso declare.

    Se sobrescribe componente a componente y no en bloque, de modo que declarar
    una no arrastre las otras cuatro. Lo que el caso no declara se rige por la
    version de datos maestros que la corrida registra en su terna.

    El libro declara un solo juego de tasas y las dos vias lo comparten para la
    parte lineal, asi que lo declarado afecta a las dos.
    """
    if not declaradas:
        return maestras
    return replace(maestras, **declaradas)


def _capital_ajustado(caso: Caso) -> list[CapitalDeUnidad]:
    """Capital de las unidades, afectado por la banda de ajuste del caso.

    La hoja `Depreciacion` multiplica cada fila de capex por `(1 + ajuste)`
    antes de depreciarla, y el flujo de inversiones ve ese mismo capital. Es la
    banda de precisión del estimado, que el libro declara entre -35 % y +50 %.

    El factor afecta a las dos clasificaciones por igual, de modo que el cuadre
    entre ellas se conserva.
    """
    capitales = [u.capital for u in caso.unidades if u.capital is not None]
    if not caso.datos_comunes.ajuste_de_capex:
        return capitales
    factor = _serie(caso.datos_comunes.ajuste_de_capex, caso.horizonte, "ajuste de capex")
    return [
        replace(
            capital,
            por_etapa=_escalado(capital.por_etapa, factor),
            por_naturaleza=_escalado(capital.por_naturaleza, factor),
        )
        for capital in capitales
    ]


def _escalado(clasificacion: Mapping[str, Serie], factor: Serie) -> dict[str, Serie]:
    """Aplica el factor año a año sobre cada serie de una clasificación."""
    return {
        nombre: tuple(valor * (1.0 + factor[i]) for i, valor in enumerate(serie))
        for nombre, serie in clasificacion.items()
    }


def _gastos(caso: Caso, costo_por_unidad: dict[str, Serie]) -> _Gastos:
    """Consolida el bloque de gastos y deriva las dos filas que el libro calcula.

    Lo que cada unidad carga se suma a lo que el caso declara como no atribuible
    a ninguna: la hoja `Caso` recoge lo común y la plantilla de OPEX lo que tiene
    dueño. Sumar los dos lados es lo que hace el libro con su fila `Total
    Gastos`.
    """
    horizonte = caso.horizonte
    comunes = caso.datos_comunes
    tasa = _serie(comunes.planilla_sobre_cash_cost, horizonte, "planilla sobre cash cost")

    por_unidad: dict[str, dict[str, Serie]] = {}
    for unidad in caso.unidades:
        if not unidad.gastos:
            continue
        cargados = {
            concepto: _serie(serie, horizonte, f"{unidad.nombre}/{concepto}")
            for concepto, serie in unidad.gastos.items()
        }
        costo = _serie(costo_por_unidad.get(unidad.nombre, ()), horizonte, unidad.nombre)
        social = cargados.get(GESTION_SOCIAL, horizonte.ceros())
        fraccion = _fraccion(unidad.fraccion_gestion_social_deducible, horizonte)
        cargados[PLANILLA] = tuple(planilla(costo[i], tasa[i]) for i in range(horizonte.anos))
        cargados[GESTION_SOCIAL_DEDUCIBLE] = tuple(
            parte_deducible(social[i], fraccion[i]) for i in range(horizonte.anos)
        )
        por_unidad[unidad.nombre] = cargados

    def sumadas(*conceptos: str, comun: Serie = ()) -> Serie:
        base = _serie(comun, horizonte, "gasto comun")
        aportes = [
            cargados[concepto]
            for cargados in por_unidad.values()
            for concepto in conceptos
            if concepto in cargados
        ]
        return tuple(base[i] + sum(a[i] for a in aportes) for i in range(horizonte.anos))

    estudios_deducibles = sumadas(ESTUDIOS_DE_GASTO, comun=comunes.estudios)
    capitalizables = sumadas(ESTUDIOS_CAPITALIZABLES)
    return _Gastos(
        administrativos=sumadas(GASTOS_ADMINISTRATIVOS, comun=comunes.gastos_administrativos),
        gestion_social=sumadas(GESTION_SOCIAL, comun=comunes.gestion_social),
        # Lo que el caso declara como comun no lleva fraccion declarada, asi que
        # es deducible entero: es lo que el libro hace por defecto.
        gestion_social_deducible=sumadas(GESTION_SOCIAL_DEDUCIBLE, comun=comunes.gestion_social),
        donaciones=sumadas(DONACIONES),
        planilla=sumadas(PLANILLA),
        predios=sumadas(PREDIOS, comun=comunes.predios),
        servidumbres=sumadas(SERVIDUMBRES),
        estudios=tuple(estudios_deducibles[i] + capitalizables[i] for i in range(horizonte.anos)),
        estudios_deducibles=estudios_deducibles,
        exploraciones=sumadas(EXPLORACIONES, comun=comunes.exploraciones),
        por_unidad=por_unidad,
    )


def _fraccion(serie: Serie, horizonte: Horizonte) -> Serie:
    """Una fracción sin declarar es la unidad, no cero."""
    if not serie:
        return tuple(1.0 for _ in range(horizonte.anos))
    return _serie(serie, horizonte, "fraccion deducible")


@dataclass(frozen=True)
class _CapitalDeTrabajo:
    """Las dos cuentas comerciales y la variacion que entra al flujo."""

    por_cobrar: capital_trabajo.SaldosDeCapitalTrabajo
    por_pagar: capital_trabajo.SaldosDeCapitalTrabajo
    variacion: Serie


def _produce(caso: Caso) -> tuple[bool, ...]:
    """`Otros!90`: los ejercicios en que alguna unidad participa.

    El libro la rotula con el nombre de una unidad concreta y aqui se deriva
    de todas, que es el criterio que Finanzas fijo el 01/09/2026: un proyecto
    que hoy no existe no cabe en el rotulo del libro. Es la regla `086`.
    """
    activos = {i for posiciones in unidades_activas(caso).values() for i in posiciones}
    return tuple(i in activos for i in range(caso.horizonte.anos))


def _capital_de_trabajo(
    caso: Caso,
    *,
    ventas: Serie,
    bolsa: Serie,
    igv: capital_trabajo.BloqueDeIgv,
    produce: Sequence[bool],
) -> _CapitalDeTrabajo:
    """Capital de trabajo del caso, `Otros!57-84`.

    La cartera rota sobre la venta y la deuda sobre la bolsa de egresos. **La
    bandera que decide en que ejercicio se liquidan es el ano con produccion**,
    la fila 90 del libro, y no la existencia de venta: un ano de acopio o de
    parada comercial no es el fin de la vida util, y tomarlo por tal liquida
    cartera y deuda un ano antes para volver a abrirlas al siguiente. Es la
    regla 053.
    """
    horizonte = caso.horizonte
    comunes = caso.datos_comunes
    por_cobrar = capital_trabajo.cuenta(
        ventas,
        _serie(comunes.dias_por_cobrar, horizonte, "dias por cobrar"),
        produce,
        es_por_cobrar=True,
        dias_del_ano=comunes.dias_del_ano_comercial,
    )
    por_pagar = capital_trabajo.cuenta(
        bolsa,
        _serie(comunes.dias_por_pagar, horizonte, "dias por pagar"),
        produce,
        es_por_cobrar=False,
        dias_del_ano=comunes.dias_del_ano_comercial,
    )
    return _CapitalDeTrabajo(
        por_cobrar=por_cobrar,
        por_pagar=por_pagar,
        variacion=capital_trabajo.variacion_de_capital_trabajo(
            horizonte,
            por_cobrar=por_cobrar.variaciones,
            por_pagar=por_pagar.variaciones,
            otras_por_cobrar=_serie(
                comunes.otras_cuentas_por_cobrar, horizonte, "otras cuentas por cobrar"
            ),
            otras_por_pagar=_serie(
                comunes.otras_cuentas_por_pagar, horizonte, "otras cuentas por pagar"
            ),
            variacion_igv=igv.variacion_para_el_flujo,
            cuentas_activas=comunes.cuentas_de_capital_trabajo_activas,
        ),
    )


def _indicadores(caso: Caso, tasa: float, flujo: FlujoDelCaso, capex: Serie) -> Indicadores:
    economico = flujo.flujo_economico
    try:
        tasa_interna: float | None = tir(economico)
    except ValueError:
        # No todo caso tiene TIR: un flujo sin cambio de signo, uno que abre en
        # positivo -operacion en marcha, no inversion- y uno cuya unica raiz
        # queda por debajo de cero no la definen. No es un fallo del caso.
        tasa_interna = None

    capacidad = caso.datos_comunes.capacidad_para_intensidad
    intensidad = capital_intensity(sum(capex), capacidad) if capacidad > 0.0 else None

    return Indicadores(
        npv=npv(economico, tasa),
        tir=tasa_interna,
        payback=payback(economico),
        payback_descontado=payback_descontado(economico, tasa),
        capital_intensity=intensidad,
    )


# --- Utilidades ---------------------------------------------------------------


def _serie(valores: Sequence[float], horizonte: Horizonte, nombre: str) -> Serie:
    """Alinea una serie al horizonte; una serie vacía es una serie de ceros.

    Declarar en cero lo que no aplica evita que cada bloque tenga que decidir
    qué hacer con un dato ausente, que es donde aparecen los `None` que se
    propagan hasta el NPV.
    """
    if not valores:
        return horizonte.ceros()
    return horizonte.serie(valores, nombre=nombre)


def _sumadas(primera: Serie, segunda: Serie) -> Serie:
    """Suma dos series ya alineadas al horizonte."""
    return tuple(a + b for a, b in zip(primera, segunda, strict=True))


def _por_tonelada(tarifa: Sequence[float], toneladas: Serie, horizonte: Horizonte) -> Serie:
    """Gasto proporcional al tonelaje embarcado."""
    if not tarifa:
        return horizonte.ceros()
    serie = horizonte.serie(tarifa, nombre="tarifa")
    return tuple(serie[i] * toneladas[i] for i in range(horizonte.anos))


def unidades_activas(caso: Caso) -> dict[str, tuple[int, ...]]:
    """Años en que cada unidad participa, derivados de sus datos.

    Es el criterio que fijó Finanzas el 01/09/2026: una unidad entra en el caso
    en los años en que tiene valores, sin interruptor que la active.
    """
    return {
        unidad.nombre: anos_con_dato(
            _serie(unidad.produccion.mineral_tratado, caso.horizonte, unidad.nombre)
        )
        for unidad in caso.unidades
    }
