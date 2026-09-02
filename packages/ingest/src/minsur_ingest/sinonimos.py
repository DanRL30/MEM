"""Traducción del vocabulario del libro al del catálogo.

La verificación de cobertura del catálogo de inputs dejó un hallazgo con
consecuencia directa aquí: el libro corporativo **no llama a las cosas por su
nombre canónico**. Abrevia (`LT`, `Pta Subproductos`), pega el nombre de la
unidad a la etiqueta (`Mineral Tratado Planta B2`, `Tratamiento de Relaves B2`)
y alterna con o sin paréntesis (`Mineral Tratado Total (Cash Cost)`).

Sin esta traducción, leer una plantilla llenada al estilo del libro pierde una
de cada veinte líneas **en silencio**, que es la peor forma de perderlas: el
caso se calcula igual, con un concepto en cero.

La normalización hace el trabajo grueso —acentos, mayúsculas, puntuación— y la
tabla solo recoge lo que la normalización no puede adivinar. Añadir un sinónimo
es una línea; inventarse uno que el libro no usa es ruido.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

# Etiqueta del libro, ya normalizada, a concepto del catalogo.
SINONIMOS = {
    "mineral tratado total cash cost": "mineral tratado total para cash cost",
    "mineral tratado planta": "mineral tratado total en concentradora",
    # `Tratamiento de Relaves B2` es una linea de InputsOpex, no de
    # produccion: mapearla a un concepto de produccion creaba un costo
    # fantasma con nombre de tonelaje.
    "tratamiento de relaves": "relavera",
    "concentrado alimentado": "concentrado alimentado desde otra unidad",
    "sn en concentrado": "metal contenido en el concentrado",
    "toneladas alimentadas escoria": "toneladas alimentadas mas escoria",
    "produccion sn refinado": "produccion de metal refinado",
    "produccion sn refinado sin restriccion": "produccion de metal refinado",
    "planta preconcentracion": "planta de preconcentracion",
    "pta subproductos": "planta de subproductos",
    "lt": "linea de transmision",
    "servidumbre usufructos": "predios, servidumbres y usufructos",
    "gestion social deducible": "gestion social",
    "estudios y optimizaciones": "estudios y optimizaciones",
}

METALES_CONOCIDOS = ("Sn", "Cu", "Ag")
"""El alcance del modelo son tres metales, no seis.

Admitir Pb, Zn y Au hacia que una etiqueta con uno de ellos se leyera como un
concepto valido de un metal que la plataforma no sabe liquidar. Con la lista
acotada, esa fila llega a la ingesta como concepto no reconocido y se reporta.
"""


def normalizar(etiqueta: str) -> str:
    """Baja a minúsculas, quita acentos y colapsa la puntuación."""
    sin_acentos = unicodedata.normalize("NFKD", etiqueta).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", sin_acentos.lower()).strip()


def separar_metal(etiqueta: str) -> tuple[str, str | None]:
    """Separa el metal del concepto: `Ley de cabeza de Sn` da `(ley de cabeza, Sn)`."""
    for metal in METALES_CONOCIDOS:
        patron = re.compile(rf"\s+(?:de\s+)?{metal}\b\s*$", re.IGNORECASE)
        if patron.search(etiqueta):
            return patron.sub("", etiqueta).strip(), metal
    return etiqueta.strip(), None


def sin_nombre_de_unidad(etiqueta: str, unidades: Iterable[str]) -> str:
    """Quita el nombre de la unidad pegado a la etiqueta.

    El libro escribe `Cash Cost San Rafael` y `Total B2`. Como los nombres de
    las unidades los declara el propio caso, aquí se conocen y se pueden
    retirar sin adivinar.
    """
    resultado = etiqueta
    for unidad in sorted(unidades, key=len, reverse=True):
        normalizada = normalizar(unidad)
        if not normalizada:
            continue
        resultado = re.sub(rf"\b{re.escape(normalizada)}\b", " ", resultado)
    return re.sub(r"\s+", " ", resultado).strip()


def canonizar(etiqueta: str, unidades: Iterable[str] = ()) -> tuple[str, str | None]:
    """Devuelve el concepto del catálogo y el metal al que se refiere, si lo hay.

    El concepto vuelve normalizado, que es como se comparan: lo que importa es
    que dos escrituras de la misma cosa lleguen al mismo sitio, no cuál de las
    dos se conserva.
    """
    sin_metal, metal = separar_metal(etiqueta)
    normalizada = normalizar(sin_metal)
    normalizada = sin_nombre_de_unidad(normalizada, unidades)
    return SINONIMOS.get(normalizada, normalizada), metal
