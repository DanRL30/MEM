"""La estructura estándar de una pestaña de CAPEX, y su lectura.

**El capital se pide una sola vez y por naturaleza contable.** Es lo único que
el libro carga: la disección de `InputsCapex` del 02/09/2026 no encontró en toda
la hoja una sola constante tecleada, y la clasificación por unidad es el único
bloque que llega de fuera. Todo lo demás —la etapa, el cruce etapa por
naturaleza, los totales y los dos `check`— lo calcula el propio libro a partir de
ella, y aquí lo calcula el motor.

Por eso esta plantilla no lleva filas corroborables: no hay dos valores que
comparar, igual que en opex.

Cinco filas y cinco componentes. El libro junta los equipos de cómputo con la
maquinaria bajo un solo código para depreciar, y la plataforma **no los
consolida**: cada componente se deprecia y se informa por separado, para que un
proyecto nuevo con componentes que hoy no existen tenga el suyo sin deshacer una
suma. Mientras Finanzas no confirme una tasa propia para el cómputo, se usa la de
maquinaria, que es lo que el libro hace de hecho.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from minsur_engine.capex import CapitalDeUnidad, clasificar_por_etapa
from minsur_engine.caso import Caso, UnidadProductiva
from minsur_engine.horizonte import Horizonte, Serie, anos_con_dato
from minsur_ingest.incidencias import Incidencia
from minsur_ingest.sinonimos import equivalente

SECCION = None

MEDIDA = "$k"
"""El libro lleva el capital en miles de dólares. La ingesta los convierte."""


@dataclass(frozen=True)
class FilaDeCapex:
    """Una fila de la estructura estándar."""

    etiqueta: str
    medida: str | None
    """`None` marca una fila de sección, que no lleva datos."""

    naturaleza: str = ""
    """Naturaleza contable del motor que alimenta."""

    codigo: str = ""
    """Codigo contable de tres letras, el de la columna A del libro.

    **No es decorativo: es la clave con la que el libro suma.** Todo lo derivado
    de esta hoja —la etapa, el cruce, los totales— sale de un `SUMIF` sobre el,
    y que los equipos de computo compartan `MAQ` con la maquinaria es lo que
    hace que el libro los muestre fusionados donde la plataforma los separa.
    """

    calculada: bool = False
    """Ninguna lo es: en esta plantilla no hay nada que corroborar."""

    @property
    def es_seccion(self) -> bool:
        return self.medida is SECCION


FILAS_DE_CAPEX = (
    FilaDeCapex("Clasificación contable", SECCION),
    FilaDeCapex("No depreciable", MEDIDA, "no_depreciable", codigo="NOD"),
    FilaDeCapex("Equipos de cómputo", MEDIDA, "equipos_de_computo", codigo="MAQ"),
    FilaDeCapex("Maquinaria, equipos y vehículos", MEDIDA, "maquinaria", codigo="MAQ"),
    FilaDeCapex(
        "Instalaciones y equipos diversos y de comunicaciones",
        MEDIDA,
        "instalaciones",
        codigo="INS",
    ),
    FilaDeCapex("Edificaciones y construcciones", MEDIDA, "edificaciones", codigo="EDI"),
)

CON_DATO_DE_CAPEX = tuple(f for f in FILAS_DE_CAPEX if not f.es_seccion)


class ErrorDeAsociacion(ValueError):
    """Las pestañas del libro de capex no cuadran con las unidades del caso."""


@dataclass(frozen=True)
class CapexDeUnidad:
    """Lo que una pestaña aporta: sus cinco conceptos, tal como se cargaron."""

    conceptos: dict[str, Serie] = field(default_factory=dict)

    def por_naturaleza(self, horizonte: Horizonte) -> dict[str, Serie]:
        """Alinea los cinco conceptos con los cinco componentes del motor."""
        acumulado: dict[str, list[float]] = {}
        for fila in CON_DATO_DE_CAPEX:
            serie = self.conceptos.get(fila.etiqueta, ())
            if not serie:
                continue
            destino = acumulado.setdefault(fila.naturaleza, [0.0] * horizonte.anos)
            for i, valor in enumerate(serie[: horizonte.anos]):
                destino[i] += valor
        return {naturaleza: tuple(serie) for naturaleza, serie in acumulado.items()}

    @property
    def declara_capital(self) -> bool:
        return any(any(serie) for serie in self.conceptos.values())


def armar_capex(
    filas: Sequence[tuple[str, Serie]],
    incidencias: list[Incidencia],
    *,
    hoja: str,
) -> CapexDeUnidad:
    """Convierte las filas de una pestaña en el capital de su unidad.

    Recorre en paralelo la estructura estándar y la de la hoja. Una etiqueta que
    no es la que toca **detiene la lectura de esa pestaña y se reporta**: si la
    secuencia se rompe, seguir leyendo asignaría cada serie a la naturaleza de al
    lado, y con ella cambiarían la depreciación y el escudo fiscal.
    """
    conceptos: dict[str, Serie] = {}
    if not filas:
        # Una pestana vacia no es un error de estructura: es una unidad cuyo
        # capital todavia no se ha cargado.
        return CapexDeUnidad(conceptos)

    for salto, esperada in enumerate(CON_DATO_DE_CAPEX):
        if salto >= len(filas):
            incidencias.append(
                Incidencia(
                    hoja,
                    "-",
                    f"la clasificacion se corta en {esperada.etiqueta!r}: la pestana no trae "
                    "esa fila.",
                )
            )
            return CapexDeUnidad(conceptos)
        etiqueta, serie = filas[salto]
        if equivalente(etiqueta) != equivalente(esperada.etiqueta):
            incidencias.append(
                Incidencia(
                    hoja,
                    etiqueta,
                    f"se esperaba {esperada.etiqueta!r} y hay {etiqueta!r}. La plantilla de capex "
                    "tiene una estructura fija y esta pestana se aparta de ella.",
                )
            )
            return CapexDeUnidad(conceptos)
        conceptos[esperada.etiqueta] = serie

    if len(filas) != len(CON_DATO_DE_CAPEX):
        incidencias.append(
            Incidencia(
                hoja,
                filas[len(CON_DATO_DE_CAPEX)][0],
                f"sobran {len(filas) - len(CON_DATO_DE_CAPEX)} fila(s) despues de la "
                "clasificacion contable, que es todo lo que esta plantilla pide.",
            )
        )
    return CapexDeUnidad(conceptos)


def aplicar(caso: Caso, bloques: Sequence[CapexDeUnidad]) -> Caso:
    """Vuelca el capital leído sobre las unidades del caso, en orden.

    **Aquí se deriva la etapa**, con `clasificar_por_etapa` y los años en que la
    unidad produce. Una unidad sin capital cargado se queda sin `CapitalDeUnidad`
    en vez de recibir uno en ceros: el motor distingue las dos cosas, y un
    capital vacío entraría en el desglose por mina con una serie nula.
    """
    if len(bloques) != len(caso.unidades):
        raise ErrorDeAsociacion(
            f"El libro de capex trae {len(bloques)} pestana(s) y el caso declara "
            f"{len(caso.unidades)} unidad(es), incluidos la refineria y los depositos. "
            "Asociarlas por orden exige que sean tantas como unidades: sobra o falta un proyecto."
        )
    return replace(
        caso,
        unidades=tuple(
            replace(unidad, capital=_capital(caso.horizonte, unidad, bloque))
            for unidad, bloque in zip(caso.unidades, bloques, strict=True)
        ),
    )


def _capital(
    horizonte: Horizonte, unidad: UnidadProductiva, bloque: CapexDeUnidad
) -> CapitalDeUnidad | None:
    """Construye el capital de una unidad con las dos clasificaciones.

    El dueño es el nombre que declara el caso y no el de la pestaña: el motor
    rechaza un capital cuya unidad no coincida, porque cruzarlos rompe el
    desglose por mina.
    """
    if not bloque.declara_capital:
        return None
    por_naturaleza = bloque.por_naturaleza(horizonte)
    return CapitalDeUnidad(
        unidad=unidad.nombre,
        por_naturaleza=por_naturaleza,
        por_etapa=clasificar_por_etapa(
            horizonte,
            por_naturaleza,
            anos_activos=anos_con_dato(unidad.produccion.mineral_tratado),
            umbral_inicial=unidad.umbral_de_capital_inicial,
        ),
    )
