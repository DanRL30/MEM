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

**La refinería no es una hoja.** Vive dentro de `InputsProd`, después de las
unidades mineras, y la hoja no termina ahí: cierra con `Venta Sn Spot`.

**Qué se oculta lo decide el motor.** `campos_con_dato_por_unidad` viaja tal cual
hasta la pantalla. Si cada vista resolviera por su cuenta qué filas están vacías,
dos pantallas mostrarían cosas distintas del mismo caso.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import fields as campos_de
from typing import Any

from minsur_engine.capex import (
    CapitalDeUnidad,
    capex_de_etapa,
    capex_total,
    desglosar_por_etapa_y_naturaleza,
)
from minsur_engine.cash_cost import (
    GESTION_SOCIAL_DEDUCIBLE,
    PLANILLA,
    SERVIDUMBRES,
    cash_cost_unitario,
)
from minsur_engine.caso import UnidadProductiva
from minsur_engine.corroboracion import series_calculadas
from minsur_engine.horizonte import Serie, anos_con_dato
from minsur_engine.refineria import BloqueDeLaRefineria
from minsur_ingest.capex import (
    CON_DATO_DE_CAPEX,
    MEDIDA as MEDIDA_CAPEX,
)
from minsur_ingest.opex import (
    CON_DATO_DE_CASH_COST,
    FILAS_DE_CASH_COST,
    FILAS_DE_GASTOS,
    FILAS_DE_OPEX,
    MEDIDA as MEDIDA_OPEX,
)
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

# El libro carga una sola clasificación del capital, la contable, y deriva la
# etapa de ella. Su fila de cuadre comparaba dos sumas que salían de celdas
# distintas; aquí salen de la misma, de modo que cuadra siempre.
NOTA_DEL_CUADRE_DEL_CAPITAL = (
    "Fila de cuadre del libro. Con una sola clasificación cargada se cumple por "
    "construcción: vale cero salvo que el capital se arme a mano."
)

# El libro da a los equipos de cómputo el mismo código contable que a la
# maquinaria, de modo que su cruce por naturaleza los muestra sumados. El motor
# los lleva por separado en las dos vías de depreciación, y esta hoja también.
NOTA_DEL_COMPUTO = (
    "El libro suma este componente con la maquinaria, porque comparten código "
    "contable. La plataforma lo lleva aparte: lo que llega sumado no se separa."
)

# Las series monetarias del motor están en dólares. El libro lleva varias de sus
# hojas en miles, pero la conversión es de la ingesta al entrar y no se deshace
# al salir: la pantalla muestra la unidad en la que el dato realmente está.
DOLARES = "US$"

# Lo que tiene sentido sumar a lo largo del horizonte. Una ley no: se pondera
# por el tonelaje de su fila, que es como el propio libro consolida las leyes de
# dos corrientes. Un ratio -un costo por tonelada- no tiene total.
SUMABLES = frozenset({"t", "tt", "tmf", "kt", "$", "$k", "k$", "us$", "mus$", "miles de us$"})
PONDERADAS = frozenset({"%", "oz/t", "g/t"})

# Los diez conceptos que MINSUR pide ver siempre, aunque la unidad los tenga en
# cero: son la estructura base de un bloque de cash cost, y con ellos fijos los
# conceptos caen en la misma linea en todas las unidades. Los que vienen detras
# -los propios de la refineria y los de una unidad concreta- se ocultan si estan
# en cero todo el horizonte.
#
# Se toman del catalogo y no se escriben aqui, de modo que la etiqueta sea
# exactamente la de la plantilla. `test_la_estructura_base_del_cash_cost` fija
# cuales son: si el catalogo se reordena, esa prueba falla en vez de cambiar en
# silencio lo que se ve.
BASE_DEL_CASH_COST = tuple(fila.etiqueta for fila in CON_DATO_DE_CASH_COST[:10])


def _rotulo_de_refineria(nombre: str) -> str:
    """`Refinería Pisco` a partir de una unidad llamada `Pisco`.

    El nombre de la unidad lo pone el caso y aquí no se incrusta ninguno: el
    motor, la ingesta y la API no mencionan una sola unidad de MINSUR, y esta
    pantalla tampoco. Si el caso ya la llama refinería, el rótulo es el suyo y
    no se le antepone nada.
    """
    if "refiner" in nombre.casefold():
        return nombre
    return f"Refinería {nombre}"


def _tiene_dato(valores: Sequence[float] | None) -> bool:
    """Una fila entera en cero no se muestra, como en el resto de la hoja."""
    return valores is not None and any(valores)


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


def _acumulado(valores: Sequence[float], medida: str, peso: Sequence[float] | None) -> float | None:
    """El total del horizonte, cuando significa algo.

    Un tonelaje o un importe se suman. Una ley se pondera por el tonelaje de su
    fila: es como el libro consolida la ley de dos corrientes, y sumarla daría
    la suma de treinta y seis porcentajes, que no es nada. Un ratio sin tonelaje
    con el que ponderar se queda sin total.
    """
    unidad = medida.strip().lower()
    if unidad in SUMABLES:
        return sum(valores)
    if unidad in PONDERADAS and peso is not None:
        base = sum(peso[: len(valores)])
        if base == 0.0:
            return 0.0
        return sum(v * peso[i] for i, v in enumerate(valores) if i < len(peso)) / base
    return None


def _serie(
    etiqueta: str,
    valores: Sequence[float],
    *,
    medida: str = "",
    concepto: str = "",
    codigo: str = "",
    origen: str = "calculada",
    recalculada: list[float] | None = None,
    total: bool = False,
    peso: Sequence[float] | None = None,
    nota: str | None = None,
) -> SerieAnual:
    return SerieAnual(
        acumulado=_acumulado(valores, medida, peso),
        etiqueta=etiqueta,
        medida=medida,
        concepto=concepto,
        codigo=codigo,
        valores=[float(v) for v in valores],
        origen="dato" if origen == "dato" else "calculada",
        recalculada=recalculada,
        total=total,
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
        tonelaje: Sequence[float] | None = None

        for fila in FILAS_DE_PRODUCCION:
            if fila.es_seccion:
                abierta = SeccionDelBloque(titulo=fila.etiqueta, series=[])
                secciones.append(abierta)
                continue
            valores = getattr(unidad.produccion, fila.campo)
            # La ley se pondera por el tonelaje de su fila. En el libro van en
            # pares -un tonelaje y su ley debajo- y esa posicion es lo unico que
            # las relaciona: la etiqueta `Ley Sn` se repite cinco veces.
            if (fila.medida or "") in PONDERADAS:
                peso = tonelaje
            else:
                peso = None
                tonelaje = valores
            if fila.campo not in con_dato or abierta is None:
                continue
            abierta.series.append(
                _serie(
                    fila.etiqueta,
                    valores,
                    medida=fila.medida or "",
                    concepto=fila.campo,
                    origen="dato",
                    recalculada=recalculo.get(fila.campo) if fila.calculada else None,
                    peso=peso,
                )
            )

        con_filas = [seccion for seccion in secciones if seccion.series]
        if con_filas:
            grupos.append(GrupoDelBloque(titulo=unidad.nombre, secciones=con_filas))

    return grupos


def _grupo_de_la_refineria(refineria: BloqueDeLaRefineria, nombre: str) -> GrupoDelBloque:
    """El bloque de la refinería, en el orden de las filas 90 a 106 del libro.

    Ninguna fila es un dato: la refinería no lleva pestaña de producción porque
    todo lo suyo sale del concentrado que le entregan las minas.

    **Las dos leyes consolidadas se ponderan por el concentrado entregado, no
    por el alimentado**, que es el denominador que el libro escribe en su fila
    101. La diferencia solo se ve cuando la refinería satura: pesando por lo
    alimentado, un ejercicio en que no entra nada dejaría la ley del horizonte
    en cero aunque cada ejercicio tuviera la suya.
    """
    series: list[SerieAnual] = []

    # Cinco pares alimentado/ley, uno por origen, en el orden de las minas. Cada
    # ley se totaliza ponderada por el concentrado de su propia fila.
    #
    # **Estas filas son lo que cada unidad entrega, sin acotar por la capacidad**,
    # y por eso no suman el consolidado de mas abajo cuando la refineria satura:
    # ese es el `MIN` que el libro escribe en su fila 100. Lo que se queda fuera
    # aparece integro en `Venta Sn Spot`, y la fila `Check` cierra las dos.
    for aporte in refineria.aportes:
        series.append(
            _serie(f"Concentrado Alimentado {aporte.unidad}", aporte.concentrado, medida="t")
        )
        series.append(
            _serie(
                f"Ley de Sn en Concentrado {aporte.unidad}",
                aporte.ley,
                medida="%",
                peso=aporte.concentrado,
            )
        )

    series.extend(
        [
            _serie("Concentrado Alimentado", refineria.concentrado_alimentado, medida="t"),
            _serie(
                "Ley de Sn en Concentrado",
                refineria.ley_de_alimentacion,
                medida="%",
                peso=refineria.concentrado_entregado,
            ),
            _serie("Toneladas Alimentadas+escoria", refineria.toneladas_alimentadas, medida="t"),
            _serie(
                "Ley Promedio de Alimentación",
                refineria.ley_de_alimentacion,
                medida="%",
                peso=refineria.concentrado_entregado,
            ),
        ]
    )

    # La recuperación se pondera por lo que cada origen entrega: una recuperación
    # media sin pesar por el concentrado daría el mismo valor a una unidad que
    # aporta el ochenta por ciento y a otra que aporta el dos.
    for aporte in refineria.aportes:
        series.append(
            _serie(
                f"Recuperación Sn {aporte.unidad}",
                aporte.recuperacion,
                medida="%",
                peso=aporte.concentrado,
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
                _serie(
                    "Ley Promedio de Alimentación",
                    refineria.ley_del_excedente,
                    medida="%",
                    peso=refineria.concentrado_excedente,
                ),
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
        grupos.append(
            _grupo_de_la_refineria(resultado.refineria, _rotulo_de_refineria(refineria.nombre))
        )
        grupos.append(_grupo_de_venta_spot(resultado.refineria))
    return BloqueDeCorrida(
        clave="produccion",
        etiqueta="InputsProd",
        titulo="Producción, refinería y venta spot",
        hoja="InputsProd",
        grupos=grupos,
    )


# --- El resto de las hojas ----------------------------------------------------


def _serie_unitaria(costo: Sequence[float], base: Sequence[float]) -> list[float]:
    """Costo por tonelada, ejercicio a ejercicio.

    Divide con la función del motor y no con un operador: con cero toneladas
    devuelve cero, que es lo que hace el libro con su `IFERROR`.
    """
    return [
        cash_cost_unitario(valor, base[i] if i < len(base) else 0.0)
        for i, valor in enumerate(costo)
    ]


def _se_muestra(etiqueta: str, valores: Sequence[float] | None) -> bool:
    """Los diez de la base siempre; el resto solo si la unidad los usa."""
    return etiqueta in BASE_DEL_CASH_COST or _tiene_dato(valores)


def _o_en_ceros(valores: Sequence[float] | None, anos: int) -> Sequence[float]:
    """Una fila de la base sin dato se dibuja igual, con su guion en cada año."""
    return valores if valores else (0.0,) * anos


def _grupos_de_cash_cost(corrida: CorridaAlmacenada, anos: int) -> list[GrupoDelBloque]:
    """Un bloque por unidad, con la estructura completa del libro.

    Los diez conceptos de `BASE_DEL_CASH_COST` aparecen siempre, con su guion si
    están en cero: son la estructura que MINSUR quiere ver en todos los bloques.

    **Los demás se ocultan si están en cero todo el horizonte**, y eso es lo que
    hace que cada unidad muestre los suyos. El libro tiene bloques de distinta
    altura —una mina lleva diez filas y la refinería otras nueve, distintas— y
    la plantilla no puede: emite la misma estructura para todas, porque tiene
    que servir a un proyecto que hoy no existe. Ocultar lo vacío recupera esa
    lista por unidad sin decidir aquí qué concepto es de quién.
    """
    resultado = corrida.resultado
    del_catalogo = {fila.etiqueta for fila in FILAS_DE_OPEX if not fila.es_seccion}
    grupos: list[GrupoDelBloque] = []

    for unidad in resultado.caso.unidades:
        series = [
            _serie(
                fila.etiqueta,
                _o_en_ceros(unidad.costos.get(fila.etiqueta), anos),
                medida=fila.medida or "",
                origen="dato",
            )
            for fila in FILAS_DE_CASH_COST
            if not fila.es_seccion and _se_muestra(fila.etiqueta, unidad.costos.get(fila.etiqueta))
        ]
        series.extend(
            _serie(concepto, valores, medida=MEDIDA_OPEX, origen="dato")
            for concepto, valores in unidad.costos.items()
            if concepto not in del_catalogo and _tiene_dato(valores)
        )
        total = resultado.cash_cost_por_unidad.get(unidad.nombre)
        if total is not None:
            series.append(_serie(f"Total {unidad.nombre}", total, medida=MEDIDA_OPEX, total=True))
        grupos.append(
            GrupoDelBloque(titulo=f"Cash Cost - {unidad.nombre}", secciones=_una_seccion(series))
        )

    return grupos


def _grupo_de_supuestos_de_la_refineria(corrida: CorridaAlmacenada) -> list[GrupoDelBloque]:
    """El reparto del costo de la refinería por origen. Es la regla `079`.

    El libro cobra la refinería de dos maneras: los orígenes de su bloque
    directo llevan los conceptos de la propia planta, y el resto se cobra a una
    tarifa por tonelada fina aplicada a lo que refina cada uno.

    Cada unidad declara por cuál va: la que marca `costo_directo_en_la_refineria`
    ya lleva su costo en los conceptos del bloque, y no sale aquí. La lista no se
    escribe en el código: la declara el caso, unidad a unidad.

    **Se informa y no entra al flujo.** Sumarlo al cash cost cambia el NPV, y esa
    es una decisión de Finanzas que la regla `079` deja abierta.
    """
    resultado = corrida.resultado
    refineria = resultado.caso.refineria
    tarifa = resultado.caso.datos_comunes.costo_de_fundicion
    if refineria is None or not _tiene_dato(tarifa):
        return []

    series = [
        _serie("Costo / tmf", tarifa, medida="$/tmf", origen="dato"),
        _serie("Recuperación Pisco", resultado.refineria.refinado, medida="tmf"),
    ]
    directos = {
        unidad.nombre for unidad in resultado.caso.unidades if unidad.costo_directo_en_la_refineria
    }
    por_tarifa = [a for a in resultado.refineria.aportes if a.unidad not in directos]
    for aporte in por_tarifa:
        series.append(
            _serie(
                f"Sub total {refineria.nombre} {aporte.unidad}",
                [tarifa[i] * fina for i, fina in enumerate(aporte.refinado[: len(tarifa)])],
                medida=MEDIDA_OPEX,
            )
        )
    directo = resultado.cash_cost_por_unidad.get(refineria.nombre, ())
    total = [
        (directo[i] if i < len(directo) else 0.0)
        + sum(tarifa[i] * a.refinado[i] for a in por_tarifa if i < len(a.refinado))
        for i in range(len(tarifa))
    ]
    series.append(_serie(f"Total {refineria.nombre}", total, medida=MEDIDA_OPEX, total=True))

    return [
        GrupoDelBloque(
            titulo=f"Supuestos {_rotulo_de_refineria(refineria.nombre)}",
            secciones=_una_seccion(series),
        )
    ]


def _grupo_de_produccion_y_unitarios(corrida: CorridaAlmacenada, anos: int) -> list[GrupoDelBloque]:
    """Lo que el libro calcula debajo de los bloques: producción y costo unitario.

    Ninguna de estas filas es un dato. Salen de dividir lo que ya está arriba
    entre lo que la unidad trata o produce, con la función del motor.
    """
    resultado = corrida.resultado
    tratado = resultado.mineral_tratado_por_unidad

    produccion: list[SerieAnual] = []
    for unidad in resultado.caso.unidades:
        if unidad.nombre in tratado:
            produccion.append(
                _serie(f"Toneladas Tratadas {unidad.nombre}", tratado[unidad.nombre], medida="tt")
            )
    for unidad in resultado.caso.unidades:
        finas = unidad.produccion.toneladas_finas
        if _tiene_dato(finas):
            produccion.append(_serie(f"Producción {unidad.nombre}", finas, medida="tmf"))

    # El costo por tonelada tratada se calcula **una sola vez**, no por unidad:
    # el modelo lo hace sobre la unidad cuyo cash cost se analiza por tonelada
    # tratada. Se ancla a la primera del caso que trate mineral, que en las
    # evaluaciones de MINSUR es San Rafael. No se escribe aqui que unidad es:
    # un caso que declare otra en primer lugar la usaria a ella.
    ancla = next(
        (u for u in resultado.caso.unidades if _tiene_dato(tratado.get(u.nombre))),
        None,
    )
    unitarios: list[SerieAnual] = []
    if ancla is not None:
        base = tratado[ancla.nombre]
        unitarios = [
            _serie(
                fila.etiqueta,
                _serie_unitaria(_o_en_ceros(ancla.costos.get(fila.etiqueta), anos), base),
                medida="$/tt",
            )
            for fila in FILAS_DE_CASH_COST
            if not fila.es_seccion and _se_muestra(fila.etiqueta, ancla.costos.get(fila.etiqueta))
        ]
        total_del_ancla = resultado.cash_cost_por_unidad.get(ancla.nombre)
        if total_del_ancla is not None:
            unitarios.append(
                _serie(
                    f"Total {ancla.nombre} / tt",
                    _serie_unitaria(total_del_ancla, base),
                    medida="$/tt",
                    total=True,
                )
            )

    # El costo por tonelada fina, en cambio, si va unidad por unidad, y cierra
    # con el total del caso sobre lo que refina la refineria.
    por_fina = []
    for unidad in resultado.caso.unidades:
        # Las finas de la refinería no son una serie cargada: son lo que refina,
        # y el motor las calcula. Sin esta rama su fila no saldría, y el modelo
        # sí la tiene.
        finas = (
            resultado.refineria.refinado
            if unidad.es_refineria
            else unidad.produccion.toneladas_finas
        )
        total = resultado.cash_cost_por_unidad.get(unidad.nombre)
        if total is None or not _tiene_dato(finas):
            continue
        por_fina.append(
            _serie(
                f"Cash Cost {unidad.nombre} / tmf",
                _serie_unitaria(total, finas),
                medida="$/tmf",
                total=True,
            )
        )
    refineria = resultado.caso.refineria
    if refineria is not None and _tiene_dato(resultado.refineria.refinado):
        por_fina.append(
            _serie(
                f"Total Cash Cost {refineria.nombre} / tmf",
                _serie_unitaria(resultado.cash_cost, resultado.refineria.refinado),
                medida="$/tmf",
                total=True,
            )
        )

    grupos = [
        GrupoDelBloque(
            titulo="",
            secciones=_una_seccion(
                [_serie("Total Cash Cost", resultado.cash_cost, medida=MEDIDA_OPEX, total=True)]
            ),
        ),
        GrupoDelBloque(titulo="Producción", secciones=_una_seccion(produccion)),
    ]
    if unitarios:
        grupos.append(
            GrupoDelBloque(
                titulo="Cash cost por tonelada tratada", secciones=_una_seccion(unitarios)
            )
        )
    if por_fina:
        grupos.append(
            GrupoDelBloque(titulo="Cash cost por tonelada fina", secciones=_una_seccion(por_fina))
        )
    return grupos


def _grupos_de_gastos(corrida: CorridaAlmacenada, anos: int) -> list[GrupoDelBloque]:
    """Los gastos, al cierre de la hoja.

    Van al final y no dentro del bloque de cada unidad, que es donde los pone el
    libro: no son cash cost, viven en `UnidadProductiva.gastos` aparte de
    `costos`, y cada fila va a un sitio distinto del flujo.
    """
    grupos: list[GrupoDelBloque] = []
    for unidad in corrida.resultado.caso.unidades:
        # Los gastos van con su estructura completa, con guion en la fila vacia.
        # No es como el cash cost, donde ocultar lo vacio devuelve la lista de
        # conceptos de cada unidad: aqui la lista es la misma para todas y lo
        # que importa es que cada concepto caiga siempre en la misma linea.
        series = [
            _serie(
                fila.etiqueta,
                _o_en_ceros(unidad.gastos.get(fila.etiqueta), anos),
                medida=fila.medida or "",
                origen="dato",
            )
            for fila in FILAS_DE_GASTOS
            if not fila.es_seccion
        ]
        if unidad.gastos:
            grupos.append(
                GrupoDelBloque(titulo=f"Gastos - {unidad.nombre}", secciones=_una_seccion(series))
            )
    return grupos


def _grupo_del_total_de_gastos(corrida: CorridaAlmacenada, anos: int) -> list[GrupoDelBloque]:
    """La tabla con la que el modelo cierra la hoja: los gastos consolidados.

    No es la suma de los bloques de arriba y ya: lleva ademas las dos filas que
    el motor deriva y la plantilla no pide —`Planilla` y `Gestión Social
    Deducible`, las reglas `026` y `027`—, y el libro las muestra en este bloque
    junto a lo cargado.

    El orden es el del catálogo, con la planilla detrás de las servidumbres y la
    gestión social deducible al final, que es donde las pone el modelo.
    """
    resultado = corrida.resultado
    por_unidad = resultado.gastos_por_unidad

    def consolidado(concepto: str) -> list[float] | None:
        aportes = [g[concepto] for g in por_unidad.values() if concepto in g]
        if not aportes:
            return None
        return [sum(s[i] for s in aportes if i < len(s)) for i in range(anos)]

    series: list[SerieAnual] = []
    conceptos = [fila.etiqueta for fila in FILAS_DE_GASTOS if not fila.es_seccion]
    if SERVIDUMBRES in conceptos:
        conceptos.insert(conceptos.index(SERVIDUMBRES) + 1, PLANILLA)
    conceptos.append(GESTION_SOCIAL_DEDUCIBLE)

    # Aquí la estructura va completa, con su guion en la fila vacía: es la tabla
    # de cierre y el modelo la muestra entera, de modo que cada concepto cae
    # siempre en la misma línea.
    for concepto in conceptos:
        series.append(_serie(concepto, consolidado(concepto) or [0.0] * anos, medida=MEDIDA_OPEX))

    if not por_unidad:
        return []
    return [GrupoDelBloque(titulo="Total Gastos", secciones=_una_seccion(series))]


def _bloque_de_opex(corrida: CorridaAlmacenada, anos: int) -> BloqueDeCorrida:
    """La hoja de opex, en el orden del libro.

    Primero el cash cost de cada unidad con su total, después lo que el libro
    calcula debajo —producción, costo por tonelada tratada y por tonelada fina—
    y al final los gastos.

    **Falta el bloque `Supuestos Pisco`**, con el costo por tonelada fina de la
    refinería y sus subtotales por origen. La plataforma no lo modela: reparte
    el costo de la refinería como el de cualquier otra unidad, y los subtotales
    por origen del libro no tienen contraparte.
    """
    return BloqueDeCorrida(
        clave="opex",
        etiqueta="InputsOpex",
        titulo="Cash cost, costo unitario y gastos",
        hoja="InputsOpex",
        grupos=[
            *_grupos_de_cash_cost(corrida, anos),
            *_grupo_de_supuestos_de_la_refineria(corrida),
            *_grupo_de_produccion_y_unitarios(corrida, anos),
            *_grupos_de_gastos(corrida, anos),
            *_grupo_del_total_de_gastos(corrida, anos),
        ],
    )


# Las cinco naturalezas contables, con la etiqueta del libro y el campo del
# motor que las alimenta. Se toman del catalogo de la plantilla y no se escriben
# aqui, de modo que la fila que se ve sea la que el usuario lleno.
NATURALEZAS_DEL_CAPITAL = tuple(
    (fila.etiqueta, fila.naturaleza, fila.codigo) for fila in CON_DATO_DE_CAPEX
)

# Las tres etapas, con el rotulo con que el libro encabeza cada seccion de su
# cruce. La cuarta, que el libro deja rotulada `xxx`, no se emite: no tiene
# formula en ninguna columna de ano y vale cero siempre. Es la regla `032`.
ETAPAS_DEL_CAPITAL = (
    ("inicial", "Por Naturaleza - Inicial"),
    ("sostenimiento", "Por Naturaleza - Sostenimiento"),
    ("cierre", "Por Naturaleza - Cierre"),
)


def _naturaleza_de_la_unidad(unidad: UnidadProductiva, campo: str, anos: int) -> Sequence[float]:
    """Una naturaleza del capital de una unidad, o ceros si no declara capital."""
    if unidad.capital is None:
        return [0.0] * anos
    return _o_en_ceros(unidad.capital.por_naturaleza.get(campo), anos)


def _serie_de_naturaleza(
    etiqueta: str, campo: str, codigo: str, valores: Sequence[float]
) -> SerieAnual:
    """Una fila del cruce, con su código y su aviso si el libro la lleva sumada.

    El código de tres letras es la columna A del libro y no es decorativo: es la
    clave con la que sus `SUMIF` construyen todo lo derivado de esta hoja. Que
    dos filas compartan `MAQ` es lo que explica que el libro fusione los equipos
    de cómputo con la maquinaria justo donde la plataforma los separa, de modo
    que verlo en pantalla ahorra la pregunta.
    """
    return _serie(
        etiqueta,
        valores,
        medida=MEDIDA_CAPEX,
        concepto=campo,
        codigo=codigo,
        nota=NOTA_DEL_COMPUTO if campo == "equipos_de_computo" else None,
    )


def _suma(series: Sequence[Sequence[float]], anos: int) -> list[float]:
    return [sum(s[i] for s in series if i < len(s)) for i in range(anos)]


def _con_su_total(series: list[SerieAnual], anos: int) -> list[SerieAnual]:
    """Cierra un bloque con su fila de total, sombreada como en el libro."""
    return [
        *series,
        _serie("Total", _suma([s.valores for s in series], anos), medida=MEDIDA_CAPEX, total=True),
    ]


def _grupo_del_detalle_del_capital(
    corrida: CorridaAlmacenada, capital: Sequence[CapitalDeUnidad], anos: int
) -> GrupoDelBloque:
    """`Detalle Capex`: la etapa, que es lo que ve el flujo de inversiones.

    Abre la hoja aunque sea cálculo, porque así abre el libro: quien evalúa un
    proyecto mira primero cuánto es inicial y cuánto sostenimiento, y el detalle
    por unidad está debajo para explicarlo.

    **Sin la fila `Tipo vs Detalle` del libro**, que restaba este total de la
    suma de los totales por unidad. Allí compara dos sumas que vienen de celdas
    distintas y puede descuadrar; aquí las dos salen de la misma clasificación
    cargada, de modo que la fila era un cero constante ocupando una línea.
    """
    horizonte = corrida.resultado.caso.horizonte
    series = [
        _serie("Capex Inicial", capex_de_etapa(horizonte, capital, "inicial"), medida=MEDIDA_CAPEX),
        _serie(
            "Sostenimiento",
            capex_de_etapa(horizonte, capital, "sostenimiento"),
            medida=MEDIDA_CAPEX,
        ),
        _serie("Cierre Mina", capex_de_etapa(horizonte, capital, "cierre"), medida=MEDIDA_CAPEX),
        _serie("Total", capex_total(horizonte, capital), medida=MEDIDA_CAPEX, total=True),
    ]
    return GrupoDelBloque(titulo="Detalle Capex", secciones=_una_seccion(series))


def _grupos_de_la_clasificacion(corrida: CorridaAlmacenada, anos: int) -> list[GrupoDelBloque]:
    """`Clasificación <unidad>`: lo único que esta hoja carga.

    La estructura va completa en todas las unidades, con su guion en la fila
    vacía, que es como la lleva el libro: las cinco naturalezas son la misma
    lista para todas y lo que importa es que cada concepto caiga siempre en la
    misma línea. Una unidad sin capital declarado lleva su bloque en ceros.
    """
    grupos = []
    for unidad in corrida.resultado.caso.unidades:
        series = [
            _serie(
                etiqueta,
                _naturaleza_de_la_unidad(unidad, campo, anos),
                medida=MEDIDA_CAPEX,
                concepto=campo,
                codigo=codigo,
                origen="dato",
                nota=NOTA_DEL_COMPUTO if campo == "equipos_de_computo" else None,
            )
            for etiqueta, campo, codigo in NATURALEZAS_DEL_CAPITAL
        ]
        grupos.append(
            GrupoDelBloque(
                titulo=f"Clasificación {unidad.nombre}",
                secciones=_una_seccion(_con_su_total(series, anos)),
            )
        )
    return grupos


def _desglose_de(
    corrida: CorridaAlmacenada, unidad: UnidadProductiva
) -> dict[str, dict[str, Serie]]:
    """El cruce de una unidad, derivado con la regla de etapa del motor.

    Se le pide al motor en vez de deducirlo del capital ya clasificado: la regla
    que decide si un ejercicio es inicial o de sostenimiento vive en un solo
    sitio, y rehacerla aquí la pondría en dos.
    """
    if unidad.capital is None:
        return {}
    return desglosar_por_etapa_y_naturaleza(
        corrida.resultado.caso.horizonte,
        unidad.capital.por_naturaleza,
        anos_activos=anos_con_dato(unidad.produccion.mineral_tratado),
        umbral_inicial=unidad.umbral_de_capital_inicial,
    )


def _cruce_consolidado(corrida: CorridaAlmacenada, anos: int) -> dict[str, dict[str, Serie]]:
    consolidado: dict[str, dict[str, list[float]]] = {}
    for unidad in corrida.resultado.caso.unidades:
        for etapa, filas in _desglose_de(corrida, unidad).items():
            destino = consolidado.setdefault(etapa, {})
            for campo, serie in filas.items():
                acumulada = destino.setdefault(campo, [0.0] * anos)
                for i, valor in enumerate(serie[:anos]):
                    acumulada[i] += valor
    return {
        etapa: {campo: tuple(serie) for campo, serie in filas.items()}
        for etapa, filas in consolidado.items()
    }


def _secciones_del_cruce(
    desglose: dict[str, dict[str, Serie]], anos: int
) -> list[SeccionDelBloque]:
    """Las tres etapas del cruce, cada una con sus cinco naturalezas.

    El cruce es disperso y no es un hueco: lo no depreciable solo aparece en
    cierre, y ninguna otra naturaleza aparece ahí. Las filas van igual, porque
    es la forma de la hoja y porque un cero dice algo distinto de una fila que
    falta.
    """
    secciones = []
    for etapa, titulo in ETAPAS_DEL_CAPITAL:
        filas = desglose.get(etapa, {})
        series = [
            _serie_de_naturaleza(etiqueta, campo, codigo, _o_en_ceros(filas.get(campo), anos))
            for etiqueta, campo, codigo in NATURALEZAS_DEL_CAPITAL
        ]
        secciones.append(SeccionDelBloque(titulo=titulo, series=_con_su_total(series, anos)))
    return secciones


def _grupos_del_cruce(corrida: CorridaAlmacenada, anos: int) -> list[GrupoDelBloque]:
    """`Capex por Naturaleza`: el consolidado y el desglose de cada proyecto.

    El libro reparte este bloque en dos juegos, uno general y otro propio de un
    proyecto, y **excluye ese proyecto del general** porque alimenta una hoja de
    flujo aparte. La plataforma evalúa un flujo: el consolidado recoge todas las
    unidades y el bloque del proyecto es un desglose dentro de él, no una vía
    paralela. Es lo que hace que las dos filas de cuadre cierren en cero.

    Unidad de proyecto es la que declara `umbral_de_capital_inicial`, la misma
    definición con la que el motor decide la etapa. Aquí no se cablea el nombre
    de ninguna unidad de MINSUR.
    """
    grupos = [
        GrupoDelBloque(
            titulo="Capex por Naturaleza",
            secciones=_secciones_del_cruce(_cruce_consolidado(corrida, anos), anos),
        )
    ]
    for unidad in corrida.resultado.caso.unidades:
        if unidad.umbral_de_capital_inicial is None:
            continue
        grupos.append(
            GrupoDelBloque(
                titulo=f"Capex por Naturaleza - {unidad.nombre}",
                secciones=_secciones_del_cruce(_desglose_de(corrida, unidad), anos),
            )
        )
    return grupos


def _grupo_del_total_por_naturaleza(
    corrida: CorridaAlmacenada, capital: Sequence[CapitalDeUnidad], anos: int
) -> GrupoDelBloque:
    """`Por Naturaleza - Total`, con el `check` que cierra la hoja.

    Es el único bloque de naturalezas sin código a la izquierda, y así lo lleva
    el libro: aquí no se agrupa nada, se suman las tres etapas que los `SUMIF`
    ya construyeron.
    """
    consolidado = _cruce_consolidado(corrida, anos)
    series = [
        _serie_de_naturaleza(
            etiqueta,
            campo,
            "",
            _suma([filas.get(campo, ()) for filas in consolidado.values()], anos),
        )
        for etiqueta, campo, _codigo in NATURALEZAS_DEL_CAPITAL
    ]
    con_total = _con_su_total(series, anos)
    total = con_total[-1].valores
    del_detalle = capex_total(corrida.resultado.caso.horizonte, capital)
    con_total.append(
        _serie(
            "check",
            [v - (del_detalle[i] if i < len(del_detalle) else 0.0) for i, v in enumerate(total)],
            medida=MEDIDA_CAPEX,
            nota=NOTA_DEL_CUADRE_DEL_CAPITAL,
        )
    )
    return GrupoDelBloque(titulo="Capex por Naturaleza TOTAL", secciones=_una_seccion(con_total))


def _bloque_de_capex(corrida: CorridaAlmacenada, anos: int) -> BloqueDeCorrida:
    """La hoja del capital, en el orden del libro.

    Abre con la etapa consolidada, sigue con la clasificación contable de cada
    unidad —que es lo único que la hoja carga— y cierra con el cruce de las dos
    clasificaciones y su total.

    Las cifras van en `$k`, que es como el libro lleva esta hoja y como la
    ingesta la lee. El motor guarda dólares porque convierte al entrar; aquí se
    rotula la unidad del libro y la pantalla deshace la conversión, igual que en
    opex.
    """
    capital = list(corrida.resultado.capital_por_unidad)
    return BloqueDeCorrida(
        clave="capex",
        etiqueta="InputsCapex",
        titulo="Capital por etapa y naturaleza contable",
        hoja="InputsCapex",
        grupos=[
            _grupo_del_detalle_del_capital(corrida, capital, anos),
            *_grupos_de_la_clasificacion(corrida, anos),
            *_grupos_del_cruce(corrida, anos),
            _grupo_del_total_por_naturaleza(corrida, capital, anos),
        ],
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
            _bloque_de_opex(corrida, len(anios)),
            _bloque_de_capex(corrida, len(anios)),
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
