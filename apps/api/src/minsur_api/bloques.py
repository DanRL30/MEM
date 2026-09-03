"""Traduce una corrida a los bloques intermedios, con la forma del libro.

La interfaz reproduce la hoja que el usuario tiene aprendida, y este módulo es
el único sitio donde vive esa correspondencia: los routers piden bloques y no
saben ni en qué orden van ni cómo se llaman.

**No calcula nada.** Recorre lo que el motor ya produjo y le pone nombre. Si una
cifra no coincide con el modelo, el error está en el motor y se localiza por el
módulo que la produce, no por este archivo.

Cuatro propiedades que conviene no romper:

**El vocabulario no se escribe aquí.** Las etiquetas y las unidades de medida de
producción salen de `FILAS_DE_PRODUCCION`, el mismo catálogo con el que se emite
la plantilla y con el que se lee. Copiarlas a mano crearía una tercera lista que
mantener, y la primera vez que alguien cambie una fila del libro habría dos
sitios que actualizar y uno que se olvidaría.

**El orden es el del libro, no el de la cadena de cálculo.** `Depreciacion` va
antes que `Ventas` porque así está en el libro, aunque el cálculo no lo exija.

**El complejo no es una hoja.** Vive dentro de `InputsProd`, después de las
unidades mineras, y la hoja no termina ahí: cierra con `Venta Sn Spot`.

**Qué se oculta lo decide el motor.** `campos_con_dato_por_unidad` viaja tal cual
hasta la pantalla. Si cada vista resolviera por su cuenta qué filas están vacías,
dos pantallas mostrarían cosas distintas del mismo caso.
"""

from __future__ import annotations

from dataclasses import fields as campos_de
from typing import Any

from minsur_engine.corroboracion import series_calculadas
from minsur_engine.refineria import BloqueDeLaRefineria
from minsur_ingest.produccion import FILAS_DE_PRODUCCION

from .esquemas import (
    BloqueDeCorrida,
    BloquesDeCorrida,
    DiscrepanciaDeCorroboracion,
    GrupoDelBloque,
    SeccionDelBloque,
    SerieAnual,
)
from .repositorio import CorridaAlmacenada

# El libro agrupa la recuperación de la refinería en `SR + B2` y `NZ + SRP`. La
# plataforma la lleva por unidad: un proyecto que hoy no existe no cabe en
# ninguno de esos grupos sin decidir a cuál se parece, y una diferencia en un
# total agregado no se puede atribuir a un origen. Como ahora se ve en pantalla,
# la fila lo dice.
NOTA_DE_RECUPERACION = (
    "El libro agrupa esta recuperación con la de otra unidad. La plataforma la "
    "lleva por unidad: un proyecto nuevo no cabe en ningún grupo."
)

NOTA_DEL_CHECK = (
    "Fila del libro. Aquí se cumple por construcción, así que confirma que la "
    "cadena cuadra pero no la verifica: eso lo hace la corroboración."
)

# Las series monetarias del motor están en dólares. El libro lleva varias de sus
# hojas en miles, pero la conversión es de la ingesta al entrar y no se deshace
# al salir: la pantalla muestra la unidad en la que el dato realmente está.
DOLARES = "US$"


def _bonito(nombre: str) -> str:
    """Etiqueta legible para los bloques que todavía no tienen catálogo.

    Producción sale del catálogo del libro. Impuestos, ventas y flujo no lo
    tienen escrito en el repositorio, así que su nombre de campo se presenta
    lo mejor posible hasta que se levante su estructura hoja por hoja.
    """
    return nombre.replace("_", " ").replace("· ", "· ").capitalize()


def _series_de(fuente: Any) -> dict[str, tuple[float, ...]]:
    """Extrae las series de un bloque del motor, por nombre de campo.

    Los bloques del motor son dataclases cuyos campos son series anuales, así
    que recorrerlos por reflexión mantiene la correspondencia 1:1 con las filas
    del libro sin repetir aquí setenta nombres que ya están escritos allí.
    """
    salida: dict[str, tuple[float, ...]] = {}
    for campo in campos_de(fuente):
        valor = getattr(fuente, campo.name)
        if isinstance(valor, tuple) and all(isinstance(v, int | float) for v in valor):
            salida[campo.name] = tuple(float(v) for v in valor)
    return salida


def _serie(
    etiqueta: str,
    valores: tuple[float, ...] | list[float],
    *,
    medida: str = "",
    concepto: str = "",
    origen: str = "calculada",
    recalculada: list[float] | None = None,
    nota: str | None = None,
) -> SerieAnual:
    return SerieAnual(
        etiqueta=etiqueta,
        medida=medida,
        concepto=concepto,
        valores=[float(v) for v in valores],
        origen="dato" if origen == "dato" else "calculada",
        recalculada=recalculada,
        nota=nota,
    )


def _una_seccion(series: list[SerieAnual]) -> list[SeccionDelBloque]:
    """Un grupo que no se subdivide: una sección sin título."""
    return [SeccionDelBloque(titulo=None, series=series)]


def _un_grupo(series: list[SerieAnual]) -> list[GrupoDelBloque]:
    """Un bloque que no se reparte por unidad: un grupo sin banda."""
    return [GrupoDelBloque(titulo="", secciones=_una_seccion(series))]


# --- InputsProd ---------------------------------------------------------------


def _grupos_de_unidades(corrida: CorridaAlmacenada, anos: int) -> list[GrupoDelBloque]:
    """Un grupo por unidad que produce, con las filas del libro en su orden.

    Se recorre `FILAS_DE_PRODUCCION`, que trae las veintidós entradas del libro:
    las tres bandas de sección y las diecinueve filas con dato, cada una con su
    etiqueta, su unidad de medida y el campo del motor que la alimenta.
    """
    resultado = corrida.resultado
    grupos: list[GrupoDelBloque] = []

    for unidad in resultado.caso.unidades:
        con_dato = resultado.campos_con_dato_por_unidad.get(unidad.nombre, frozenset())
        if not con_dato:
            continue
        recalculo = series_calculadas(unidad.produccion, anos)
        secciones: list[SeccionDelBloque] = []
        abierta: SeccionDelBloque | None = None

        for fila in FILAS_DE_PRODUCCION:
            if fila.es_seccion:
                abierta = SeccionDelBloque(titulo=fila.etiqueta, series=[])
                secciones.append(abierta)
                continue
            if fila.campo not in con_dato or abierta is None:
                continue
            abierta.series.append(
                _serie(
                    fila.etiqueta,
                    getattr(unidad.produccion, fila.campo),
                    medida=fila.medida or "",
                    concepto=fila.campo,
                    origen="dato",
                    recalculada=recalculo.get(fila.campo) if fila.calculada else None,
                )
            )

        con_filas = [seccion for seccion in secciones if seccion.series]
        if con_filas:
            grupos.append(GrupoDelBloque(titulo=unidad.nombre, secciones=con_filas))

    return grupos


def _grupo_del_complejo(refineria: BloqueDeLaRefineria, nombre: str) -> GrupoDelBloque:
    """El bloque de la refinería, en el orden de las filas 90 a 106 del libro.

    Ninguna fila es un dato: la refinería no lleva pestaña de producción porque
    todo lo suyo sale del concentrado que le entregan las minas.
    """
    series: list[SerieAnual] = []

    # Cinco pares alimentado/ley, uno por origen, en el orden de las minas.
    for aporte in refineria.aportes:
        series.append(
            _serie(f"Concentrado Alimentado {aporte.unidad}", aporte.concentrado, medida="t")
        )
        series.append(_serie(f"Ley de Sn en Concentrado {aporte.unidad}", aporte.ley, medida="%"))

    series.extend(
        [
            _serie("Concentrado Alimentado", refineria.concentrado_alimentado, medida="t"),
            _serie("Ley de Sn en Concentrado", refineria.ley_de_alimentacion, medida="%"),
            _serie("Toneladas Alimentadas+escoria", refineria.toneladas_alimentadas, medida="t"),
            _serie("Ley Promedio de Alimentación", refineria.ley_de_alimentacion, medida="%"),
        ]
    )

    for aporte in refineria.aportes:
        series.append(
            _serie(
                f"Recuperación Sn {aporte.unidad}",
                aporte.recuperacion,
                medida="%",
                nota=NOTA_DE_RECUPERACION,
            )
        )

    series.append(
        _serie(
            "Producción Sn Refinado (Sin Restricción Pisco)",
            refineria.refinado_sin_restriccion,
            medida="t",
        )
    )
    series.append(_serie("Producción Sn Refinado", refineria.refinado, medida="t"))

    return GrupoDelBloque(titulo=nombre, secciones=_una_seccion(series))


def _grupo_de_venta_spot(refineria: BloqueDeLaRefineria) -> GrupoDelBloque:
    """Las cuatro filas con las que cierra la hoja, 109 a 112."""
    return GrupoDelBloque(
        titulo="Venta Sn Spot",
        secciones=_una_seccion(
            [
                _serie("Concentrado Excedente", refineria.concentrado_excedente, medida="t"),
                _serie("Ley Promedio de Alimentación", refineria.ley_del_excedente, medida="%"),
                _serie("Producción Sn Refinado", refineria.refinado_del_excedente, medida="t"),
                _serie("Check", refineria.check, medida="t", nota=NOTA_DEL_CHECK),
            ]
        ),
    )


def _bloque_de_produccion(corrida: CorridaAlmacenada, anos: int) -> BloqueDeCorrida:
    resultado = corrida.resultado
    grupos = _grupos_de_unidades(corrida, anos)
    refineria = resultado.caso.refineria
    if refineria is not None:
        grupos.append(_grupo_del_complejo(resultado.refineria, refineria.nombre))
        grupos.append(_grupo_de_venta_spot(resultado.refineria))
    return BloqueDeCorrida(
        clave="produccion",
        etiqueta="InputsProd",
        titulo="Producción, complejo y venta spot",
        hoja="InputsProd",
        grupos=grupos,
    )


# --- El resto de las hojas ----------------------------------------------------


def _bloque_de_opex(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    """Cash cost y gastos. Las etiquetas ya son las del libro.

    El catálogo de la ingesta usa la etiqueta como clave del diccionario del
    motor, así que aquí no hay nada que traducir.
    """
    resultado = corrida.resultado
    grupos: list[GrupoDelBloque] = []
    for unidad in resultado.caso.unidades:
        secciones: list[SeccionDelBloque] = []
        costos = [
            _serie(concepto, valores, medida=DOLARES) for concepto, valores in unidad.costos.items()
        ]
        if unidad.nombre in resultado.cash_cost_por_unidad:
            costos.insert(
                0,
                _serie("Cash cost", resultado.cash_cost_por_unidad[unidad.nombre], medida=DOLARES),
            )
        if costos:
            secciones.append(SeccionDelBloque(titulo="Cash Cost", series=costos))
        gastos = [
            _serie(concepto, valores, medida=DOLARES, origen="dato")
            for concepto, valores in unidad.gastos.items()
        ]
        if gastos:
            secciones.append(SeccionDelBloque(titulo="Gastos", series=gastos))
        if secciones:
            grupos.append(GrupoDelBloque(titulo=unidad.nombre, secciones=secciones))

    grupos.insert(
        0,
        GrupoDelBloque(
            titulo="",
            secciones=_una_seccion(
                [_serie("Cash cost del caso", resultado.cash_cost, medida=DOLARES)]
            ),
        ),
    )
    return BloqueDeCorrida(
        clave="opex",
        etiqueta="InputsOpex",
        titulo="Cash cost y gastos",
        hoja="InputsOpex",
        grupos=grupos,
    )


def _bloque_de_capex(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    return BloqueDeCorrida(
        clave="capex",
        etiqueta="InputsCapex",
        titulo="Capital",
        hoja="InputsCapex",
        grupos=_un_grupo([_serie("Capex", corrida.resultado.capex, medida=DOLARES)]),
    )


def _bloque_de_depreciacion(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    """Las dos vías, por mina y componente a componente.

    Se informan separadas aunque el libro fusione el cómputo con la maquinaria:
    una depreciación que llega sumada no se puede volver a separar.
    """
    resultado = corrida.resultado
    grupos: list[GrupoDelBloque] = []
    for unidad in resultado.caso.unidades:
        secciones: list[SeccionDelBloque] = []
        for titulo, por_mina, por_componente in (
            (
                "Tributaria",
                resultado.depreciacion_tributaria_por_mina,
                resultado.depreciacion_tributaria_por_componente,
            ),
            (
                "Financiera",
                resultado.depreciacion_financiera_por_mina,
                resultado.depreciacion_financiera_por_componente,
            ),
        ):
            series: list[SerieAnual] = []
            if unidad.nombre in por_mina:
                series.append(_serie("Total de la unidad", por_mina[unidad.nombre], medida=DOLARES))
            for componente, valores in por_componente.get(unidad.nombre, {}).items():
                series.append(_serie(componente, valores, medida=DOLARES))
            if series:
                secciones.append(SeccionDelBloque(titulo=titulo, series=series))
        if secciones:
            grupos.append(GrupoDelBloque(titulo=unidad.nombre, secciones=secciones))
    return BloqueDeCorrida(
        clave="depreciacion",
        etiqueta="Depreciacion",
        titulo="Depreciación tributaria y financiera",
        hoja="Depreciacion",
        grupos=grupos,
    )


def _bloque_de_ventas(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    resultado = corrida.resultado
    caminos = [
        _serie("Ventas del caso", resultado.ventas, medida=DOLARES),
        *(
            _serie(camino, valores, medida=DOLARES)
            for camino, valores in resultado.ventas_por_camino.items()
        ),
    ]
    grupos = [GrupoDelBloque(titulo="", secciones=_una_seccion(caminos))]
    for unidad in resultado.caso.unidades:
        series: list[SerieAnual] = []
        if unidad.nombre in resultado.ventas_por_unidad:
            series.append(
                _serie("Ventas", resultado.ventas_por_unidad[unidad.nombre], medida=DOLARES)
            )
        if unidad.nombre in resultado.concentrado_liquidado_por_unidad:
            series.append(
                _serie(
                    "Concentrado liquidado",
                    resultado.concentrado_liquidado_por_unidad[unidad.nombre],
                    medida=DOLARES,
                )
            )
        for metal, valores in resultado.volumen_pagable_por_unidad.get(unidad.nombre, {}).items():
            series.append(_serie(f"Volumen pagable {metal}", valores, medida="t"))
        if series:
            grupos.append(GrupoDelBloque(titulo=unidad.nombre, secciones=_una_seccion(series)))
    return BloqueDeCorrida(
        clave="ventas",
        etiqueta="Ventas",
        titulo="Los tres caminos de ingreso",
        hoja="Ventas",
        grupos=grupos,
    )


def _bloque_de_otros(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    resultado = corrida.resultado
    capital = [
        _serie("Bolsa de egresos", resultado.bolsa_de_egresos, medida=DOLARES),
        _serie(
            "Variación del capital de trabajo", resultado.variacion_capital_trabajo, medida=DOLARES
        ),
        _serie("Cuentas por cobrar", resultado.cuentas_por_cobrar.saldos, medida=DOLARES),
        _serie(
            "Cuentas por cobrar, variación",
            resultado.cuentas_por_cobrar.variaciones,
            medida=DOLARES,
        ),
        _serie("Cuentas por pagar", resultado.cuentas_por_pagar.saldos, medida=DOLARES),
        _serie(
            "Cuentas por pagar, variación", resultado.cuentas_por_pagar.variaciones, medida=DOLARES
        ),
    ]
    igv = [
        _serie(_bonito(nombre), valores, medida=DOLARES, concepto=nombre)
        for nombre, valores in _series_de(resultado.igv).items()
    ]
    return BloqueDeCorrida(
        clave="otros",
        etiqueta="Otros",
        titulo="Bolsa de egresos, IGV y capital de trabajo",
        hoja="Otros",
        grupos=[
            GrupoDelBloque(
                titulo="",
                secciones=[
                    SeccionDelBloque(titulo="Capital de trabajo", series=capital),
                    SeccionDelBloque(titulo="IGV", series=igv),
                ],
            )
        ],
    )


def _bloque_de_impuestos(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    """La hoja entera, con el signo del libro.

    Ventas positivas y gastos negativos, de modo que cada total es literalmente
    la suma de las filas que tiene encima. Es lo que se contrasta.
    """
    impuestos = corrida.resultado.impuestos
    secciones = [
        SeccionDelBloque(
            titulo=titulo,
            series=[
                _serie(_bonito(nombre), valores, medida=DOLARES, concepto=nombre)
                for nombre, valores in _series_de(sub_bloque).items()
            ],
        )
        for titulo, sub_bloque in (
            ("Regalías e IEM", impuestos.regalias),
            ("Renta", impuestos.renta),
            ("Impuesto a la renta", impuestos.impuesto_a_la_renta),
            ("Pérdida tributaria", impuestos.perdida_tributaria),
        )
    ]
    return BloqueDeCorrida(
        clave="impuestos",
        etiqueta="Impuestos",
        titulo="Regalías, renta e impuesto",
        hoja="Impuestos",
        grupos=[GrupoDelBloque(titulo="", secciones=secciones)],
    )


def _bloque_de_flujo(corrida: CorridaAlmacenada) -> BloqueDeCorrida:
    flujo = corrida.resultado.flujo
    return BloqueDeCorrida(
        clave="flujo",
        etiqueta="FC NZ",
        titulo="Flujo operativo, de inversiones y económico",
        hoja="FC NZ",
        grupos=_un_grupo(
            [
                _serie("EBITDA ajustado", flujo.ebitda_ajustado, medida=DOLARES),
                _serie("Flujo operativo", flujo.flujo_operativo, medida=DOLARES),
                _serie("Flujo de inversiones", flujo.flujo_de_inversiones, medida=DOLARES),
                _serie("Flujo económico", flujo.flujo_economico, medida=DOLARES),
            ]
        ),
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
