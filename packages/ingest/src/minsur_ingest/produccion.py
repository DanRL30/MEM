"""La estructura estándar de una pestaña de producción, y su lectura.

**Hay una sola estructura y es siempre la misma.** No se adapta al proyecto: uno
sin preconcentración deja esas filas en cero y la plataforma no las muestra. Es
lo que hace que la plantilla sirva para un proyecto que hoy no existe, y lo que
obliga a leerla por secuencia y no por nombre: el libro repite la etiqueta
`Ley Sn` cinco veces, y lo único que las distingue es la fila que llevan encima.

Las etiquetas, las unidades de medida y el orden son los del libro de MINSUR. No
se traducen ni se reordenan: es lo que Finanzas reconoce al revisar.

Cada fila es **dato** o **calculada**. Las dos se cargan igual; la diferencia es
que las calculadas se rehacen y se comparan contra lo cargado. El sistema no
corrige nunca: avisa.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from minsur_engine.caso import ProduccionDeUnidad
from minsur_engine.horizonte import Horizonte, Serie
from minsur_ingest.incidencias import Incidencia
from minsur_ingest.sinonimos import normalizar

SECCION = None


@dataclass(frozen=True)
class FilaDeProduccion:
    """Una fila de la estructura estándar."""

    etiqueta: str
    medida: str | None
    """`None` marca una fila de sección, que no lleva datos."""

    campo: str = ""
    """Campo de `ProduccionDeUnidad` que alimenta."""

    calculada: bool = False
    """Si el sistema la rehace para corroborar lo que el usuario cargó."""

    @property
    def es_seccion(self) -> bool:
        return self.medida is SECCION


FILAS_DE_PRODUCCION = (
    FilaDeProduccion("Mina", SECCION),
    FilaDeProduccion("Mineral extraído", "t", "mineral_extraido"),
    FilaDeProduccion("Ley Sn", "%", "ley_de_cabeza"),
    FilaDeProduccion("Planta", SECCION),
    FilaDeProduccion("Mineral Tratado en Pre Concentración", "t", "tratado_en_preconcentracion"),
    FilaDeProduccion("Ley de Sn (entrada)", "%", "ley_de_entrada"),
    FilaDeProduccion("Mineral Pre-Concentrado a Concentradora", "t", "preconcentrado"),
    FilaDeProduccion("Ley Sn", "%", "ley_del_preconcentrado"),
    FilaDeProduccion("Mineral Directo a Planta Concentradora", "t", "directo", calculada=True),
    FilaDeProduccion("Ley de Sn", "%", "ley_del_directo", calculada=True),
    FilaDeProduccion("Mineral Tratado Total en Concentradora", "t", "tratado_total", True),
    FilaDeProduccion("Ley Sn", "%", "ley_del_tratado_total", calculada=True),
    FilaDeProduccion("Mineral Tratado Total (Cash Cost)", "t", "mineral_tratado", True),
    FilaDeProduccion("Ley Sn", "%", "ley_del_cash_cost", calculada=True),
    FilaDeProduccion("Toneladas finas", "t", "toneladas_finas", calculada=True),
    FilaDeProduccion("Ley Sn Concentrado", "%", "ley_del_concentrado"),
    FilaDeProduccion("Recuperación Sn", "%", "recuperacion"),
    FilaDeProduccion("Producción Concentrado", "t", "concentrado_producido", calculada=True),
    FilaDeProduccion("Concentrado de Cu", SECCION),
    FilaDeProduccion("Concentrado Producido Cu", "t", "concentrado_de_cu"),
    FilaDeProduccion("Ley Cu", "%", "ley_cu"),
    # La plata se paga por onza troy y su ley viene en onzas por tonelada, no en
    # porcentaje. Leerla como porcentaje la dividiria entre cien sin avisar.
    FilaDeProduccion("Ley Ag", "oz/t", "ley_ag"),
)

FILAS_CON_DATO = tuple(f for f in FILAS_DE_PRODUCCION if not f.es_seccion)

UNIDADES_PROVISIONALES = ("SR", "B2", "NZ", "SRP", "SD")
"""Abreviaturas que ofrece el selector mientras no llegue el catalogo de MINSUR.

Son las cinco unidades mineras del modelo vigente: San Rafael, B2, Nazareth, San
Rafael Potencial y Santo Domingo. **No incluye Pisco**, porque la refinería no se
carga: sus filas son resultado del concentrado que le entregan las minas.

Es una lista provisional y no una regla del motor. El catalogo definitivo lo
mantiene MINSUR como dato maestro.
"""


class ErrorDeAsociacion(ValueError):
    """Las pestañas del libro no cuadran con las unidades del caso."""


def armar_produccion(
    filas: Sequence[tuple[str, Serie]],
    horizonte: Horizonte,
    incidencias: list[Incidencia],
    *,
    hoja: str,
) -> ProduccionDeUnidad:
    """Convierte las filas de una pestaña en la producción de su unidad.

    Recorre en paralelo la estructura estándar y la de la hoja. Una etiqueta que
    no es la que toca **detiene la lectura de esa pestaña y se reporta**: si la
    secuencia se rompe, seguir leyendo asignaría cada serie al concepto de al
    lado y el caso saldría plausible y equivocado.
    """
    if not filas:
        # Sin filas no hay nada que leer, y no es un error de estructura: es lo
        # que ocurre con la refinería, que no tiene pestana porque sus filas son
        # resultado de lo que producen las minas.
        return _armada({}, horizonte)

    campos: dict[str, Serie] = {}
    for esperada, (etiqueta, serie) in zip(FILAS_CON_DATO, filas, strict=False):
        if normalizar(etiqueta) != normalizar(esperada.etiqueta):
            incidencias.append(
                Incidencia(
                    hoja,
                    etiqueta,
                    f"se esperaba {esperada.etiqueta!r} y hay {etiqueta!r}. La plantilla de "
                    "produccion tiene una estructura fija y esta pestana se aparta de ella.",
                )
            )
            return _armada(campos, horizonte)
        campos[esperada.campo] = serie

    if len(filas) != len(FILAS_CON_DATO):
        incidencias.append(
            Incidencia(
                hoja,
                "-",
                f"la pestana trae {len(filas)} filas de datos y la estructura estandar tiene "
                f"{len(FILAS_CON_DATO)}.",
            )
        )
    return _armada(campos, horizonte)


def _armada(campos: dict[str, Serie], horizonte: Horizonte) -> ProduccionDeUnidad:
    return ProduccionDeUnidad(
        mineral_tratado=campos.pop("mineral_tratado", horizonte.ceros()), **campos
    )


def asociar_por_orden(hojas: Sequence[str], unidades: Sequence[str]) -> dict[str, str]:
    """Empareja cada pestaña con una unidad por su posicion.

    Es lo que acordo el avance 02 del 28/08/2026: el procesamiento se basa en el
    orden de las hojas y el proyecto se asigna desde la plataforma. El nombre de
    la pestaña no decide nada, porque quien llena el archivo puede rotularla como
    quiera y dos fuentes de identidad acaban contradiciendose.
    """
    if len(hojas) != len(unidades):
        raise ErrorDeAsociacion(
            f"El libro trae {len(hojas)} pestana(s) de proyecto y el caso declara "
            f"{len(unidades)} unidad(es). Asociarlas por orden exige que sean tantas como "
            "unidades: sobra o falta un proyecto."
        )
    return dict(zip(unidades, hojas, strict=True))
