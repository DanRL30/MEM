"""La corrida: encadena los once bloques y produce los indicadores.

Es el único módulo que conoce el orden del cálculo. Los demás resuelven su
línea sin saber quién los llama, que es lo que permite probarlos por separado y
localizar una discrepancia en un archivo.

El orden reproduce la cadena del libro:

    produccion --> ventas --> costos --> capital --> depreciacion --> tributos
        --> capital de trabajo --> flujo --> indicadores

Solo hay un ciclo en toda la cadena y está dentro de `tributos`, resuelto en
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

from minsur_engine import capital_trabajo, refineria, tributos
from minsur_engine.capex import (
    CapitalDeUnidad,
    capex_de_etapa,
    capex_de_sostenimiento,
    capex_total,
)
from minsur_engine.cash_cost import (
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
from minsur_engine.caso import Caso, DatosMaestros, UnidadProductiva, campos_con_dato
from minsur_engine.corroboracion import Discrepancia, corroborar
from minsur_engine.depreciacion import (
    Agotamiento,
    TasasDeDepreciacion,
    depreciacion_por_mina,
    por_unidad,
    total_depreciado,
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
    """La venta del año y su desglose por unidad."""

    total: Serie
    concentrado_liquidado_por_unidad: dict[str, Serie]


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
    planilla: Serie
    predios: Serie
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

    campos_con_dato_por_unidad: dict[str, frozenset[str]]
    """Filas que cada unidad llena de verdad.

    Una fila entera en cero significa que el concepto no aplica y la
    plataforma no la muestra. Se decide aqui para que la API y la interfaz
    no lleguen a conclusiones distintas del mismo caso.
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
    depreciacion_tributaria_por_mina: dict[str, Serie]
    depreciacion_financiera_por_mina: dict[str, Serie]

    depreciacion_tributaria_por_componente: dict[str, dict[str, Serie]]
    depreciacion_financiera_por_componente: dict[str, dict[str, Serie]]
    """La misma depreciacion, abierta por componente contable.

    El libro consolida los equipos de computo con la maquinaria y la plataforma
    no: un proyecto nuevo puede traer componentes que hoy no existen, y una
    depreciacion que llega sumada no se puede volver a separar. Lleva ademas la
    proyeccion ya contabilizada, que no sale de ninguna inversion del caso.
    """
    tributos_por_ano: tuple[tributos.ResultadoTributario, ...]
    variacion_capital_trabajo: Serie
    flujo: FlujoDelCaso
    indicadores: Indicadores

    @property
    def regalias(self) -> Serie:
        return tuple(t.regalia for t in self.tributos_por_ano)

    @property
    def impuesto_renta(self) -> Serie:
        return tuple(t.impuesto_renta for t in self.tributos_por_ano)

    @property
    def participacion_trabajadores(self) -> Serie:
        return tuple(t.participacion_trabajadores for t in self.tributos_por_ano)


def calcular(caso: Caso, maestros: DatosMaestros) -> Corrida:
    """Evalúa un caso de punta a punta."""
    horizonte = caso.horizonte
    parametros = maestros.parametros

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
    detalle_tributario = depreciacion_por_mina(
        horizonte,
        capital,
        tributarias,
        produccion=con_produccion,
        proyecciones={u.nombre: u.proyeccion_tributaria for u in caso.unidades},
        estudios=capitalizados,
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
    )
    depreciacion_tributaria = por_unidad(horizonte, detalle_tributario)
    depreciacion_financiera = por_unidad(horizonte, detalle_financiero)

    comunes = caso.datos_comunes
    fletes = _por_tonelada(comunes.fletes_por_tonelada, bloque.concentrado_alimentado, horizonte)
    gasto_de_ventas = _por_tonelada(
        comunes.gasto_de_ventas_por_tonelada, bloque.concentrado_alimentado, horizonte
    )
    administrativos = gastos.administrativos
    gestion_social = gastos.gestion_social
    # La planilla es un gasto operativo derivado del cash cost de cada unidad, y
    # va donde el libro la deja: con los otros gastos del flujo operativo.
    otros_gastos = tuple(
        _serie(comunes.otros_gastos, horizonte, "otros gastos")[i] + gastos.planilla[i]
        for i in range(horizonte.anos)
    )
    estudios = gastos.estudios
    exploraciones = gastos.exploraciones
    predios = gastos.predios
    intereses = _serie(comunes.intereses, horizonte, "intereses")
    otros_flujo = _serie(comunes.otros_flujo, horizonte, "otros")
    reguladores = _reguladores(caso, parametros)

    resultados = _resolver_tributos(
        caso,
        maestros,
        ventas=ventas,
        cash_cost=cash_cost,
        fletes=fletes,
        gasto_de_ventas=gasto_de_ventas,
        administrativos=administrativos,
        gestion_social_deducible=gastos.gestion_social_deducible,
        otros_gastos=otros_gastos,
        estudios_deducibles=gastos.estudios_deducibles,
        exploraciones=exploraciones,
        depreciacion_tributaria=total_depreciado(horizonte, depreciacion_tributaria),
        depreciacion_financiera=total_depreciado(horizonte, depreciacion_financiera),
    )

    variacion_wk = _capital_de_trabajo(
        caso,
        ventas=ventas,
        compras=tuple(
            cash_cost[i] + administrativos[i] + fletes[i] + gasto_de_ventas[i]
            for i in range(horizonte.anos)
        ),
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
    total_capex = capex_total(horizonte, capital)

    return Corrida(
        caso=caso,
        version_datos_maestros=maestros.version,
        ventas=ventas,
        cash_cost=cash_cost,
        cash_cost_por_unidad=resultado_de_costos.por_unidad,
        gastos_por_unidad=gastos.por_unidad,
        refineria=bloque,
        concentrado_liquidado_por_unidad=resultado_de_ventas.concentrado_liquidado_por_unidad,
        campos_con_dato_por_unidad={u.nombre: campos_con_dato(u.produccion) for u in caso.unidades},
        mineral_tratado_por_unidad=produccion_por_unidad,
        anos_activos_por_unidad=_anos_activos(caso),
        discrepancias=corroborar(caso),
        capex=total_capex,
        depreciacion_tributaria_por_mina=depreciacion_tributaria,
        depreciacion_financiera_por_mina=depreciacion_financiera,
        depreciacion_tributaria_por_componente=detalle_tributario,
        depreciacion_financiera_por_componente=detalle_financiero,
        tributos_por_ano=resultados,
        variacion_capital_trabajo=variacion_wk,
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


def _refinado_de_la_refineria(caso: Caso) -> Serie:
    """Metal refinado que produce la refinería, por año.

    **No es un dato: es resultado.** La lectura de las fórmulas del libro lo
    confirmó fila por fila. Lo que alimenta a la refinería es el concentrado de
    cada mina y su ley, y el refinado es la suma del contenido fino por la
    recuperación que corresponde a cada origen.

    Se calcula sobre lo alimentado **sin acotar por la capacidad**, que es la
    línea que el libro llama `Producción Sn Refinado (Sin Restricción Pisco)`.
    Cómo se reparte el recorte cuando la refinería se satura es la regla `017`,
    reportada y sin confirmar: en el libro se le resta entero a la última unidad
    en entrar, y generalizarlo sin respuesta sería inventarlo.
    """
    horizonte = caso.horizonte
    planta = caso.refineria
    if planta is None:
        return horizonte.ceros()

    recuperaciones = planta.recuperacion_en_la_refineria
    refinado = [0.0] * horizonte.anos
    for unidad in caso.unidades_mineras:
        por_metal = recuperaciones.get(unidad.nombre, {})
        recuperacion = por_metal.get("Sn")
        if recuperacion is None:
            continue
        alimentado = _serie(
            unidad.produccion.concentrado_producido, horizonte, f"{unidad.nombre}/concentrado"
        )
        ley = _serie(unidad.produccion.ley_del_concentrado, horizonte, f"{unidad.nombre}/ley")
        tasa = _serie(recuperacion, horizonte, f"{unidad.nombre}/recuperacion")
        for i in range(horizonte.anos):
            refinado[i] += alimentado[i] * ley[i] * tasa[i]
    return tuple(refinado)


def _ventas(caso: Caso, bloque: BloqueDeLaRefineria) -> _Ventas:
    """Los tres caminos de ingreso que distingue el libro.

    El estaño refinado se vende a precio más premio; el estaño en concentrado, a
    precio por el factor pagable; y el concentrado polimetálico se liquida
    embarque a embarque, valorizando su contenido pagable y descontando maquila
    y refinación.

    El excedente de la refinería no se descarta: es concentrado que no llegó a
    refinarse y se vende como tal, por el camino del metal en concentrado.

    La liquidación se guarda **por unidad**, no solo su suma: es la regla de oro
    de la refinería aplicada aquí, y sin ella una diferencia en la venta no se
    puede atribuir a un origen.
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

    total = [0.0] * horizonte.anos
    liquidado: dict[str, Serie] = {}
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
                volumen_concentrado[i] + bloque.refinado_del_excedente[i]
                for i in range(horizonte.anos)
            )

        liquidaciones = _liquidar_concentrado_de(caso, unidad)
        if liquidaciones is not None:
            liquidado[unidad.nombre] = tuple(x.valor_neto for x in liquidaciones)

        for i in range(horizonte.anos):
            total[i] += venta_total(
                metal_refinado=venta_de_metal_refinado(
                    volumen_refinado[i], precio_refinado[i], premio[i]
                ),
                metal_en_concentrado=venta_de_metal_en_concentrado(
                    volumen_concentrado[i], precio_concentrado[i], factor[i]
                ),
                concentrado=None if liquidaciones is None else liquidaciones[i],
            )

    return _Ventas(
        total=tuple(total[i] + ajustes[i] for i in range(horizonte.anos)),
        concentrado_liquidado_por_unidad=liquidado,
    )


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
    penalidades = _serie(condiciones.penalidades_por_tonelada, horizonte, "penalidades")
    metales = [
        (
            metal,
            _serie(metal.ley_pagable, horizonte, f"ley pagable de {metal.nombre}"),
            _serie(metal.precio, horizonte, f"precio de {metal.nombre}"),
            _serie(metal.cargo_de_refinacion, horizonte, f"refinacion de {metal.nombre}"),
        )
        for metal in condiciones.metales
    ]

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
                )
                for metal, ley, precio, cargo in metales
            ],
            maquila_por_tonelada=maquila[i],
            # El libro las lleva por tonelada de concentrado; `liquidar` las
            # espera en dolares del embarque.
            penalidades=penalidades[i] * embarcado[i],
        )
        for i in range(horizonte.anos)
    ]


def _reguladores(caso: Caso, parametros: ParametrosCorporativos) -> Serie:
    """Aporte a Osinergmin y OEFA de cada año, en tanto por uno sobre la venta.

    El libro no los lleva como tasa fija: van decrecientes los primeros
    ejercicios y después se estabilizan. MINSUR confirmó el 01/09/2026 que es
    deliberado, porque tienen mejor información sobre los años próximos. Si el
    caso no los declara se usa la tasa de los parámetros corporativos, que es la
    de referencia.
    """
    horizonte = caso.horizonte
    comunes = caso.datos_comunes
    de_referencia = parametros.osinergmin + parametros.oefa
    if not comunes.osinergmin and not comunes.oefa:
        return tuple(de_referencia for _ in range(horizonte.anos))
    osinergmin = _serie(comunes.osinergmin, horizonte, "osinergmin")
    oefa = _serie(comunes.oefa, horizonte, "oefa")
    return tuple(osinergmin[i] + oefa[i] for i in range(horizonte.anos))


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
        planilla=sumadas(PLANILLA),
        predios=sumadas(PREDIOS, SERVIDUMBRES, comun=comunes.predios),
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


def _resolver_tributos(
    caso: Caso,
    maestros: DatosMaestros,
    *,
    ventas: Serie,
    cash_cost: Serie,
    fletes: Serie,
    gasto_de_ventas: Serie,
    administrativos: Serie,
    gestion_social_deducible: Serie,
    otros_gastos: Serie,
    estudios_deducibles: Serie,
    exploraciones: Serie,
    depreciacion_tributaria: Serie,
    depreciacion_financiera: Serie,
) -> tuple[tributos.ResultadoTributario, ...]:
    """Resuelve el bloque tributario de cada año, arrastrando las pérdidas.

    Las dos bases difieren en una sola línea, igual que en el libro: la de
    regalías descuenta la depreciación financiera y la de renta la tributaria.
    Confundirlas desplaza los tributos sin que el flujo económico lo delate.

    **Los gastos entran por su parte deducible, no por su importe.** La gestión
    social y los estudios salen enteros del flujo y solo en parte de la base: la
    fracción deducible de la primera la declara cada unidad, y de los segundos
    solo deduce el que es gasto, porque el capitalizable se deprecia.
    """
    parametros = maestros.parametros
    resultados: list[tributos.ResultadoTributario] = []
    saldo = caso.datos_comunes.saldo_inicial_de_perdidas

    for i in range(caso.horizonte.anos):
        gastos_comunes = (
            cash_cost[i]
            + fletes[i]
            + gasto_de_ventas[i]
            + administrativos[i]
            + gestion_social_deducible[i]
            + otros_gastos[i]
            + estudios_deducibles[i]
            + ventas[i] * _reguladores(caso, parametros)[i]
        )
        entradas = tributos.EntradasTributarias(
            ventas_totales=ventas[i],
            base_operativa=ventas[i] - gastos_comunes - depreciacion_financiera[i],
            base_imponible=(
                ventas[i] - gastos_comunes - depreciacion_tributaria[i] - exploraciones[i]
            ),
            saldo_perdidas=saldo,
            escala_regalia=maestros.escala_regalia,
            escala_iem=maestros.escala_iem,
            tasa_regalia_ventas=parametros.regalia_minima,
            tasa_fondo_jubilacion=parametros.fondo_jubilacion_minera,
            tasa_participacion=parametros.participacion_trabajadores,
            tasa_impuesto_renta=parametros.impuesto_renta,
        )
        resultado = tributos.resolver(entradas)
        resultados.append(resultado)

        # El saldo de perdidas crece con la del ejercicio y baja con lo
        # amortizado, que llega como deduccion negativa.
        perdida = max(-resultado.utilidad_imponible, 0.0)
        saldo = saldo + perdida + resultado.deduccion_perdidas

    return tuple(resultados)


def _capital_de_trabajo(caso: Caso, *, ventas: Serie, compras: Serie) -> Serie:
    """Variación del capital de trabajo del caso.

    La base de las cuentas por pagar es la bolsa de egresos operativos —cash
    cost, administrativos, fletes y gastos de venta—, que es la aproximación
    que hace el libro con su fila de adiciones.
    """
    horizonte = caso.horizonte
    comunes = caso.datos_comunes
    produce = tuple(v != 0.0 for v in ventas)

    por_cobrar = capital_trabajo.variacion_de_cuenta(
        capital_trabajo.saldo_por_dias(
            ventas, _serie(comunes.dias_por_cobrar, horizonte, "dias por cobrar")
        ),
        produce,
        es_por_cobrar=True,
    )
    por_pagar = capital_trabajo.variacion_de_cuenta(
        capital_trabajo.saldo_por_dias(
            compras, _serie(comunes.dias_por_pagar, horizonte, "dias por pagar")
        ),
        produce,
        es_por_cobrar=False,
    )
    return capital_trabajo.variacion_de_capital_trabajo(
        horizonte,
        por_cobrar=por_cobrar,
        por_pagar=por_pagar,
        cuentas_activas=comunes.cuentas_de_capital_trabajo_activas,
    )


def _indicadores(caso: Caso, tasa: float, flujo: FlujoDelCaso, capex: Serie) -> Indicadores:
    economico = flujo.flujo_economico
    try:
        tasa_interna: float | None = tir(economico)
    except ValueError:
        # Un flujo sin cambio de signo no tiene TIR. No es un fallo del caso:
        # un proyecto sin desembolso o sin retorno simplemente no la define.
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
