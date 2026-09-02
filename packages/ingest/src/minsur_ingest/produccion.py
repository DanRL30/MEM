"""Traduce las filas de una pestaña de producción a la estructura del motor.

Es parseo puro: recibe etiquetas ya normalizadas con su serie de valores y no
sabe nada de Excel. La lectura del archivo vive en `plantilla.py`, y esa
separación es la que permite probar el vocabulario sin construir un libro.

**Aquí no se borran los nombres de unidad de las etiquetas.** En la hoja del
complejo el nombre es el dato: `concentrado alimentado desde San Rafael` dice de
dónde viene lo que entra, y quitarlo deja una etiqueta que no significa nada. La
unidad a la que pertenece la fila ya la da la pestaña.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from minsur_engine.caso import ConcentradoDeMetal, CorrienteDeMineral, ProduccionDeUnidad
from minsur_engine.horizonte import Horizonte, Serie
from minsur_ingest.incidencias import Incidencia

METALES = ("Sn", "Cu", "Ag")
_METAL = "|".join(m.lower() for m in METALES)

# Sufijo con que la plantilla nombra la ley de cada corriente, y el campo de
# `ProduccionDeUnidad` al que alimenta esa corriente. El libro rotula todas las
# leyes igual y las distingue por la fila de arriba; la plantilla las nombra, y
# esta tabla es la que convierte ese nombre en destino.
CORRIENTES = {
    "mineral extraido": ("extraido", "del mineral extraido"),
    "mineral tratado en preconcentracion": (
        "tratado_en_preconcentracion",
        "de entrada a preconcentracion",
    ),
    "mineral preconcentrado a concentradora": (
        "preconcentrado_a_concentradora",
        "del preconcentrado",
    ),
    "mineral directo a planta concentradora": ("directo_a_concentradora", "del mineral directo"),
    "mineral tratado total en concentradora": ("tratado_total", "del tratado total"),
}
CORRIENTE_DE_LEY = {sufijo: campo for campo, sufijo in CORRIENTES.values()}

CASH_COST = "mineral tratado total para cash cost"
LEY_DE_CASH_COST = "del tratado para cash cost"
ENTREGADO = "concentrado entregado al complejo"

_LEY_DE_CORRIENTE = re.compile(rf"^ley de ({_METAL}) (.+)$")
_LEY_EN_CONCENTRADO = re.compile(rf"^ley de ({_METAL}) en el concentrado$")
_LEY_DE_SUBPRODUCTO = re.compile(rf"^ley de ({_METAL}) en el concentrado de ({_METAL})$")
_FINAS = re.compile(rf"^toneladas finas de ({_METAL})$")
_RECUPERACION = re.compile(rf"^recuperacion de ({_METAL})$")
_CONCENTRADO = re.compile(rf"^produccion de concentrado de ({_METAL})$")

_ALIMENTADO_DESDE = re.compile(r"^concentrado alimentado desde (.+)$")
_LEY_DE_ORIGEN = re.compile(rf"^ley de ({_METAL}) del concentrado de (.+)$")
_RECUPERACION_DE_ORIGEN = re.compile(rf"^recuperacion de ({_METAL}) de (.+)$")
_LEY_DE_ALIMENTACION = re.compile(rf"^ley promedio de alimentacion de ({_METAL})$")
_REFINADO = re.compile(rf"^produccion de metal refinado de ({_METAL})$")

_DEL_COMPLEJO = {
    "toneladas alimentadas mas escoria": "toneladas_alimentadas",
    "capacidad maxima de tratamiento": "capacidad_de_tratamiento",
    "concentrado excedente": "concentrado_excedente",
}


class _Acumulador:
    """Recoge las series de una pestaña antes de congelarlas en el motor."""

    def __init__(self, horizonte: Horizonte) -> None:
        self.horizonte = horizonte
        self.tonelajes: dict[str, Serie] = {}
        self.leyes: dict[str, dict[str, Serie]] = {}
        self.concentrados: dict[str, dict[str, Serie]] = {}
        self.leyes_del_tratado: dict[str, Serie] = {}
        self.mineral_tratado: Serie = ()
        self.entregado: Serie = ()
        self.alimentado: dict[str, Serie] = {}
        self.leyes_alimentadas: dict[str, dict[str, Serie]] = {}
        self.recuperacion_por_origen: dict[str, Serie] = {}
        self.del_complejo: dict[str, Serie] = {}
        self.refinado: dict[str, Serie] = {}

    def corriente(self, campo: str) -> CorrienteDeMineral | None:
        if campo not in self.tonelajes and campo not in self.leyes:
            return None
        return CorrienteDeMineral(
            toneladas=self.tonelajes.get(campo, self.horizonte.ceros()),
            leyes=dict(self.leyes.get(campo, {})),
        )


def armar_produccion(
    unidad: str,
    filas: Sequence[tuple[str, Serie]],
    horizonte: Horizonte,
    incidencias: list[Incidencia],
    *,
    hoja: str = "",
    declaradas: Sequence[str] = (),
) -> ProduccionDeUnidad:
    """Convierte las filas de una pestaña en la producción de su unidad.

    Una etiqueta que no se reconoce **se reporta**. Descartarla en silencio es
    el peor modo de fallo posible aquí: el usuario llena una fila, el caso se
    lee sin errores, y su dato no se usa.
    """
    acumulado = _Acumulador(horizonte)
    for etiqueta, serie in filas:
        if not _clasificar(acumulado, etiqueta, serie):
            incidencias.append(
                Incidencia(
                    hoja or unidad,
                    etiqueta,
                    f"concepto no reconocido en la pestana de {unidad}. La fila se llenaria "
                    "y su dato no se usaria.",
                )
            )

    return ProduccionDeUnidad(
        mineral_tratado=acumulado.mineral_tratado or horizonte.ceros(),
        concentrado_producido=_entregado(acumulado, horizonte),
        capacidad_de_tratamiento=acumulado.del_complejo.get("capacidad_de_tratamiento", ()),
        metal_refinado_vendido=_primera(acumulado.refinado),
        extraido=acumulado.corriente("extraido"),
        tratado_en_preconcentracion=acumulado.corriente("tratado_en_preconcentracion"),
        preconcentrado_a_concentradora=acumulado.corriente("preconcentrado_a_concentradora"),
        directo_a_concentradora=acumulado.corriente("directo_a_concentradora"),
        tratado_total=acumulado.corriente("tratado_total"),
        leyes_del_tratado=dict(acumulado.leyes_del_tratado),
        concentrados=_concentrados(acumulado),
        alimentacion_recibida=_alimentacion(acumulado, horizonte, declaradas),
        recuperacion_por_grupo={
            _declarada(origen, declaradas): serie
            for origen, serie in acumulado.recuperacion_por_origen.items()
        },
    )


def _clasificar(acumulado: _Acumulador, etiqueta: str, serie: Serie) -> bool:
    """Coloca una fila en su sitio. Devuelve si supo reconocerla.

    El orden importa: las etiquetas del complejo llevan un nombre de unidad al
    final y las de la mina no, de modo que lo especifico se prueba antes que lo
    general.
    """
    if etiqueta in CORRIENTES:
        acumulado.tonelajes[CORRIENTES[etiqueta][0]] = serie
        return True
    if etiqueta == CASH_COST:
        acumulado.mineral_tratado = serie
        return True
    if etiqueta == ENTREGADO:
        acumulado.entregado = serie
        return True
    if etiqueta in _DEL_COMPLEJO:
        acumulado.del_complejo[_DEL_COMPLEJO[etiqueta]] = serie
        return True

    return _clasificar_por_metal(acumulado, etiqueta, serie) or _clasificar_del_complejo(
        acumulado, etiqueta, serie
    )


def _clasificar_por_metal(acumulado: _Acumulador, etiqueta: str, serie: Serie) -> bool:
    if (m := _LEY_DE_SUBPRODUCTO.match(etiqueta)) is not None:
        subproducto, portador = _metal(m.group(1)), _metal(m.group(2))
        acumulado.concentrados.setdefault(portador, {})[f"ley de {subproducto}"] = serie
        return True
    if (m := _LEY_EN_CONCENTRADO.match(etiqueta)) is not None:
        acumulado.concentrados.setdefault(_metal(m.group(1)), {})["ley"] = serie
        return True
    if (m := _FINAS.match(etiqueta)) is not None:
        acumulado.concentrados.setdefault(_metal(m.group(1)), {})["finas"] = serie
        return True
    if (m := _CONCENTRADO.match(etiqueta)) is not None:
        acumulado.concentrados.setdefault(_metal(m.group(1)), {})["toneladas"] = serie
        return True
    if (m := _RECUPERACION_DE_ORIGEN.match(etiqueta)) is not None:
        acumulado.recuperacion_por_origen[m.group(2).strip()] = serie
        return True
    if (m := _RECUPERACION.match(etiqueta)) is not None:
        acumulado.concentrados.setdefault(_metal(m.group(1)), {})["recuperacion"] = serie
        return True
    if (m := _LEY_DE_ORIGEN.match(etiqueta)) is not None:
        origen = m.group(2).strip()
        acumulado.leyes_alimentadas.setdefault(origen, {})[_metal(m.group(1))] = serie
        return True
    if (m := _LEY_DE_CORRIENTE.match(etiqueta)) is not None:
        metal, sufijo = _metal(m.group(1)), m.group(2).strip()
        if sufijo == LEY_DE_CASH_COST:
            acumulado.leyes_del_tratado[metal] = serie
            return True
        campo = CORRIENTE_DE_LEY.get(sufijo)
        if campo is not None:
            acumulado.leyes.setdefault(campo, {})[metal] = serie
            return True
    return False


def _clasificar_del_complejo(acumulado: _Acumulador, etiqueta: str, serie: Serie) -> bool:
    if (m := _ALIMENTADO_DESDE.match(etiqueta)) is not None:
        acumulado.alimentado[m.group(1).strip()] = serie
        return True
    if (m := _LEY_DE_ALIMENTACION.match(etiqueta)) is not None:
        acumulado.leyes.setdefault("alimentacion", {})[_metal(m.group(1))] = serie
        return True
    if (m := _REFINADO.match(etiqueta)) is not None:
        acumulado.refinado[_metal(m.group(1))] = serie
        return True
    return False


def _entregado(acumulado: _Acumulador, horizonte: Horizonte) -> Serie:
    """Lo que la unidad entrega al complejo.

    Si la plantilla no trae la fila consolidada —porque la unidad vende directo
    y no hay fundicion— se toma el concentrado del unico metal que la produce.
    """
    if acumulado.entregado:
        return acumulado.entregado
    toneladas = [c["toneladas"] for c in acumulado.concentrados.values() if "toneladas" in c]
    if len(toneladas) == 1:
        return toneladas[0]
    return horizonte.ceros()


def _concentrados(acumulado: _Acumulador) -> dict[str, ConcentradoDeMetal]:
    salida: dict[str, ConcentradoDeMetal] = {}
    for metal, partes in acumulado.concentrados.items():
        if "toneladas" not in partes and "ley" not in partes:
            continue
        salida[metal] = ConcentradoDeMetal(
            toneladas=partes.get("toneladas", ()),
            ley=partes.get("ley", ()),
            recuperacion=partes.get("recuperacion", ()),
            toneladas_finas=partes.get("finas", ()),
        )
    return salida


def _alimentacion(
    acumulado: _Acumulador, horizonte: Horizonte, declaradas: Sequence[str]
) -> dict[str, CorrienteDeMineral]:
    origenes = set(acumulado.alimentado) | set(acumulado.leyes_alimentadas)
    return {
        _declarada(origen, declaradas): CorrienteDeMineral(
            toneladas=acumulado.alimentado.get(origen, horizonte.ceros()),
            leyes=dict(acumulado.leyes_alimentadas.get(origen, {})),
        )
        for origen in sorted(origenes)
    }


def _declarada(origen: str, declaradas: Sequence[str]) -> str:
    """Devuelve el nombre de la unidad tal como el caso la declara.

    La etiqueta viene normalizada y el motor cruza estas claves con los nombres
    de las unidades: sin devolver el nombre declarado, el corroborador no
    encuentra la unidad de origen y deja de comprobar la alimentacion.
    """
    for nombre in declaradas:
        if _plano(nombre) == _plano(origen):
            return nombre
    return origen


def _plano(texto: str) -> str:
    return " ".join(texto.lower().split())


def _primera(series: dict[str, Serie]) -> Serie:
    """La primera serie declarada, o vacía. Ordena para no depender del azar."""
    for clave in sorted(series):
        return series[clave]
    return ()


def _metal(texto: str) -> str:
    return next(m for m in METALES if m.lower() == texto.lower())


UNIDADES_PROVISIONALES = ("SR", "B2", "NZ", "SRP", "SD")
"""Abreviaturas que ofrece el selector mientras no llegue el catalogo de MINSUR.

Son las cinco unidades mineras del modelo vigente: San Rafael, B2, Nazareth, San
Rafael Potencial y Santo Domingo. **No incluye Pisco**, porque el complejo no se
carga: se calcula a partir del concentrado que le entregan las minas.

Es una lista provisional y no una regla del motor. El catalogo definitivo lo
mantiene MINSUR como dato maestro, y hasta entonces un caso nuevo puede declarar
unidades que no esten aqui.
"""


class ErrorDeAsociacion(ValueError):
    """Las pestañas del libro no cuadran con las unidades del caso."""


def asociar_por_orden(hojas: Sequence[str], unidades: Sequence[str]) -> dict[str, str]:
    """Empareja cada pestaña con una unidad por su posicion.

    Es lo que acordo el avance 02 del 28/08/2026: el procesamiento se basa en el
    orden de las hojas y el proyecto se asigna desde la plataforma. El nombre de
    la pestaña no decide nada, porque quien llena el archivo puede rotularla como
    quiera y dos fuentes de identidad acaban contradiciendose.

    Devuelve el nombre de hoja de cada unidad, en el orden en que llegaron.
    """
    if len(hojas) != len(unidades):
        raise ErrorDeAsociacion(
            f"El libro trae {len(hojas)} pestana(s) de proyecto y el caso declara "
            f"{len(unidades)} unidad(es). Asociarlas por orden exige que sean tantas como "
            "unidades: sobra o falta un proyecto."
        )
    return dict(zip(unidades, hojas, strict=True))
