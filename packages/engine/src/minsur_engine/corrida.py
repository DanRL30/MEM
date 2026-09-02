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

from collections.abc import Sequence
from dataclasses import dataclass

from minsur_engine import capital_trabajo, complejo, tributos
from minsur_engine.capex import capex_de_etapa, capex_de_sostenimiento, capex_total
from minsur_engine.cash_cost import CostoDeUnidad, cash_cost_total
from minsur_engine.caso import Caso, DatosMaestros
from minsur_engine.complejo import BloqueDelComplejo
from minsur_engine.corroboracion import Discrepancia, corroborar
from minsur_engine.depreciacion import depreciacion_por_mina, total_depreciado
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
from minsur_engine.ventas import venta_de_metal_en_concentrado, venta_de_metal_refinado


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
class Corrida:
    """Resultado completo de evaluar un caso con una versión de datos maestros."""

    caso: Caso
    version_datos_maestros: str
    ventas: Serie
    cash_cost: Serie
    complejo: BloqueDelComplejo
    """El bloque del complejo, entero y calculado componente a componente."""

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

    bloque = _bloque_del_complejo(caso)
    ventas = _ventas(caso, bloque.refinado_sin_restriccion)
    cash_cost = _cash_cost(caso)
    capital = [u.capital for u in caso.unidades if u.capital is not None]

    produccion_por_unidad = {
        u.nombre: _serie(u.produccion.mineral_tratado, horizonte, f"{u.nombre}/tratado")
        for u in caso.unidades
    }
    depreciacion_tributaria = depreciacion_por_mina(
        horizonte, capital, maestros.tasas_tributarias, produccion=produccion_por_unidad
    )
    depreciacion_financiera = depreciacion_por_mina(
        horizonte, capital, maestros.tasas_financieras, produccion=produccion_por_unidad
    )

    comunes = caso.datos_comunes
    fletes = _por_tonelada(comunes.fletes_por_tonelada, bloque.concentrado_alimentado, horizonte)
    gasto_de_ventas = _por_tonelada(
        comunes.gasto_de_ventas_por_tonelada, bloque.concentrado_alimentado, horizonte
    )
    administrativos = _serie(comunes.gastos_administrativos, horizonte, "gastos administrativos")
    gestion_social = _serie(comunes.gestion_social, horizonte, "gestion social")
    otros_gastos = _serie(comunes.otros_gastos, horizonte, "otros gastos")
    estudios = _serie(comunes.estudios, horizonte, "estudios")
    exploraciones = _serie(comunes.exploraciones, horizonte, "exploraciones")
    predios = _serie(comunes.predios, horizonte, "predios")
    intereses = _serie(comunes.intereses, horizonte, "intereses")
    otros_flujo = _serie(comunes.otros_flujo, horizonte, "otros")

    resultados = _resolver_tributos(
        caso,
        maestros,
        ventas=ventas,
        cash_cost=cash_cost,
        fletes=fletes,
        gasto_de_ventas=gasto_de_ventas,
        administrativos=administrativos,
        gestion_social=gestion_social,
        otros_gastos=otros_gastos,
        estudios=estudios,
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
                otros_gastos[i]
                + ventas[i] * (parametros.osinergmin + parametros.oefa)
                + resultados[i].fondo_jubilacion_minera
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
        complejo=bloque,
        mineral_tratado_por_unidad=produccion_por_unidad,
        anos_activos_por_unidad=_anos_activos(caso),
        discrepancias=corroborar(caso),
        capex=total_capex,
        depreciacion_tributaria_por_mina=depreciacion_tributaria,
        depreciacion_financiera_por_mina=depreciacion_financiera,
        tributos_por_ano=resultados,
        variacion_capital_trabajo=variacion_wk,
        flujo=flujo,
        indicadores=_indicadores(caso, parametros.tasa_descuento, flujo, total_capex),
    )


# --- Bloques ------------------------------------------------------------------


def _bloque_del_complejo(caso: Caso) -> BloqueDelComplejo:
    """Rehace el bloque del complejo desde lo que producen las minas.

    Cada unidad entra con su propia recuperacion y su aporte al refinado se
    calcula por separado: la regla de oro es que nada se agrupe. El libro lleva
    una `Recuperación Sn SR + B2` y otra `NZ + SRP`, y ahi esta el problema, que
    un proyecto nuevo no cabe en ningun grupo y una diferencia en el total no se
    puede atribuir a una unidad.
    """
    fundicion = caso.fundicion
    recuperaciones = fundicion.recuperacion_del_complejo if fundicion is not None else {}
    componentes = [
        complejo.Componente(
            unidad=u.nombre,
            concentrado=u.produccion.concentrado_producido,
            ley=u.produccion.ley_del_concentrado,
            recuperacion=recuperaciones.get(u.nombre, {}).get("Sn", ()),
        )
        for u in caso.unidades_mineras
    ]
    capacidad = fundicion.produccion.capacidad_de_tratamiento if fundicion is not None else ()
    return complejo.calcular(caso.horizonte, componentes, capacidad)


def _anos_activos(caso: Caso) -> dict[str, tuple[int, ...]]:
    """Años calendario en que cada unidad produce."""
    calendario = caso.horizonte.anos_calendario
    return {
        nombre: tuple(calendario[i] for i in posiciones)
        for nombre, posiciones in unidades_activas(caso).items()
    }


def _refinado_del_complejo(caso: Caso) -> Serie:
    """Metal refinado que produce el complejo, por año.

    **No es un dato: es resultado.** La lectura de las fórmulas del libro lo
    confirmó fila por fila. Lo que alimenta a la fundición es el concentrado de
    cada mina y su ley, y el refinado es la suma del contenido fino por la
    recuperación que corresponde a cada origen.

    Se calcula sobre lo alimentado **sin acotar por la capacidad**, que es la
    línea que el libro llama `Producción Sn Refinado (Sin Restricción Pisco)`.
    Cómo se reparte el recorte cuando el complejo se satura es la regla `017`,
    reportada y sin confirmar: en el libro se le resta entero a la última unidad
    en entrar, y generalizarlo sin respuesta sería inventarlo.
    """
    horizonte = caso.horizonte
    fundicion = caso.fundicion
    if fundicion is None:
        return horizonte.ceros()

    recuperaciones = fundicion.recuperacion_del_complejo
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


def _ventas(caso: Caso, refinado_del_complejo: Serie) -> Serie:
    """Venta anual: metal refinado más metal en concentrado, más ajustes."""
    horizonte = caso.horizonte
    terminos = caso.terminos
    precio_refinado = _serie(terminos.precio_metal_refinado, horizonte, "precio refinado")
    premio = _serie(terminos.premio_metal_refinado, horizonte, "premio")
    precio_concentrado = _serie(
        terminos.precio_metal_en_concentrado, horizonte, "precio en concentrado"
    )
    factor = _serie(terminos.factor_metal_pagable, horizonte, "factor de metal pagable")
    ajustes = _serie(terminos.ajustes, horizonte, "ajustes de venta")

    refinado = [0.0] * horizonte.anos
    en_concentrado = [0.0] * horizonte.anos
    for unidad in caso.unidades:
        # El complejo no declara su refinado: se calculo desde las minas. Una
        # unidad que vende directo si lo declara, porque no pasa por fundicion.
        volumen_refinado = (
            refinado_del_complejo
            if unidad.es_fundicion
            else _serie(
                unidad.produccion.metal_refinado_vendido, horizonte, f"{unidad.nombre}/refinado"
            )
        )
        volumen_concentrado = _serie(
            unidad.produccion.metal_en_concentrado_vendido,
            horizonte,
            f"{unidad.nombre}/en concentrado",
        )
        for i in range(horizonte.anos):
            refinado[i] += venta_de_metal_refinado(
                volumen_refinado[i], precio_refinado[i], premio[i]
            )
            en_concentrado[i] += venta_de_metal_en_concentrado(
                volumen_concentrado[i], precio_concentrado[i], factor[i]
            )

    return tuple(refinado[i] + en_concentrado[i] + ajustes[i] for i in range(horizonte.anos))


def _cash_cost(caso: Caso) -> Serie:
    """Cash cost del caso, sumando las unidades año a año."""
    horizonte = caso.horizonte
    total = [0.0] * horizonte.anos
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
    return tuple(total)


def _resolver_tributos(
    caso: Caso,
    maestros: DatosMaestros,
    *,
    ventas: Serie,
    cash_cost: Serie,
    fletes: Serie,
    gasto_de_ventas: Serie,
    administrativos: Serie,
    gestion_social: Serie,
    otros_gastos: Serie,
    estudios: Serie,
    exploraciones: Serie,
    depreciacion_tributaria: Serie,
    depreciacion_financiera: Serie,
) -> tuple[tributos.ResultadoTributario, ...]:
    """Resuelve el bloque tributario de cada año, arrastrando las pérdidas.

    Las dos bases difieren en una sola línea, igual que en el libro: la de
    regalías descuenta la depreciación financiera y la de renta la tributaria.
    Confundirlas desplaza los tributos sin que el flujo económico lo delate.
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
            + gestion_social[i]
            + otros_gastos[i]
            + estudios[i]
            + ventas[i] * (parametros.osinergmin + parametros.oefa)
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
