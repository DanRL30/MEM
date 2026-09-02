"""La estructura estándar de una pestaña de OPEX, y su lectura.

**Hay una sola estructura y es siempre la misma**, como en producción: una
unidad sin planta de preconcentración deja esa fila en cero y la plataforma no
la muestra. Es lo que permite cargar un proyecto que hoy no existe en el libro.

El bloque de la hoja `InputsOpex` es **todo dato**. Lo que el libro calcula ahí
—los totales, el costo por tonelada, los subtotales del complejo y la producción
que trae de `InputsProd`— no se pide: la plataforma lo calcula. Por eso esta
plantilla no lleva filas corroborables y no hay recálculo que contrastar contra
lo cargado, a diferencia de la de producción.

Tres conceptos que el libro escribe como filas tampoco se piden, porque los
deriva: `Planilla` sale del cash cost de la unidad por la tasa de los supuestos,
`Gestión Social Deducible` es la parte de la gestión social que admite la base
imponible, y `Año con operación` es una bandera sobre el total. Pedirlas
invitaría a que contradijeran a su origen.

Las etiquetas y el orden son los del libro, salvo donde el rótulo lleva el
nombre propio de una unidad —`Tratamiento de Relaves B2`— o donde abrevia
—`LT`—. Un proyecto nuevo no cabe en el primer caso y nadie reconoce el segundo;
la tabla de sinónimos traduce ambos.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from minsur_engine.cash_cost import (
    ESTUDIOS_CAPITALIZABLES,
    ESTUDIOS_DE_GASTO,
    EXPLORACIONES,
    GASTOS_ADMINISTRATIVOS,
    GESTION_SOCIAL,
    PREDIOS,
    SERVIDUMBRES,
)
from minsur_engine.caso import Caso
from minsur_engine.horizonte import Serie
from minsur_ingest.incidencias import Incidencia
from minsur_ingest.sinonimos import equivalente

SECCION = None

MEDIDA = "$k"
"""El libro lleva todo el bloque en miles de dólares. La ingesta los convierte."""

CONCEPTOS_LIBRES = 3
"""Filas de la cola, con concepto a elección del usuario.

El acuerdo 6 de la minuta del 27/08/2026 exige que la lista de conceptos de
opex sea extensible: Santo Domingo tiene costos que ninguna otra unidad tiene y
un proyecto nuevo tendrá los suyos. La cola es de longitud fija y va en un
lugar fijo, que es lo que permite seguir leyendo por secuencia. Lo que se
escriba en ella **solo afecta al total**, que es la condición con que el propio
acuerdo la mantiene contrastable.
"""


@dataclass(frozen=True)
class FilaDeOpex:
    """Una fila de la estructura estándar."""

    etiqueta: str
    medida: str | None
    """`None` marca una fila de sección, que no lleva datos."""

    calculada: bool = False
    """Ninguna lo es, y ese es el punto.

    El escritor de plantillas es común a las tres estructuras y consulta este
    campo para colorear las filas que el sistema rehace. En OPEX no hay ninguna.
    """

    @property
    def es_seccion(self) -> bool:
        return self.medida is SECCION


FILAS_DE_CASH_COST = (
    FilaDeOpex("Cash Cost", SECCION),
    FilaDeOpex("Exploraciones", MEDIDA),
    FilaDeOpex("Geología", MEDIDA),
    FilaDeOpex("Mina", MEDIDA),
    FilaDeOpex("Planta Preconcentración", MEDIDA),
    FilaDeOpex("Planta Concentradora", MEDIDA),
    FilaDeOpex("Mantenimiento", MEDIDA),
    FilaDeOpex("Energía", MEDIDA),
    FilaDeOpex("Apoyo", MEDIDA),
    FilaDeOpex("Estudios y optimizaciones", MEDIDA),
    FilaDeOpex("Relavera", MEDIDA),
    FilaDeOpex("Línea de transmisión", MEDIDA),
    FilaDeOpex("Peajes y mantenimiento", MEDIDA),
    FilaDeOpex("Agua potable", MEDIDA),
    FilaDeOpex("STA", MEDIDA),
    # Los de la refineria. Van en la misma estructura que los demas, no en una
    # plantilla aparte: una mina los deja en cero, como deja en cero la
    # preconcentracion la unidad que no la tiene.
    FilaDeOpex("Fundición", MEDIDA),
    FilaDeOpex("Refinería", MEDIDA),
    FilaDeOpex("Planta de subproductos", MEDIDA),
    FilaDeOpex("Mantenimiento de fundición y refinería", MEDIDA),
)
"""Los conceptos de costo que el usuario carga, uno por unidad.

Tres conceptos del libro quedan fuera por decision del 02/09/2026. Dos son de
Santo Domingo —servicios de mina y preconcentrado de terceros— y el tercero es
la planilla, que **no es un dato**: se deriva del cash cost de la unidad por la
tasa de los supuestos, igual que la parte deducible de la gestion social se
deriva de esta.

Lo que una unidad tenga y no este aqui entra por la cola de conceptos propios,
que para eso existe. Ahi va tambien el `Covid` de la refineria, que es una
reclasificacion de un caso concreto y no un concepto del catalogo.
"""

FILAS_DE_LA_COLA = (
    FilaDeOpex("Otros conceptos", SECCION),
    *(FilaDeOpex("", MEDIDA) for _ in range(CONCEPTOS_LIBRES)),
)

FILAS_DE_GASTOS = (
    FilaDeOpex("Gastos", SECCION),
    FilaDeOpex(GASTOS_ADMINISTRATIVOS, MEDIDA),
    FilaDeOpex(GESTION_SOCIAL, MEDIDA),
    FilaDeOpex(PREDIOS, MEDIDA),
    FilaDeOpex(SERVIDUMBRES, MEDIDA),
    FilaDeOpex(ESTUDIOS_DE_GASTO, MEDIDA),
    FilaDeOpex(ESTUDIOS_CAPITALIZABLES, MEDIDA),
    FilaDeOpex(EXPLORACIONES, MEDIDA),
)

FILAS_DE_OPEX = FILAS_DE_CASH_COST + FILAS_DE_LA_COLA + FILAS_DE_GASTOS

CON_DATO_DE_CASH_COST = tuple(f for f in FILAS_DE_CASH_COST if not f.es_seccion)
CON_DATO_DE_GASTOS = tuple(f for f in FILAS_DE_GASTOS if not f.es_seccion)


class ErrorDeAsociacion(ValueError):
    """Las pestañas del libro de opex no cuadran con las unidades del caso."""


@dataclass(frozen=True)
class OpexDeUnidad:
    """Lo que una pestaña aporta: sus costos y sus gastos."""

    costos: dict[str, Serie] = field(default_factory=dict)
    gastos: dict[str, Serie] = field(default_factory=dict)


def armar_opex(
    filas: Sequence[tuple[str, Serie]],
    incidencias: list[Incidencia],
    *,
    hoja: str,
) -> OpexDeUnidad:
    """Convierte las filas de una pestaña en el opex de su unidad.

    Recorre en paralelo la estructura estándar y la de la hoja, bloque a
    bloque. Una etiqueta que no es la que toca **detiene la lectura de esa
    pestaña y se reporta**: si la secuencia se rompe, seguir leyendo asignaría
    cada serie al concepto de al lado y el caso saldría plausible y equivocado.
    """
    resultado = OpexDeUnidad()
    if not filas:
        # Una pestana vacia no es un error de estructura: es una unidad cuyo
        # costo todavia no se ha cargado.
        return resultado

    leidas = _tomar(
        CON_DATO_DE_CASH_COST,
        filas,
        0,
        resultado.costos,
        incidencias,
        hoja=hoja,
        bloque="cash cost",
    )
    if leidas is None:
        return resultado

    leidas = _tomar_la_cola(filas, leidas, resultado.costos, incidencias, hoja=hoja)
    if leidas is None:
        return resultado

    leidas = _tomar(
        CON_DATO_DE_GASTOS, filas, leidas, resultado.gastos, incidencias, hoja=hoja, bloque="gastos"
    )
    if leidas is None:
        return resultado

    if leidas != len(filas):
        incidencias.append(
            Incidencia(
                hoja,
                filas[leidas][0],
                f"sobran {len(filas) - leidas} fila(s) despues del bloque de gastos, que es el "
                "ultimo de la estructura estandar.",
            )
        )
    return resultado


def _tomar(
    definicion: Sequence[FilaDeOpex],
    filas: Sequence[tuple[str, Serie]],
    desde: int,
    destino: dict[str, Serie],
    incidencias: list[Incidencia],
    *,
    hoja: str,
    bloque: str,
) -> int | None:
    """Consume un bloque de la estructura. Devuelve dónde quedó, o nada si se rompió."""
    for salto, esperada in enumerate(definicion):
        posicion = desde + salto
        if posicion >= len(filas):
            incidencias.append(
                Incidencia(
                    hoja,
                    "-",
                    f"el bloque de {bloque} se corta en {esperada.etiqueta!r}: la pestana no "
                    "trae esa fila.",
                )
            )
            return None
        etiqueta, serie = filas[posicion]
        if equivalente(etiqueta) != equivalente(esperada.etiqueta):
            incidencias.append(
                Incidencia(
                    hoja,
                    etiqueta,
                    f"se esperaba {esperada.etiqueta!r} y hay {etiqueta!r}. La plantilla de opex "
                    "tiene una estructura fija y esta pestana se aparta de ella.",
                )
            )
            return None
        destino[esperada.etiqueta] = serie
    return desde + len(definicion)


def _tomar_la_cola(
    filas: Sequence[tuple[str, Serie]],
    desde: int,
    destino: dict[str, Serie],
    incidencias: list[Incidencia],
    *,
    hoja: str,
) -> int | None:
    """Consume los conceptos propios del proyecto, que van sin catalogar.

    Una fila de la cola que nadie llenó no llega hasta aquí: sin concepto no
    hay fila. Pasada la cuenta de la cola, lo que venga tiene que ser el bloque
    de gastos; si no lo es, se reporta en vez de seguir tragando filas, porque
    tragarlas convertiría un gasto mal escrito en un costo con su nombre.
    """
    empieza_gastos = equivalente(CON_DATO_DE_GASTOS[0].etiqueta)
    posicion = desde
    while posicion < len(filas) and equivalente(filas[posicion][0]) != empieza_gastos:
        etiqueta, serie = filas[posicion]
        if posicion - desde >= CONCEPTOS_LIBRES:
            incidencias.append(
                Incidencia(
                    hoja,
                    etiqueta,
                    f"la cola de conceptos propios admite {CONCEPTOS_LIBRES} filas y aqui hay "
                    f"mas. Despues de ellas se espera {CON_DATO_DE_GASTOS[0].etiqueta!r}.",
                )
            )
            return None
        destino[etiqueta.strip()] = serie
        posicion += 1
    return posicion


def aplicar(caso: Caso, bloques: Sequence[OpexDeUnidad]) -> Caso:
    """Vuelca el opex leído sobre las unidades del caso, en orden.

    **El complejo entra en la cuenta**, a diferencia del libro de producción,
    que lo excluye porque sus toneladas son resultado. Aquí su costo es un dato
    como el de cualquier otra unidad, de modo que el libro de opex trae una
    pestaña más que el de producción.
    """
    if len(bloques) != len(caso.unidades):
        raise ErrorDeAsociacion(
            f"El libro de opex trae {len(bloques)} pestana(s) y el caso declara "
            f"{len(caso.unidades)} unidad(es), incluido el complejo. Asociarlas por orden exige "
            "que sean tantas como unidades: sobra o falta un proyecto."
        )
    return replace(
        caso,
        unidades=tuple(
            replace(unidad, costos=bloque.costos, gastos=bloque.gastos)
            for unidad, bloque in zip(caso.unidades, bloques, strict=True)
        ),
    )
