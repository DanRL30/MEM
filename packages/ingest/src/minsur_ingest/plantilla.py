"""Lectura de la plantilla canónica: de un libro de Excel a un caso validado.

Es la frontera del motor. Aquí se lee Excel, se traduce el vocabulario del
libro al del catálogo, se validan las celdas y se convierten unidades y escalas.
Del otro lado el motor recibe estructuras limpias y no vuelve a ver una hoja de
cálculo, que es lo que le permite ser puro.

**Aquí y solo aquí se convierten escalas.** El libro alterna dólares y miles de
dólares con factores de 10^3 repartidos por las fórmulas —la regla 003, todavía
sin confirmar— y esa mezcla no se propaga: la plantilla declara sus unidades en
la columna B y el motor trabaja siempre en dólares y toneladas.

**La lectura no se detiene en el primer error.** Acumula incidencias con su hoja
y su celda y las devuelve juntas, porque una plantilla llena a mano llega con
varios problemas a la vez.

La estructura que se lee es la que emite `scripts/generar_plantilla_inputs.py`:
fila 3 con los años desde la columna C, secciones en gris con el nombre de la
unidad, y filas de entrada con concepto en A y unidad de medida en B.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from minsur_engine.caso import (
    Caso,
    DatosComunes,
    ProduccionDeUnidad,
    TerminosComerciales,
    UnidadProductiva,
)
from minsur_engine.horizonte import ErrorHorizonte, Horizonte, Serie
from minsur_ingest.capex import CapexDeUnidad, armar_capex
from minsur_ingest.incidencias import ErrorDePlantilla, Incidencia
from minsur_ingest.opex import OpexDeUnidad, armar_opex
from minsur_ingest.produccion import armar_produccion
from minsur_ingest.sinonimos import canonizar, normalizar
from minsur_ingest.supuestos import (
    CON_DATO_DE_PRECIOS,
    CON_DATO_DE_SUPUESTOS,
    CON_DATO_POR_UNIDAD,
    ComiteDePrecios,
    SupuestosDelCaso,
    armar_filas,
)

HOJAS_REQUERIDAS = ("Caso", "Precios")
"""Ni la produccion, ni el opex, ni el capex: cada bloque viene en su libro.

Los nombres de sus pestanas los declara el caso o el orden, de modo que no se
pueden fijar en una constante. `Leeme` se ignora.
"""

PRIMERA_FILA_DE_DATOS = 5
PRIMERA_COLUMNA_DE_ANOS = 3
FILA_DE_ANOS = 3
LIMITE_DE_NOMBRE_DE_HOJA = 31

HOJA_DE_PRECIOS = "Comite de Precios"
HOJA_COMUN = "Comunes"

HOJAS_SIN_DATOS = ("leeme", "caso")
"""Pestanas del libro de produccion que no son un proyecto."""

# Unidad de medida declarada en la columna B, y su factor a la unidad del motor.
# La clave conserva el simbolo de moneda y el de porcentaje: son lo unico que
# distingue "US$" de "miles de US$", y perderlos al normalizar deja pasar un
# factor de mil sin avisar.
FACTORES_DE_ESCALA = {
    "us$": 1.0,
    "us$/ano": 1.0,
    "miles de us$": 1_000.0,
    "mus$": 1_000.0,
    "t": 1.0,
    "tmf": 1.0,
    "kt": 1_000.0,
    "%": 0.01,
    "fraccion": 1.0,
    "dias": 1.0,
    "us$/t": 1.0,
    # La ley de plata viene en onzas troy por tonelada, no en porcentaje.
    "oz/t": 1.0,
    # Unidades de la hoja de supuestos, con las abreviaturas del libro.
    "$": 1.0,
    "$/t": 1.0,
    "$/oz": 1.0,
    "$/t conc": 1.0,
    "$/tmf": 1.0,
    "g/t": 1.0,
    # Miles de dolares. Es la regla 003 otra vez: el libro alterna escalas y la
    # conversion ocurre aqui, no dentro del motor. Las dos escrituras son suyas:
    # la hoja de depreciacion pone `k$` y la de opex `$k`, y reconocer solo una
    # deja pasar un factor de mil sin avisar.
    "k$": 1_000.0,
    "$k": 1_000.0,
}


def _clave_de_medida(texto: str) -> str:
    """Normaliza una unidad de medida sin borrar su moneda ni su porcentaje."""
    sin_acentos = (
        unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"\s+", " ", sin_acentos.strip().lower())


@dataclass(frozen=True)
class Lectura:
    """Resultado de leer una plantilla."""

    caso: Caso | None
    incidencias: tuple[Incidencia, ...]

    @property
    def valida(self) -> bool:
        return self.caso is not None


@dataclass(frozen=True)
class LecturaDeComite:
    """Resultado de leer la plantilla del comite de precios."""

    comite: ComiteDePrecios | None
    incidencias: tuple[Incidencia, ...]

    @property
    def valida(self) -> bool:
        return self.comite is not None


@dataclass(frozen=True)
class LecturaDeSupuestos:
    """Resultado de leer la plantilla de supuestos del caso."""

    supuestos: SupuestosDelCaso | None
    horizonte: Horizonte | None
    incidencias: tuple[Incidencia, ...]

    @property
    def valida(self) -> bool:
        return self.supuestos is not None


@dataclass(frozen=True)
class BloqueDeProduccion:
    """Una pestaña del libro de producción, sin unidad asignada todavía.

    `orden` es lo que la plataforma usa para asociarla: la primera pestaña es la
    primera unidad del caso. `hoja` viaja como pista para quien elige, no como
    identidad.
    """

    orden: int
    hoja: str
    produccion: ProduccionDeUnidad


@dataclass(frozen=True)
class LecturaDeProduccion:
    """Resultado de leer el libro de producción."""

    bloques: tuple[BloqueDeProduccion, ...]
    horizonte: Horizonte | None
    incidencias: tuple[Incidencia, ...]

    @property
    def valida(self) -> bool:
        return bool(self.bloques) and not self.incidencias


@dataclass(frozen=True)
class BloqueDeOpex:
    """Una pestaña del libro de opex, sin unidad asignada todavía."""

    orden: int
    hoja: str
    opex: OpexDeUnidad


@dataclass(frozen=True)
class BloqueDeCapex:
    """Una pestaña del libro de capex, sin unidad asignada todavía."""

    orden: int
    hoja: str
    capex: CapexDeUnidad


@dataclass(frozen=True)
class LecturaDeCapex:
    """Resultado de leer el libro de capex."""

    bloques: tuple[BloqueDeCapex, ...]
    horizonte: Horizonte | None
    incidencias: tuple[Incidencia, ...]

    @property
    def valida(self) -> bool:
        return bool(self.bloques) and not self.incidencias


@dataclass(frozen=True)
class LecturaDeOpex:
    """Resultado de leer el libro de opex."""

    bloques: tuple[BloqueDeOpex, ...]
    horizonte: Horizonte | None
    incidencias: tuple[Incidencia, ...]

    @property
    def valida(self) -> bool:
        return bool(self.bloques) and not self.incidencias


@dataclass(frozen=True)
class _UnidadDeclarada:
    """Una fila de la tabla de unidades de la hoja `Caso`.

    El origen y las etapas viajan aqui y no en la hoja de instrucciones porque
    son los que deciden que filas tiene la pestana de la unidad: sin ellos, de
    una plantilla llena no se puede regenerar la misma plantilla.
    """

    nombre: str
    tipo: str
    metales: str
    origen: str = "yacimiento"
    etapas: str = ""
    entrega_a: str = ""

    @property
    def hoja(self) -> str:
        """Nombre de su pestana, con el limite que impone Excel."""
        limpio = "".join(c for c in self.nombre if c not in r"[]:*?/\'")
        return limpio[:LIMITE_DE_NOMBRE_DE_HOJA] or "Unidad"


@dataclass
class _Cabecera:
    """Lo que la hoja `Caso` declara sobre el caso completo."""

    nombre: str
    escenario: str
    horizonte: Horizonte | None
    unidades: list[_UnidadDeclarada]
    comunes: dict[str, float]


@dataclass
class _Fila:
    """Una fila de datos de la plantilla, ya localizada y traducida."""

    hoja: str
    numero: int
    seccion: str
    concepto: str
    metal: str | None
    medida: str
    valores: tuple[object, ...]


def leer_plantilla(ruta: Path, *, escenario: str | None = None) -> Lectura:
    """Lee una plantilla llena y devuelve el caso, o las incidencias que lo impiden.

    `escenario` elige el juego de precios; si no se indica, se usa el que la
    propia plantilla declara en su hoja `Caso`.
    """
    incidencias: list[Incidencia] = []
    if not ruta.exists():
        return Lectura(None, (Incidencia("(archivo)", str(ruta), "no existe"),))

    libro = load_workbook(ruta, data_only=True, read_only=True)
    faltantes = [h for h in HOJAS_REQUERIDAS if h not in libro.sheetnames]
    if faltantes:
        return Lectura(
            None,
            (
                Incidencia(
                    "(libro)",
                    "-",
                    f"faltan las hojas {', '.join(faltantes)}. La plantilla no es la canonica.",
                ),
            ),
        )

    cabecera = _leer_hoja_caso(libro["Caso"], incidencias)
    horizonte = cabecera.horizonte
    if horizonte is None:
        return Lectura(None, tuple(incidencias))

    produccion: dict[str, list[_Fila]] = {}
    for declarada in cabecera.unidades:
        if declarada.tipo != "mina":
            # Ni la refinería ni un deposito tienen pestana de produccion: la
            # primera recibe concentrado y el segundo relave.
            continue
        if declarada.hoja not in libro.sheetnames:
            incidencias.append(
                Incidencia(
                    "(libro)",
                    declarada.hoja,
                    f"la unidad {declarada.nombre!r} esta declarada en la hoja Caso y no tiene "
                    "pestana de produccion.",
                )
            )
            continue
        produccion[declarada.nombre] = _leer_pestana_de_unidad(libro[declarada.hoja], horizonte)

    precios = _leer_hoja_de_series(libro["Precios"], horizonte, [], incidencias)
    libro.close()

    unidades = _armar_unidades(cabecera, horizonte, produccion, incidencias)
    terminos = _armar_terminos(precios, horizonte, escenario or cabecera.escenario, incidencias)
    comunes = _armar_datos_comunes(cabecera, horizonte)

    if incidencias or not unidades:
        if not unidades and not incidencias:
            incidencias.append(
                Incidencia("Caso", "A16", "la plantilla no declara unidades productivas")
            )
        return Lectura(None, tuple(incidencias))

    try:
        caso = Caso(
            nombre=cabecera.nombre or ruta.stem,
            horizonte=horizonte,
            unidades=tuple(unidades),
            terminos=terminos,
            datos_comunes=comunes,
        )
    except ValueError as error:
        return Lectura(None, (Incidencia("Caso", "-", str(error)),))

    return Lectura(caso, ())


def leer_produccion(ruta: Path) -> LecturaDeProduccion:
    """Lee el libro de produccion: una pestaña por proyecto, en orden.

    **No identifica el caso ni las unidades.** El archivo se sube desde un caso
    que la plataforma ya tiene abierto, y cada pestaña se asocia a una unidad
    por su posicion, que es lo que acordo el avance 02 del 28/08/2026. El nombre
    de la pestaña viaja como pista para quien elige en el selector, nunca como
    identidad: dos fuentes de identidad acaban contradiciendose.

    El horizonte se deduce de la fila de años de la primera pestaña, de modo que
    un proyecto de vida larga no exige tocar nada.
    """
    incidencias: list[Incidencia] = []
    if not ruta.exists():
        return LecturaDeProduccion((), None, (Incidencia("(archivo)", str(ruta), "no existe"),))

    libro = load_workbook(ruta, data_only=True, read_only=True)
    hojas = [h for h in libro.sheetnames if normalizar(h) not in HOJAS_SIN_DATOS]
    if not hojas:
        libro.close()
        return LecturaDeProduccion(
            (),
            None,
            (Incidencia("(libro)", "-", "el libro no trae ninguna pestana de proyecto"),),
        )

    horizonte = _horizonte_de_la_cabecera(libro[hojas[0]], incidencias)
    if horizonte is None:
        libro.close()
        return LecturaDeProduccion((), None, tuple(incidencias))

    bloques: list[BloqueDeProduccion] = []
    for orden, nombre in enumerate(hojas, start=1):
        filas = [
            (fila.concepto, _serie(fila, horizonte, incidencias))
            for fila in _leer_pestana_de_unidad(libro[nombre], horizonte)
        ]
        bloques.append(
            BloqueDeProduccion(
                orden=orden,
                hoja=nombre,
                produccion=armar_produccion(filas, horizonte, incidencias, hoja=nombre),
            )
        )
    libro.close()
    return LecturaDeProduccion(tuple(bloques), horizonte, tuple(incidencias))


def leer_opex(ruta: Path) -> LecturaDeOpex:
    """Lee el libro de opex: una pestaña por unidad, en orden.

    Igual que el de producción, no identifica el caso: la pestaña n es la
    unidad n del caso que ya está abierto. **Trae una pestaña más que el libro
    de producción**, porque la refinería tiene costo aunque su producción sea
    resultado.
    """
    incidencias: list[Incidencia] = []
    if not ruta.exists():
        return LecturaDeOpex((), None, (Incidencia("(archivo)", str(ruta), "no existe"),))

    libro = load_workbook(ruta, data_only=True, read_only=True)
    hojas = [h for h in libro.sheetnames if normalizar(h) not in HOJAS_SIN_DATOS]
    if not hojas:
        libro.close()
        return LecturaDeOpex(
            (),
            None,
            (Incidencia("(libro)", "-", "el libro no trae ninguna pestana de proyecto"),),
        )

    horizonte = _horizonte_de_la_cabecera(libro[hojas[0]], incidencias)
    if horizonte is None:
        libro.close()
        return LecturaDeOpex((), None, tuple(incidencias))

    bloques: list[BloqueDeOpex] = []
    for orden, nombre in enumerate(hojas, start=1):
        hoja = libro[nombre]
        _reportar_importes_sin_concepto(hoja, horizonte, incidencias)
        bloques.append(
            BloqueDeOpex(
                orden=orden,
                hoja=nombre,
                opex=armar_opex(_pares(hoja, horizonte, incidencias), incidencias, hoja=nombre),
            )
        )
    libro.close()
    return LecturaDeOpex(tuple(bloques), horizonte, tuple(incidencias))


def leer_capex(ruta: Path) -> LecturaDeCapex:
    """Lee el libro de capex: una pestaña por unidad, en orden.

    Trae **una pestaña por cada unidad que el caso declare**, refinería y
    depósitos incluidos: los tres tipos invierten, aunque solo uno produzca.
    """
    incidencias: list[Incidencia] = []
    if not ruta.exists():
        return LecturaDeCapex((), None, (Incidencia("(archivo)", str(ruta), "no existe"),))

    libro = load_workbook(ruta, data_only=True, read_only=True)
    hojas = [h for h in libro.sheetnames if normalizar(h) not in HOJAS_SIN_DATOS]
    if not hojas:
        libro.close()
        return LecturaDeCapex(
            (),
            None,
            (Incidencia("(libro)", "-", "el libro no trae ninguna pestana de proyecto"),),
        )

    horizonte = _horizonte_de_la_cabecera(libro[hojas[0]], incidencias)
    if horizonte is None:
        libro.close()
        return LecturaDeCapex((), None, tuple(incidencias))

    bloques: list[BloqueDeCapex] = []
    for orden, nombre in enumerate(hojas, start=1):
        hoja = libro[nombre]
        _reportar_importes_sin_concepto(hoja, horizonte, incidencias)
        bloques.append(
            BloqueDeCapex(
                orden=orden,
                hoja=nombre,
                capex=armar_capex(_pares(hoja, horizonte, incidencias), incidencias, hoja=nombre),
            )
        )
    libro.close()
    return LecturaDeCapex(tuple(bloques), horizonte, tuple(incidencias))


def _reportar_importes_sin_concepto(
    hoja: Worksheet, horizonte: Horizonte, incidencias: list[Incidencia]
) -> None:
    """Avisa de una fila de la cola con importes y sin nombre.

    Las filas de la cola salen en blanco y la lectura salta las que siguen así,
    que es lo correcto: una fila sin concepto no aporta nada. Pero una fila con
    importes y sin nombre es otra cosa —un costo que nadie puede atribuir— y
    saltarla en silencio lo haría desaparecer del total sin dejar rastro.
    """
    ultima = PRIMERA_COLUMNA_DE_ANOS + horizonte.anos - 1
    # El numero de fila se lleva contado y no se pide a la celda: sin concepto,
    # la primera columna llega como celda vacia y una celda vacia no sabe donde
    # esta.
    for numero, fila in enumerate(
        hoja.iter_rows(min_row=PRIMERA_FILA_DE_DATOS, max_col=ultima), start=PRIMERA_FILA_DE_DATOS
    ):
        etiqueta, medida = fila[0].value, fila[1].value
        if medida is None or (etiqueta is not None and str(etiqueta).strip()):
            continue
        if any(isinstance(celda.value, int | float) and celda.value for celda in fila[2:]):
            incidencias.append(
                Incidencia(
                    hoja.title,
                    f"A{numero}",
                    "hay importes en una fila sin concepto. Un costo sin nombre no se puede "
                    "atribuir, y quedaria fuera del total sin que nada lo acuse.",
                )
            )


def leer_comite_de_precios(ruta: Path) -> LecturaDeComite:
    """Lee la plantilla de precios que sube Finanzas.

    Es dato maestro y por eso lleva identificacion: una corrida registra que
    comite uso, no "el vigente". Publicar uno nuevo no reescribe evaluaciones
    pasadas.
    """
    incidencias: list[Incidencia] = []
    if not ruta.exists():
        return LecturaDeComite(None, (Incidencia("(archivo)", str(ruta), "no existe"),))

    libro = load_workbook(ruta, data_only=True, read_only=True)
    if HOJA_DE_PRECIOS not in libro.sheetnames:
        libro.close()
        return LecturaDeComite(
            None,
            (
                Incidencia(
                    "(libro)",
                    "-",
                    f"falta la hoja {HOJA_DE_PRECIOS!r}. No es la plantilla del comite.",
                ),
            ),
        )

    hoja = libro[HOJA_DE_PRECIOS]
    horizonte = _horizonte_de_la_cabecera(hoja, incidencias)
    if horizonte is None:
        libro.close()
        return LecturaDeComite(None, tuple(incidencias))

    nombre = str(hoja["B2"].value or "").strip()
    aprobado = str(hoja["D2"].value or "").strip()
    campos = armar_filas(
        CON_DATO_DE_PRECIOS,
        _pares(hoja, horizonte, incidencias),
        incidencias,
        hoja=HOJA_DE_PRECIOS,
    )
    libro.close()

    if not nombre:
        incidencias.append(
            Incidencia(
                HOJA_DE_PRECIOS,
                "B2",
                "el comite no esta identificado. Una corrida registra que comite uso, "
                "y sin nombre no hay a que referirse.",
            )
        )
    if incidencias:
        return LecturaDeComite(None, tuple(incidencias))

    return LecturaDeComite(
        ComiteDePrecios(
            nombre=nombre,
            aprobado_el=aprobado,
            horizonte=horizonte,
            sn=campos.get("sn", ()),
            cu=campos.get("cu", ()),
            ag=campos.get("ag", ()),
        ),
        (),
    )


def leer_supuestos(ruta: Path) -> LecturaDeSupuestos:
    """Lee la plantilla de supuestos del caso.

    La pestana `Comunes` trae lo que es del caso; las demas, en orden, traen lo
    que es de cada unidad: su depreciacion y su recuperacion en la refinería.
    Igual que en produccion, la unidad se asigna por posicion y no por nombre.
    """
    incidencias: list[Incidencia] = []
    if not ruta.exists():
        return LecturaDeSupuestos(None, None, (Incidencia("(archivo)", str(ruta), "no existe"),))

    libro = load_workbook(ruta, data_only=True, read_only=True)
    if HOJA_COMUN not in libro.sheetnames:
        libro.close()
        return LecturaDeSupuestos(
            None,
            None,
            (
                Incidencia(
                    "(libro)",
                    "-",
                    f"falta la hoja {HOJA_COMUN!r}. No es la plantilla de supuestos.",
                ),
            ),
        )

    horizonte = _horizonte_de_la_cabecera(libro[HOJA_COMUN], incidencias)
    if horizonte is None:
        libro.close()
        return LecturaDeSupuestos(None, None, tuple(incidencias))

    comunes = armar_filas(
        CON_DATO_DE_SUPUESTOS,
        _pares(libro[HOJA_COMUN], horizonte, incidencias),
        incidencias,
        hoja=HOJA_COMUN,
    )
    por_unidad: dict[str, dict[str, Serie]] = {}
    for nombre in libro.sheetnames:
        if normalizar(nombre) in HOJAS_SIN_DATOS or nombre == HOJA_COMUN:
            continue
        por_unidad[nombre] = armar_filas(
            CON_DATO_POR_UNIDAD,
            _pares(libro[nombre], horizonte, incidencias),
            incidencias,
            hoja=nombre,
        )
    libro.close()

    if incidencias:
        return LecturaDeSupuestos(None, horizonte, tuple(incidencias))
    return LecturaDeSupuestos(
        SupuestosDelCaso(comunes=comunes, por_unidad=por_unidad), horizonte, ()
    )


def _pares(
    hoja: Worksheet, horizonte: Horizonte, incidencias: list[Incidencia]
) -> list[tuple[str, Serie]]:
    """Etiqueta y serie de cada fila con datos de una pestana."""
    return [
        (fila.concepto, _serie(fila, horizonte, incidencias))
        for fila in _leer_pestana_de_unidad(hoja, horizonte)
    ]


def _horizonte_de_la_cabecera(hoja: Worksheet, incidencias: list[Incidencia]) -> Horizonte | None:
    """Deduce el horizonte de la fila de años, sin tope fijado de antemano."""
    anos: list[int] = []
    for celda in next(hoja.iter_rows(min_row=FILA_DE_ANOS, max_row=FILA_DE_ANOS))[
        PRIMERA_COLUMNA_DE_ANOS - 1 :
    ]:
        if not isinstance(celda.value, int | float):
            break
        anos.append(int(celda.value))

    if not anos:
        incidencias.append(
            Incidencia(
                hoja.title,
                f"C{FILA_DE_ANOS}",
                "la fila de anos esta vacia. Sin ella no se sabe que horizonte cubre la plantilla.",
            )
        )
        return None

    esperados = list(range(anos[0], anos[0] + len(anos)))
    if anos != esperados:
        incidencias.append(
            Incidencia(
                hoja.title,
                f"C{FILA_DE_ANOS}",
                f"los anos no son consecutivos: van de {anos[0]} a {anos[-1]} en {len(anos)} "
                "columnas. Un salto desplaza todas las series.",
            )
        )
        return None

    try:
        return Horizonte(primer_ano=anos[0], anos=len(anos))
    except ErrorHorizonte as error:
        incidencias.append(Incidencia(hoja.title, f"C{FILA_DE_ANOS}", str(error)))
        return None


def leer_o_fallar(ruta: Path, *, escenario: str | None = None) -> Caso:
    """Como `leer_plantilla`, pero levanta con todas las incidencias juntas."""
    lectura = leer_plantilla(ruta, escenario=escenario)
    if lectura.caso is None:
        raise ErrorDePlantilla(lectura.incidencias)
    return lectura.caso


# --- Lectura de hojas ---------------------------------------------------------


def _leer_hoja_caso(hoja: Worksheet, incidencias: list[Incidencia]) -> _Cabecera:
    """Lee la identificación, las unidades declaradas y los datos comunes."""
    etiquetas: dict[str, object] = {}
    unidades: list[_UnidadDeclarada] = []
    comunes: dict[str, float] = {}
    en_unidades = False
    en_comunes = False

    for fila in hoja.iter_rows(min_row=1, max_col=6):
        a, b, c, d, e, f = (celda.value for celda in fila)
        texto = normalizar(str(a)) if a is not None else ""
        if not texto:
            continue
        if texto == "unidades productivas declaradas":
            en_unidades, en_comunes = True, False
            continue
        if texto == "datos comunes al caso":
            en_unidades, en_comunes = False, True
            continue

        if en_unidades:
            if texto in ("unidad",) or b is None:
                continue
            unidades.append(
                _UnidadDeclarada(
                    nombre=str(a).strip(),
                    tipo=str(b).strip(),
                    metales=str(c or ""),
                    origen=str(d).strip() if d else "yacimiento",
                    etapas=str(e or "").strip(),
                    entrega_a=str(f or "").strip(),
                )
            )
        elif en_comunes:
            comunes[texto] = _numero(c, hoja.title, fila[2].coordinate, incidencias) or 0.0
        else:
            etiquetas[texto] = b

    nombre = etiquetas.get("nombre del caso")
    escenario = etiquetas.get("escenario de precios")
    return _Cabecera(
        nombre=str(nombre).strip() if nombre else "",
        escenario=str(escenario).strip() if escenario else "Base",
        horizonte=_armar_horizonte(etiquetas, hoja.title, incidencias),
        unidades=unidades,
        comunes=comunes,
    )


def _armar_horizonte(
    etiquetas: dict[str, object], hoja: str, incidencias: list[Incidencia]
) -> Horizonte | None:
    primer_ano = etiquetas.get("primer ano del horizonte")
    anos = etiquetas.get("numero de anos")
    if not isinstance(primer_ano, int | float) or not isinstance(anos, int | float):
        incidencias.append(
            Incidencia(
                hoja,
                "B6:B7",
                "el primer ano y el numero de anos son obligatorios y deben ser numeros",
            )
        )
        return None
    try:
        return Horizonte(primer_ano=int(primer_ano), anos=int(anos))
    except ErrorHorizonte as error:
        incidencias.append(Incidencia(hoja, "B6:B7", str(error)))
        return None


def _leer_pestana_de_unidad(hoja: Worksheet, horizonte: Horizonte) -> list[_Fila]:
    """Filas de la pestaña de una unidad, con su etiqueta tal cual.

    A diferencia de `_leer_hoja_de_series`, aquí no se separa el metal ni se
    borran los nombres de unidad: en `concentrado alimentado desde San Rafael`
    el nombre es el dato, y quitarlo deja una etiqueta que no significa nada.
    Las filas de sección —`Mina`, `Planta`, `Refinería`— son rótulos y se saltan.

    **La etiqueta se conserva como está escrita**, sin normalizar. Quien lee una
    estructura fija compara normalizando, así que no lo necesita; y quien admite
    conceptos propios del proyecto —la cola de opex— se queda con el nombre que
    el usuario escribió, que es el que después ve en pantalla.
    """
    filas: list[_Fila] = []
    ultima_columna = PRIMERA_COLUMNA_DE_ANOS + horizonte.anos - 1
    for fila in hoja.iter_rows(min_row=PRIMERA_FILA_DE_DATOS, max_col=ultima_columna):
        etiqueta = fila[0].value
        medida = fila[1].value
        if etiqueta is None or not str(etiqueta).strip() or medida is None:
            continue
        filas.append(
            _Fila(
                hoja=hoja.title,
                numero=int(fila[0].row or 0),
                seccion=hoja.title,
                concepto=str(etiqueta).strip(),
                metal=None,
                medida=_clave_de_medida(str(medida)),
                valores=tuple(celda.value for celda in fila[2:]),
            )
        )
    return filas


def _leer_hoja_de_series(
    hoja: Worksheet, horizonte: Horizonte, unidades: Sequence[str], incidencias: list[Incidencia]
) -> list[_Fila]:
    """Recorre una hoja de años y devuelve sus filas de datos ya traducidas.

    Las filas de sección —las que traen concepto y no traen unidad de medida—
    marcan a quién pertenece lo que viene debajo.
    """
    filas: list[_Fila] = []
    seccion = ""
    ultima_columna = PRIMERA_COLUMNA_DE_ANOS + horizonte.anos - 1

    for fila in hoja.iter_rows(min_row=PRIMERA_FILA_DE_DATOS, max_col=ultima_columna):
        etiqueta = fila[0].value
        medida = fila[1].value
        if etiqueta is None or not str(etiqueta).strip():
            continue
        if medida is None:
            seccion = str(etiqueta).strip()
            continue

        concepto, metal = canonizar(str(etiqueta), unidades)
        filas.append(
            _Fila(
                hoja=hoja.title,
                numero=int(fila[0].row or 0),
                seccion=seccion,
                concepto=concepto,
                metal=metal,
                medida=_clave_de_medida(str(medida)),
                valores=tuple(celda.value for celda in fila[2:]),
            )
        )
    return filas


# --- Armado del caso ----------------------------------------------------------


def _armar_unidades(
    cabecera: _Cabecera,
    horizonte: Horizonte,
    produccion: dict[str, list[_Fila]],
    incidencias: list[Incidencia],
) -> list[UnidadProductiva]:
    """Arma las unidades del caso. El opex y el capex llegan en su propio libro."""
    unidades: list[UnidadProductiva] = []
    for declarada in cabecera.unidades:
        nombre = declarada.nombre
        filas = [
            (fila.concepto, _serie(fila, horizonte, incidencias))
            for fila in produccion.get(nombre, [])
        ]

        unidades.append(
            UnidadProductiva(
                nombre=nombre,
                tipo=declarada.tipo,
                produccion=armar_produccion(filas, horizonte, incidencias, hoja=declarada.hoja),
                origen=declarada.origen,
                etapas=_etapas(declarada),
                entrega_a=declarada.entrega_a or None,
            )
        )
    return unidades


def _etapas(declarada: _UnidadDeclarada) -> tuple[str, ...]:
    """Etapas de la planta, tal como la hoja `Caso` las declara."""
    return tuple(e.strip() for e in declarada.etapas.split(",") if e.strip())


def _armar_terminos(
    precios: list[_Fila],
    horizonte: Horizonte,
    escenario: str,
    incidencias: list[Incidencia],
) -> TerminosComerciales:
    """Toma el juego de precios del escenario elegido y sus condiciones."""
    buscado = normalizar(f"precio escenario {escenario}")
    precio = horizonte.ceros()
    premio = horizonte.ceros()
    factor = horizonte.ceros()

    for fila in precios:
        concepto = normalizar(fila.concepto)
        if concepto == buscado:
            precio = _serie(fila, horizonte, incidencias)
        elif concepto == "premio del metal refinado":
            premio = _serie(fila, horizonte, incidencias)
        elif concepto == "factor de metal pagable":
            factor = _serie(fila, horizonte, incidencias)

    return TerminosComerciales(
        precio_metal_refinado=precio,
        premio_metal_refinado=premio,
        precio_metal_en_concentrado=precio,
        factor_metal_pagable=factor,
    )


def _armar_datos_comunes(cabecera: _Cabecera, horizonte: Horizonte) -> DatosComunes:
    """Convierte los datos comunes en series del horizonte.

    La plantilla los recoge como un valor único por concepto, así que se
    reparten iguales sobre todos los años. Un caso que necesite variarlos año a
    año lo dirá cuando Finanzas revise la plantilla.
    """
    comunes = cabecera.comunes

    def constante(clave: str) -> Serie:
        valor = float(comunes.get(clave, 0.0) or 0.0)
        return tuple(valor for _ in range(horizonte.anos))

    dias = float(comunes.get("dias de working capital", 0.0) or 0.0)
    return DatosComunes(
        gastos_administrativos=constante("gastos administrativos"),
        gestion_social=constante("inversion social"),
        otros_gastos=constante("otros gastos operativos"),
        estudios=constante("estudios"),
        exploraciones=constante("exploraciones no atribuibles a una unidad"),
        predios=constante("servidumbres y usufructos"),
        dias_por_cobrar=tuple(dias for _ in range(horizonte.anos)),
        dias_por_pagar=tuple(dias for _ in range(horizonte.anos)),
        saldo_inicial_de_perdidas=float(
            comunes.get("perdidas tributarias arrastradas", 0.0) or 0.0
        ),
    )


# --- Celdas -------------------------------------------------------------------


def _serie(fila: _Fila, horizonte: Horizonte, incidencias: list[Incidencia]) -> Serie:
    """Convierte los valores de una fila en una serie del horizonte."""
    factor = FACTORES_DE_ESCALA.get(fila.medida, 1.0)
    valores: list[float] = []
    for i in range(horizonte.anos):
        bruto = fila.valores[i] if i < len(fila.valores) else None
        celda = f"{get_column_letter(PRIMERA_COLUMNA_DE_ANOS + i)}{fila.numero}"
        numero = _numero(bruto, fila.hoja, celda, incidencias)
        valores.append((numero or 0.0) * factor)
    return tuple(valores)


def _numero(valor: object, hoja: str, celda: str, incidencias: list[Incidencia]) -> float | None:
    """Un valor de celda como número, o una incidencia localizada.

    Una celda vacía es cero y no es un error: significa que el concepto no
    aplica ese año, que es información legítima y frecuente.
    """
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    if isinstance(valor, bool):
        incidencias.append(Incidencia(hoja, celda, f"se esperaba un numero y hay {valor!r}"))
        return None
    if isinstance(valor, int | float):
        return float(valor)
    try:
        return float(str(valor).replace(",", "").replace("%", "").strip())
    except ValueError:
        incidencias.append(
            Incidencia(hoja, celda, f"se esperaba un numero y hay {str(valor)[:40]!r}")
        )
        return None
