"""Traduce una corrida a los bloques intermedios, en el orden del libro.

La interfaz reproduce la secuencia de hojas del modelo corporativo porque es
la que el usuario tiene aprendida. Este módulo es el único sitio donde vive esa
correspondencia: los routers piden bloques y no saben en qué orden van.

**No calcula nada.** Recorre lo que el motor ya produjo y le pone nombre. Si
una cifra de aquí no coincide con el modelo, el error está en el motor y se
localiza por el módulo que la produce, no por este archivo.

Dos propiedades que conviene no romper:

**El orden es el del libro, no el de la cadena de cálculo.** `Depreciacion` va
antes que `Ventas` porque así está en el libro, aunque el cálculo no lo exija.

**La etiqueta de la pestaña se decide aquí y no en la pantalla.** Es el nombre
de la hoja, salvo el complejo: sale de `InputsProd` igual que la producción, y
dos pestañas con el mismo rótulo no se distinguen. Resolverlo en la interfaz
obligaría a repetir allí qué bloque sale de qué hoja.

**Qué se oculta lo decide el motor.** `campos_con_dato_por_unidad` viaja tal
cual hasta la pantalla. Si cada vista resolviera por su cuenta qué filas están
vacías, dos pantallas mostrarían cosas distintas del mismo caso.
"""

from __future__ import annotations

from dataclasses import fields as campos_de
from typing import Any

from minsur_engine.corroboracion import series_calculadas

from .esquemas import (
    BloqueDeCorrida,
    BloquesDeCorrida,
    DiscrepanciaDeCorroboracion,
    SerieAnual,
)
from .repositorio import CorridaAlmacenada

# Las filas de producción que el usuario carga y el motor sabe rehacer. Son las
# ocho del bloque `Calculo Interno` del libro: se muestran con su recálculo
# debajo, que es la alerta de control de calidad que MINSUR pidió el 28/08/2026.
CALCULADAS_DE_PRODUCCION = frozenset(
    {
        "directo",
        "ley_del_directo",
        "tratado_total",
        "ley_del_tratado_total",
        "mineral_tratado",
        "ley_del_cash_cost",
        "toneladas_finas",
        "concentrado_producido",
    }
)


def _series_de(fuente: Any) -> dict[str, tuple[float, ...]]:
    """Extrae las series de un bloque del motor, por nombre de campo.

    Los bloques del motor son dataclases cuyos campos son series anuales, así
    que recorrerlos por reflexión mantiene la correspondencia 1:1 con las filas
    del libro sin repetir aquí setenta nombres que ya están escritos allí. Un
    campo nuevo en el motor aparece solo en la pantalla.
    """
    salida: dict[str, tuple[float, ...]] = {}
    for campo in campos_de(fuente):
        valor = getattr(fuente, campo.name)
        if isinstance(valor, tuple) and all(isinstance(v, int | float) for v in valor):
            salida[campo.name] = tuple(float(v) for v in valor)
    return salida


def _serie(
    concepto: str,
    valores: tuple[float, ...] | list[float],
    *,
    unidad: str | None = None,
    origen: str = "calculada",
    recalculada: list[float] | None = None,
) -> SerieAnual:
    return SerieAnual(
        concepto=concepto,
        unidad=unidad,
        valores=[float(v) for v in valores],
        origen="dato" if origen == "dato" else "calculada",
        recalculada=recalculada,
    )


def _bloque_de_produccion(corrida: CorridaAlmacenada, anos: int) -> BloqueDeCorrida:
    resultado = corrida.resultado
    series: list[SerieAnual] = []
    for unidad in resultado.caso.unidades:
        con_dato = resultado.campos_con_dato_por_unidad.get(unidad.nombre, frozenset())
        recalculo = series_calculadas(unidad.produccion, anos)
        for nombre, valores in _series_de(unidad.produccion).items():
            if nombre not in con_dato:
                continue
            es_calculada = nombre in CALCULADAS_DE_PRODUCCION
            series.append(
                _serie(
                    nombre,
                    valores,
                    unidad=unidad.nombre,
                    origen="dato",
                    recalculada=recalculo.get(nombre) if es_calculada else None,
                )
            )
    return BloqueDeCorrida(
        clave="produccion",
        etiqueta="InputsProd",
        titulo="Producción por unidad",
        hoja="InputsProd",
        series=series,
    )


def _bloque_de_refineria(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    """El complejo, rehecho desde lo que producen las minas.

    Ninguna fila de este bloque es un dato: la refinería no lleva pestaña de
    producción porque todo lo suyo sale del concentrado que recibe.
    """
    refineria = corrida.resultado.refineria
    series = [_serie(nombre, valores) for nombre, valores in _series_de(refineria).items()]
    for aporte in refineria.aportes:
        for nombre, valores in _series_de(aporte).items():
            series.append(_serie(nombre, valores, unidad=aporte.unidad))
    return BloqueDeCorrida(
        clave="refineria",
        etiqueta="Complejo",
        titulo="El complejo, calculado desde las minas",
        hoja="InputsProd",
        series=series,
    )


def _bloque_de_opex(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    resultado = corrida.resultado
    series = [_serie("cash_cost", resultado.cash_cost)]
    for unidad, valores in resultado.cash_cost_por_unidad.items():
        series.append(_serie("cash_cost", valores, unidad=unidad))
    for unidad, gastos in resultado.gastos_por_unidad.items():
        for concepto, valores in gastos.items():
            series.append(_serie(concepto, valores, unidad=unidad, origen="dato"))
    return BloqueDeCorrida(
        clave="opex",
        etiqueta="InputsOpex",
        titulo="Cash cost y gastos",
        hoja="InputsOpex",
        series=series,
    )


def _bloque_de_capex(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    return BloqueDeCorrida(
        clave="capex",
        etiqueta="InputsCapex",
        titulo="Capital",
        hoja="InputsCapex",
        series=[_serie("capex", corrida.resultado.capex)],
    )


def _bloque_de_depreciacion(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    """Las dos vías, por mina y componente a componente.

    Se informan separadas aunque el libro fusione el cómputo con la maquinaria:
    una depreciación que llega sumada no se puede volver a separar.
    """
    resultado = corrida.resultado
    series: list[SerieAnual] = []
    for etiqueta, por_mina in (
        ("depreciacion_tributaria", resultado.depreciacion_tributaria_por_mina),
        ("depreciacion_financiera", resultado.depreciacion_financiera_por_mina),
    ):
        for unidad, valores in por_mina.items():
            series.append(_serie(etiqueta, valores, unidad=unidad))
    for etiqueta, por_componente in (
        ("tributaria", resultado.depreciacion_tributaria_por_componente),
        ("financiera", resultado.depreciacion_financiera_por_componente),
    ):
        for unidad, componentes in por_componente.items():
            for componente, valores in componentes.items():
                series.append(_serie(f"{etiqueta}· {componente}", valores, unidad=unidad))
    return BloqueDeCorrida(
        clave="depreciacion",
        etiqueta="Depreciacion",
        titulo="Depreciación tributaria y financiera",
        hoja="Depreciacion",
        series=series,
    )


def _bloque_de_ventas(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    resultado = corrida.resultado
    series = [_serie("ventas", resultado.ventas)]
    for camino, valores in resultado.ventas_por_camino.items():
        series.append(_serie(f"camino· {camino}", valores))
    for unidad, valores in resultado.ventas_por_unidad.items():
        series.append(_serie("ventas", valores, unidad=unidad))
    for unidad, valores in resultado.concentrado_liquidado_por_unidad.items():
        series.append(_serie("concentrado_liquidado", valores, unidad=unidad))
    for unidad, metales in resultado.volumen_pagable_por_unidad.items():
        for metal, valores in metales.items():
            series.append(_serie(f"volumen_pagable· {metal}", valores, unidad=unidad))
    return BloqueDeCorrida(
        clave="ventas",
        etiqueta="Ventas",
        titulo="Los tres caminos de ingreso",
        hoja="Ventas",
        series=series,
    )


def _bloque_de_otros(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    resultado = corrida.resultado
    series = [
        _serie("bolsa_de_egresos", resultado.bolsa_de_egresos),
        _serie("variacion_capital_trabajo", resultado.variacion_capital_trabajo),
        _serie("cuentas_por_cobrar", resultado.cuentas_por_cobrar.saldos),
        _serie("cuentas_por_cobrar· variación", resultado.cuentas_por_cobrar.variaciones),
        _serie("cuentas_por_pagar", resultado.cuentas_por_pagar.saldos),
        _serie("cuentas_por_pagar· variación", resultado.cuentas_por_pagar.variaciones),
    ]
    series.extend(
        _serie(f"igv· {nombre}", valores) for nombre, valores in _series_de(resultado.igv).items()
    )
    return BloqueDeCorrida(
        clave="otros",
        etiqueta="Otros",
        titulo="Bolsa de egresos, IGV y capital de trabajo",
        hoja="Otros",
        series=series,
    )


def _bloque_de_impuestos(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    """La hoja entera, con el signo del libro.

    Ventas positivas y gastos negativos, de modo que cada total es literalmente
    la suma de las filas que tiene encima. Es lo que se contrasta.
    """
    impuestos = corrida.resultado.impuestos
    series: list[SerieAnual] = []
    for etiqueta, sub_bloque in (
        ("regalías", impuestos.regalias),
        ("renta", impuestos.renta),
        ("impuesto a la renta", impuestos.impuesto_a_la_renta),
        ("pérdida tributaria", impuestos.perdida_tributaria),
    ):
        for nombre, valores in _series_de(sub_bloque).items():
            series.append(_serie(f"{etiqueta}· {nombre}", valores))
    return BloqueDeCorrida(
        clave="impuestos",
        etiqueta="Impuestos",
        titulo="Regalías, renta e impuesto",
        hoja="Impuestos",
        series=series,
    )


def _bloque_de_flujo(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    flujo = corrida.resultado.flujo
    return BloqueDeCorrida(
        clave="flujo",
        etiqueta="FC NZ",
        titulo="Flujo operativo, de inversiones y económico",
        hoja="FC NZ",
        series=[
            _serie("ebitda_ajustado", flujo.ebitda_ajustado),
            _serie("flujo_operativo", flujo.flujo_operativo),
            _serie("flujo_de_inversiones", flujo.flujo_de_inversiones),
            _serie("flujo_economico", flujo.flujo_economico),
        ],
    )


def bloques_de(corrida: CorridaAlmacenada) -> BloquesDeCorrida:
    """La cadena entera de una corrida, lista para pintarse pestaña a pestaña."""
    resultado = corrida.resultado
    anios = list(resultado.caso.horizonte.anos_calendario)
    return BloquesDeCorrida(
        id_caso=corrida.id_caso,
        id_corrida=corrida.id_corrida,
        anios=anios,
        unidades=[unidad.nombre for unidad in resultado.caso.unidades],
        bloques=[
            _bloque_de_produccion(corrida, len(anios)),
            _bloque_de_refineria(corrida),
            _bloque_de_opex(corrida),
            _bloque_de_capex(corrida),
            _bloque_de_depreciacion(corrida),
            _bloque_de_ventas(corrida),
            _bloque_de_otros(corrida),
            _bloque_de_impuestos(corrida),
            _bloque_de_flujo(corrida),
        ],
        campos_con_dato={
            unidad: sorted(campos)
            for unidad, campos in resultado.campos_con_dato_por_unidad.items()
        },
        discrepancias=[
            DiscrepanciaDeCorroboracion(
                unidad=d.unidad,
                concepto=d.concepto,
                ano=d.ano,
                cargado=d.cargado,
                recalculado=d.recalculado,
                diferencia=d.diferencia,
                diferencia_relativa=d.diferencia_relativa,
            )
            for d in resultado.discrepancias
        ],
    )
