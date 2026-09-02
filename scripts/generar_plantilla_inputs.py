"""Genera la plantilla de produccion de un caso.

**Hay una sola estructura y es siempre la misma para todos los proyectos.** No
se adapta a cada uno: un proyecto sin preconcentracion deja esas filas en cero y
la plataforma no las muestra. Eso es lo que permite que un proyecto que hoy no
existe use esta plantilla sin rehacerla.

Las etiquetas, las unidades de medida y el orden son los del libro de MINSUR, y
la estructura vive en `minsur_ingest.produccion`, que es la unica fuente de
verdad: el generador la escribe y el lector la espera.

**El libro de produccion no identifica el caso.** No lleva hoja `Caso`: el
usuario lo sube desde un caso que la plataforma ya tiene abierto, y cada pestana
se asocia a una unidad **por su orden**, no por su nombre. El nombre final lo
elige en un selector. El horizonte se deduce de la fila de anos, de modo que un
proyecto de vida larga no exige tocar nada.

**Las celdas naranjas son calculo interno.** Se llenan igual que las azules, y
ademas el sistema las rehace y avisa si el dato cargado no cuadra. Nunca las
corrige: es una alarma y un control de calidad.

Uso:
    python scripts/generar_plantilla_inputs.py --salida produccion.xlsx         --unidad "Proyecto X:mina:Sn"         --unidad "Proyecto Y:mina:Sn"         --primer-ano 2025 --anos 45

La plantilla sale **vacía**. Llenarla con datos de un caso real la convierte en
información confidencial de MINSUR: no vuelve al repositorio.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.worksheet import Worksheet

    from minsur_ingest.opex import FILAS_DE_OPEX
    from minsur_ingest.produccion import FILAS_DE_PRODUCCION
    from minsur_ingest.supuestos import (
        FILAS_DE_PRECIOS,
        FILAS_DE_SUPUESTOS,
        FILAS_POR_UNIDAD,
    )
except ImportError:  # pragma: no cover - entorno sin sincronizar
    print("Falta openpyxl o minsur_ingest. Sincroniza con: uv sync --all-packages")
    raise SystemExit(1) from None

PRIMERA_FILA_DE_DATOS = 5

TIPOS_DE_UNIDAD = ("mina", "fundicion")
ORIGENES = ("yacimiento", "relave")
ETAPAS = ("preconcentracion", "concentradora")
ETAPAS_POR_DEFECTO = ("concentradora",)
METALES = ("Sn", "Cu", "Ag")

CAPEX_ETAPAS = ["Capex inicial", "Sostenimiento", "Cierre de mina", "Otros"]
CAPEX_NATURALEZAS = [
    "No depreciable",
    "Maquinaria, equipos y vehiculos",
    "Instalaciones y equipos diversos y de comunicaciones",
    "Edificaciones y construcciones",
]
DATOS_COMUNES = [
    ("Dias de working capital", "dias"),
    ("Tratamiento del IGV en working capital", "si / no"),
    ("Perdidas tributarias arrastradas", "US$"),
    ("Costos hundidos excluidos del flujo", "US$"),
    ("Inversion social", "US$/ano"),
    ("Gastos administrativos", "US$/ano"),
    ("Otros gastos operativos", "US$/ano"),
    ("Servidumbres y usufructos", "US$/ano"),
    ("Estudios", "US$/ano"),
    ("Exploraciones no atribuibles a una unidad", "US$/ano"),
]
ESCENARIOS_DE_PRECIO = ["Base", "Alto", "Bajo"]

# Paleta del manual de marca y del propio libro de MINSUR. El azul oscuro es el
# Pantone 2767 del manual; el gris azulado de las secciones es el que trae su
# archivo de produccion.
AZUL_OSCURO = "2D314D"
BANDA_DE_SECCION = "BECBD2"
BANDA_DE_UNIDAD = "D6DCE4"

TITULO = Font(bold=True, size=12, color=AZUL_OSCURO)
CABECERA = Font(bold=True, color=AZUL_OSCURO)
CABECERA_DE_ANO = Font(bold=True, color="FFFFFF")
ETIQUETA = Font(color=AZUL_OSCURO)
MEDIDA = Font(size=9, color=AZUL_OSCURO)
ANOS = PatternFill("solid", fgColor=AZUL_OSCURO)
SECCION = PatternFill("solid", fgColor=BANDA_DE_SECCION)
UNIDAD = PatternFill("solid", fgColor=BANDA_DE_UNIDAD)
# El libro de MINSUR distingue con color lo que es dato de lo que es calculo
# interno. Se conserva la convencion: el usuario llena las dos, y las calculadas
# ademas se rehacen y se comparan.
DATO = PatternFill("solid", fgColor="DDEBF7")
CALCULADA = PatternFill("solid", fgColor="FBE5D6")


def _leer_metales(nombre: str, texto: str) -> tuple[tuple[str, ...], dict[str, str]]:
    """Interpreta `Sn,Cu,Ag@Cu`: la plata viaja en el concentrado de cobre."""
    lista: list[str] = []
    portador: dict[str, str] = {}
    for bruto in texto.split(","):
        pieza = bruto.strip()
        if not pieza:
            continue
        metal, _, dentro_de = pieza.partition("@")
        metal = metal.strip()
        if metal not in METALES:
            raise ValueError(
                f"Metal {metal!r} fuera del alcance en {nombre!r}. Use {', '.join(METALES)}"
            )
        lista.append(metal)
        if dentro_de:
            portador[metal] = dentro_de.strip()
    if not lista:
        raise ValueError(f"La unidad {nombre!r} no declara metales")
    huerfanos = [m for m, p in portador.items() if p not in lista]
    if huerfanos:
        raise ValueError(
            f"En {nombre!r}, {', '.join(huerfanos)} viaja en el concentrado de un metal que la "
            "unidad no declara."
        )
    return tuple(lista), portador


@dataclass(frozen=True)
class Unidad:
    """Una unidad productiva declarada por el caso.

    El tipo dice si saca mineral o si recibe concentrado, y el origen dice de
    donde lo saca. Una relavera es una mina cuyo origen es un deposito de
    relaves ya cerrado: tiene mineral extraido y ley igual que cualquier otra,
    y de ahi sigue la misma cadena. Tratarla como una etapa de tratamiento
    aparte, que es lo que esta plantilla hacia antes, no corresponde a ningun
    bloque del libro.
    """

    nombre: str
    tipo: str
    metales: tuple[str, ...]
    etapas: tuple[str, ...]
    origen: str = "yacimiento"
    entrega_a: str | None = None
    portador: Mapping[str, str] = field(default_factory=dict)
    """Metal que viaja dentro del concentrado de otro, y en cuál.

    En el libro la plata no tiene concentrado propio: va dentro del de cobre, y
    lo único que se declara de ella es su ley en ese concentrado. Pedirle a un
    proyecto la producción de un concentrado de plata sería pedir un dato que no
    existe.
    """

    def con_concentrado_propio(self) -> tuple[str, ...]:
        return tuple(m for m in self.metales if m not in self.portador)

    @classmethod
    def desde_texto(cls, texto: str) -> Unidad:
        partes = texto.split(":")
        if not 3 <= len(partes) <= 5:
            raise ValueError(
                f"Formato esperado nombre:tipo:metales[:etapas][:origen], recibido {texto!r}"
            )
        nombre, tipo, metales = (p.strip() for p in partes[:3])
        if tipo not in TIPOS_DE_UNIDAD:
            raise ValueError(f"Tipo {tipo!r} desconocido. Use uno de {', '.join(TIPOS_DE_UNIDAD)}")
        lista, portador = _leer_metales(nombre, metales)

        if len(partes) >= 4 and partes[3].strip():
            etapas = tuple(e.strip() for e in partes[3].split(",") if e.strip())
            desconocidas = [e for e in etapas if e not in ETAPAS]
            if desconocidas:
                raise ValueError(
                    f"Etapa(s) {', '.join(desconocidas)} desconocida(s) en {nombre!r}. "
                    f"Use {', '.join(ETAPAS)}"
                )
        elif tipo == "mina":
            etapas = ETAPAS_POR_DEFECTO
        else:
            etapas = ()

        origen = partes[4].strip() if len(partes) == 5 and partes[4].strip() else "yacimiento"
        if origen not in ORIGENES:
            raise ValueError(
                f"Origen {origen!r} desconocido en {nombre!r}. Use {', '.join(ORIGENES)}"
            )
        return cls(nombre, tipo, lista, etapas, origen, portador=portador)

    @property
    def es_fundicion(self) -> bool:
        return self.tipo == "fundicion"

    def aplica(self, etapa: str | None) -> bool:
        """Si la fila condicionada por `etapa` corresponde a esta unidad."""
        if etapa is None:
            return True
        if etapa == "fundicion":
            return self.es_fundicion
        if etapa == "relavera":
            return self.origen == "relave"
        return etapa in self.etapas


def encabezar(hoja: Worksheet, titulo: str, primer_ano: int, anos: int) -> None:
    """Escribe el titulo, la leyenda y la fila de anos, y fija los paneles."""
    hoja["A1"] = titulo
    hoja["A1"].font = TITULO
    hoja["A1"].fill = UNIDAD
    hoja["A2"] = "Azul: dato que se carga.  Naranja: se carga y ademas el sistema lo recalcula."
    hoja["A2"].font = MEDIDA
    hoja["A3"] = "Concepto"
    hoja["B3"] = "Unidad"
    for celda in (hoja["A3"], hoja["B3"]):
        celda.font = CABECERA_DE_ANO
        celda.fill = ANOS
    for i in range(anos):
        celda = hoja.cell(row=3, column=3 + i, value=primer_ano + i)
        celda.font = CABECERA_DE_ANO
        celda.fill = ANOS
        celda.alignment = Alignment(horizontal="center")
    hoja.column_dimensions["A"].width = 42
    hoja.column_dimensions["B"].width = 8
    for i in range(anos):
        hoja.column_dimensions[get_column_letter(3 + i)].width = 12
    hoja.freeze_panes = "C4"


def fila_de_seccion(hoja: Worksheet, fila: int, texto: str, anos: int) -> int:
    celda = hoja.cell(row=fila, column=1, value=texto)
    celda.font = CABECERA
    for col in range(1, 3 + anos):
        hoja.cell(row=fila, column=col).fill = SECCION
    return fila + 1


def fila_de_entrada(
    hoja: Worksheet,
    fila: int,
    concepto: str,
    unidad: str,
    anos: int,
    calculada: bool = False,
) -> int:
    """Escribe una fila de datos.

    Las calculadas se pintan distinto: son las que el sistema rehace para avisar
    si el dato cargado no cuadra. Se llenan igual que las demas, porque el
    recalculo audita el dato y no lo sustituye. Es la misma convencion de color
    que usa el libro de produccion de MINSUR.
    """
    etiqueta = hoja.cell(row=fila, column=1, value=concepto)
    etiqueta.font = ETIQUETA
    medida = hoja.cell(row=fila, column=2, value=unidad)
    medida.font = MEDIDA
    relleno = CALCULADA if calculada else DATO
    for col in range(3, 3 + anos):
        hoja.cell(row=fila, column=col).fill = relleno
    return fila + 1


def validacion_numerica(hoja: Worksheet, filas: list[int], anos: int) -> None:
    """Impide texto en las celdas de datos, que es el error de carga más común."""
    if not filas:
        return
    rangos = " ".join(f"C{f}:{get_column_letter(2 + anos)}{f}" for f in filas)
    validacion = DataValidation(
        type="decimal",
        operator="greaterThanOrEqual",
        formula1="-1000000000",
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Valor no numerico",
        error="Esta celda espera un numero. Deje la celda vacia si el dato no aplica.",
    )
    hoja.add_data_validation(validacion)
    validacion.sqref = rangos


def hoja_caso(libro: Workbook, unidades: list[Unidad], primer_ano: int, anos: int) -> None:
    hoja = libro.active
    hoja.title = "Caso"
    hoja["A1"] = "Identificacion del caso"
    hoja["A1"].font = TITULO
    campos = [
        ("Nombre del caso", ""),
        ("Categoria", ""),
        ("Responsable", ""),
        ("Primer ano del horizonte", primer_ano),
        ("Numero de anos", anos),
        ("Ano de valuacion", ""),
        ("Version de datos maestros", ""),
        ("Escenario de precios", ESCENARIOS_DE_PRECIO[0]),
    ]
    for i, (etiqueta, valor) in enumerate(campos, start=3):
        hoja.cell(row=i, column=1, value=etiqueta).font = CABECERA
        celda = hoja.cell(row=i, column=2, value=valor)
        celda.fill = DATO

    fila = len(campos) + 5
    hoja.cell(row=fila, column=1, value="Unidades productivas declaradas").font = TITULO
    fila += 2
    # Las etapas y el origen viajan en la tabla y no en la hoja de
    # instrucciones: son los que deciden que filas tiene cada pestana, y si el
    # lector no los ve, de una plantilla llena no se puede regenerar la misma
    # plantilla.
    for columna, titulo in enumerate(
        ("Unidad", "Tipo", "Metales", "Origen", "Etapas", "Entrega a"), start=1
    ):
        hoja.cell(row=fila, column=columna, value=titulo).font = CABECERA
    fila += 1
    for unidad in unidades:
        hoja.cell(row=fila, column=1, value=unidad.nombre)
        hoja.cell(row=fila, column=2, value=unidad.tipo)
        hoja.cell(row=fila, column=3, value=", ".join(unidad.metales))
        hoja.cell(row=fila, column=4, value=unidad.origen)
        hoja.cell(row=fila, column=5, value=", ".join(unidad.etapas))
        hoja.cell(row=fila, column=6, value=unidad.entrega_a or "")
        fila += 1

    fila += 2
    hoja.cell(row=fila, column=1, value="Datos comunes al caso").font = TITULO
    fila += 2
    for concepto, unidad_medida in DATOS_COMUNES:
        hoja.cell(row=fila, column=1, value=concepto)
        hoja.cell(row=fila, column=2, value=unidad_medida)
        hoja.cell(row=fila, column=3).fill = DATO
        fila += 1

    hoja.column_dimensions["A"].width = 52
    hoja.column_dimensions["B"].width = 22
    hoja.column_dimensions["C"].width = 22


def hoja_produccion_de_unidad(libro: Workbook, nombre: str, primer_ano: int, anos: int) -> None:
    """Una pestana por proyecto, con la estructura estandar de MINSUR.

    La estructura no se adapta al proyecto: es siempre la misma. Uno sin
    preconcentracion deja esas filas en cero y la plataforma no las muestra.
    Eso es lo que permite que un proyecto que hoy no existe use esta plantilla
    sin rehacerla, y lo que deja leerla por secuencia.
    """
    hoja = libro.create_sheet(_nombre_de_hoja(nombre))
    encabezar(hoja, nombre, primer_ano, anos)
    fila, numericas = PRIMERA_FILA_DE_DATOS, []
    for definicion in FILAS_DE_PRODUCCION:
        if definicion.es_seccion:
            fila = fila_de_seccion(hoja, fila, definicion.etiqueta, anos)
            continue
        numericas.append(fila)
        fila = fila_de_entrada(
            hoja,
            fila,
            definicion.etiqueta,
            definicion.medida or "",
            anos,
            definicion.calculada,
        )
    validacion_numerica(hoja, numericas, anos)


def _nombre_de_hoja(nombre: str) -> str:
    """Excel limita el nombre de una hoja a 31 caracteres y prohibe varios."""
    limpio = "".join(c for c in nombre if c not in r"[]:*?/'")
    return limpio[:31] or "Proyecto"


def _hoja_de_filas(
    libro: Workbook,
    nombre: str,
    titulo: str,
    definicion: object,
    primer_ano: int,
    anos: int,
) -> None:
    """Escribe una pestana a partir de una estructura fija de filas."""
    hoja = libro.create_sheet(_nombre_de_hoja(nombre))
    encabezar(hoja, titulo, primer_ano, anos)
    fila, numericas = PRIMERA_FILA_DE_DATOS, []
    for definida in definicion:  # type: ignore[attr-defined]
        if definida.medida is None:
            fila = fila_de_seccion(hoja, fila, definida.etiqueta, anos)
            continue
        numericas.append(fila)
        fila = fila_de_entrada(
            hoja, fila, definida.etiqueta, definida.medida, anos, definida.calculada
        )
    validacion_numerica(hoja, numericas, anos)


def hoja_comite_de_precios(libro: Workbook, primer_ano: int, anos: int) -> None:
    """La plantilla que sube Finanzas: precios aprobados y nada mas.

    Va separada de los demas supuestos porque tiene otro dueno. Es dato maestro:
    Finanzas la aprueba y la sube, y quien modela solo elige que comite usa.
    Mezclarla con los supuestos del caso dejaria a cualquiera cambiando un precio
    aprobado sin que nadie lo advierta.
    """
    hoja = libro.create_sheet("Comite de Precios")
    encabezar(hoja, "Comite de Precios", primer_ano, anos)
    # Un comite se identifica, porque una corrida registra cual uso y no "el
    # vigente": publicar uno nuevo no puede reescribir evaluaciones pasadas.
    hoja["A2"] = "Comite"
    hoja["A2"].font = CABECERA
    hoja["B2"].fill = DATO
    hoja["C2"] = "Aprobado el"
    hoja["C2"].font = CABECERA
    hoja["D2"].fill = DATO

    fila, numericas = PRIMERA_FILA_DE_DATOS, []
    for definida in FILAS_DE_PRECIOS:
        if definida.medida is None:
            fila = fila_de_seccion(hoja, fila, definida.etiqueta, anos)
            continue
        numericas.append(fila)
        fila = fila_de_entrada(hoja, fila, definida.etiqueta, definida.medida, anos)
    validacion_numerica(hoja, numericas, anos)


def hoja_supuestos(libro: Workbook, primer_ano: int, anos: int) -> None:
    _hoja_de_filas(libro, "Comunes", "Supuestos del caso", FILAS_DE_SUPUESTOS, primer_ano, anos)


def hoja_supuestos_de_unidad(libro: Workbook, nombre: str, primer_ano: int, anos: int) -> None:
    _hoja_de_filas(libro, nombre, f"Supuestos de {nombre}", FILAS_POR_UNIDAD, primer_ano, anos)


def hoja_opex_de_unidad(libro: Workbook, nombre: str, primer_ano: int, anos: int) -> None:
    """Una pestana de opex, con la misma estructura para todas las unidades.

    La refinería tambien la lleva, a diferencia de produccion: sus toneladas son
    resultado, pero su costo es un dato como el de cualquier mina.
    """
    _hoja_de_filas(libro, nombre, f"Opex de {nombre}", FILAS_DE_OPEX, primer_ano, anos)


def hoja_capex(libro: Workbook, unidades: list[Unidad], primer_ano: int, anos: int) -> None:
    hoja = libro.create_sheet("Capex")
    encabezar(hoja, "Capital por unidad, etapa y naturaleza contable, en US$", primer_ano, anos)
    fila, numericas = 5, []
    for unidad in unidades:
        fila = fila_de_seccion(hoja, fila, f"{unidad.nombre} ({unidad.tipo})", anos)
        for etapa in CAPEX_ETAPAS:
            fila = fila_de_seccion(hoja, fila, f"  {etapa}", anos)
            for naturaleza in CAPEX_NATURALEZAS:
                numericas.append(fila)
                fila = fila_de_entrada(hoja, fila, f"    {naturaleza}", "US$", anos)
        fila += 1
    validacion_numerica(hoja, numericas, anos)


def hoja_precios(libro: Workbook, unidades: list[Unidad], primer_ano: int, anos: int) -> None:
    hoja = libro.create_sheet("Precios")
    encabezar(hoja, "Precios y terminos comerciales por metal", primer_ano, anos)
    metales = sorted({metal for unidad in unidades for metal in unidad.metales})
    fila, numericas = 5, []
    for metal in metales:
        fila = fila_de_seccion(hoja, fila, metal, anos)
        for escenario in ESCENARIOS_DE_PRECIO:
            numericas.append(fila)
            fila = fila_de_entrada(hoja, fila, f"Precio, escenario {escenario}", "US$/t", anos)
        for concepto, medida in (
            # El libro vende el metal por dos caminos: refinado al precio mas
            # un premio, y en concentrado al precio por el factor pagable.
            ("Premio del metal refinado", "US$/t"),
            ("Factor de metal pagable", "fraccion"),
            ("Terminos comerciales", "US$/t"),
            ("Gasto de ventas", "US$/t"),
            ("Fletes", "US$/t"),
        ):
            numericas.append(fila)
            fila = fila_de_entrada(hoja, fila, concepto, medida, anos)
        fila += 1
    validacion_numerica(hoja, numericas, anos)


def _leeme_del_bloque(bloque: str) -> list[tuple[str, Font | None]]:
    """Lo que cambia entre plantillas, que es mas de lo que comparten."""
    if bloque == "opex":
        return [
            ("Todo lo que se pide aqui es dato", CABECERA),
            ("Ninguna fila se recalcula ni se corrobora: el libro corporativo no", None),
            ("carga en este bloque ningun valor derivado. Los totales, el costo por", None),
            ("tonelada y los subtotales de la refinería los calcula la plataforma y no", None),
            ("se piden. Tampoco la planilla, que sale del cash cost de la unidad por", None),
            ("la tasa de los supuestos, ni la parte deducible de la gestion social.", None),
            ("", None),
            ("Una pestana por unidad, y la refinería tambien lleva la suya", CABECERA),
            ("Su produccion es resultado de lo que le entregan las minas, pero su", None),
            ("costo es un dato como el de cualquiera. Por eso este libro trae una", None),
            ("pestana mas que el de produccion.", None),
            ("", None),
            ("Los conceptos propios del proyecto van en la cola", CABECERA),
            ("Bajo `Otros conceptos` hay filas en blanco para lo que este proyecto", None),
            ("tenga y el catalogo no recoja: se escribe el nombre en la columna A y", None),
            ("su serie al lado. Solo afectan al total. No se agregan mas filas de las", None),
            ("que hay, ni se escriben importes sin nombrar el concepto.", None),
            ("", None),
            ("Los importes van en miles de dolares", CABECERA),
            ("Es lo que dice la columna de unidad, y es la escala del libro. La", None),
            ("plataforma convierte al leer.", None),
            ("", None),
        ]
    return [
        ("Las celdas verdes son corroborables", CABECERA),
        ("Se llenan igual que las crema. La diferencia es que el sistema las", None),
        ("recalcula a partir del resto de la cadena y avisa si el dato cargado no", None),
        ("cuadra. El dato cargado es el que se usa: el recalculo lo audita, no lo", None),
        ("sustituye.", None),
        ("", None),
        ("Una pestana por proyecto", CABECERA),
        ("Cada unidad tiene su hoja, con los sub-bloques Mina y Planta: de donde", None),
        ("sale el mineral y por que proceso pasa. Cada corriente de tonelaje lleva", None),
        ("debajo la ley de cada metal que transporta.", None),
        ("", None),
    ]


def hoja_instrucciones(libro: Workbook, unidades: list[Unidad], bloque: str = "produccion") -> None:
    """Escribe la hoja `Leeme`, con lo propio del bloque que se este emitiendo.

    Las tres plantillas comparten la asociacion por orden y la estructura fija,
    pero no lo demas: opex no tiene filas corroborables ni sub-bloques de mina y
    planta, y ahi la refinería si lleva pestana. Una sola hoja para las tres
    describia la de produccion y contradecia a las otras.
    """
    hoja = libro.create_sheet("Leeme")
    lineas = [
        ("Plantilla canonica de inputs", TITULO),
        ("", None),
        ("Las celdas con color son las que se llenan. El resto es estructura.", None),
        ("Una celda vacia significa que el concepto no aplica ese ano.", None),
        ("", None),
    ]
    lineas += _leeme_del_bloque(bloque)
    lineas += [
        ("Las pestanas se asocian por orden", CABECERA),
        ("La plataforma toma la primera pestana como la primera unidad del caso,", None),
        ("la segunda como la segunda, y asi. El nombre de la pestana es solo una", None),
        ("pista: el nombre final lo elige quien carga, en un selector.", None),
        ("No cambie el orden de las pestanas despues de llenarlas.", None),
        ("", None),
        ("La estructura la determinan las unidades declaradas al generar la", None),
        ("plantilla. Si el caso necesita otra unidad, se vuelve a generar; no se", None),
        ("agregan filas a mano, porque el motor lee la estructura, no el formato.", None),
        ("", None),
        ("Unidades de este caso:", CABECERA),
    ]
    for unidad in unidades:
        detalle = [
            unidad.tipo,
            f"origen: {unidad.origen}",
            f"metales: {', '.join(unidad.metales)}",
        ]
        if unidad.etapas:
            detalle.append(f"etapas: {', '.join(unidad.etapas)}")
        if unidad.entrega_a:
            detalle.append(f"entrega a: {unidad.entrega_a}")
        lineas.append((f"  {unidad.nombre} — {' — '.join(detalle)}", None))
    lineas += [
        ("", None),
        ("Confidencialidad", CABECERA),
        ("Llenada con datos de un caso real, esta plantilla es informacion", None),
        ("confidencial de MINSUR y no vuelve al repositorio de codigo.", None),
        ("", None),
        ("Referencia", CABECERA),
        ("docs/modelo-economico/catalogo-inputs.md define cada concepto.", None),
        ("docs/modelo-economico/modelo-estandar.md explica las entidades.", None),
    ]
    for i, (texto, fuente) in enumerate(lineas, start=1):
        celda = hoja.cell(row=i, column=1, value=texto)
        if fuente is not None:
            celda.font = fuente
    hoja.column_dimensions["A"].width = 80


def _encadenar(unidades: list[Unidad]) -> list[Unidad]:
    """Dirige el concentrado de cada mina a la fundicion, si el caso declara una.

    No se pide como campo aparte porque el caso admite una sola fundicion, y en
    el libro las cinco minas entregan a Pisco. Un proyecto que venda su
    concentrado directo simplemente no declara fundicion.
    """
    fundiciones = [u for u in unidades if u.es_fundicion]
    if len(fundiciones) > 1:
        raise ValueError(
            "El caso declara mas de una fundicion. El tope de capacidad se aplica sobre el "
            "concentrado de la refinería y no sabria a cual acotar."
        )
    if not fundiciones:
        return unidades
    destino = fundiciones[0].nombre
    return [u if u.es_fundicion else replace(u, entrega_a=destino) for u in unidades]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--salida", type=Path, required=True, help="Ruta del .xlsx a escribir")
    p.add_argument(
        "--unidad",
        action="append",
        required=True,
        metavar="NOMBRE:TIPO:METALES[:ETAPAS][:ORIGEN]",
        help=f"Unidad productiva. TIPO en {{{', '.join(TIPOS_DE_UNIDAD)}}}",
    )
    p.add_argument("--primer-ano", type=int, required=True)
    p.add_argument("--anos", type=int, default=36)
    p.add_argument(
        "--bloque",
        choices=("produccion", "opex", "supuestos", "precios", "completo"),
        default="produccion",
        help="Bloque a emitir. 'completo' mantiene el libro unico anterior.",
    )
    args = p.parse_args()

    try:
        unidades = [Unidad.desde_texto(u) for u in args.unidad]
    except ValueError as error:
        print(f"Declaracion de unidad invalida: {error}")
        return 1

    if not 1 <= args.anos <= 60:
        print("El horizonte debe estar entre 1 y 60 anos.")
        return 1

    try:
        unidades = _encadenar(unidades)
    except ValueError as error:
        print(f"Declaracion de unidad invalida: {error}")
        return 1

    libro = Workbook()
    if args.bloque == "precios":
        libro.remove(libro.active)
        hoja_comite_de_precios(libro, args.primer_ano, args.anos)
        return _guardar(libro, args)

    if args.bloque == "opex":
        # Aqui la refinería si lleva pestana: su costo es dato. Por eso el libro
        # de opex trae una pestana mas que el de produccion.
        libro.remove(libro.active)
        for unidad in unidades:
            hoja_opex_de_unidad(libro, unidad.nombre, args.primer_ano, args.anos)
        hoja_instrucciones(libro, unidades, "opex")
        return _guardar(libro, args)

    if args.bloque == "supuestos":
        libro.remove(libro.active)
        hoja_supuestos(libro, args.primer_ano, args.anos)
        for unidad in unidades:
            hoja_supuestos_de_unidad(libro, unidad.nombre, args.primer_ano, args.anos)
        hoja_instrucciones(libro, unidades)
        return _guardar(libro, args)

    if args.bloque == "completo":
        hoja_caso(libro, unidades, args.primer_ano, args.anos)
    else:
        # La plantilla de produccion no identifica el caso. El usuario sube el
        # archivo desde un caso que la plataforma ya tiene abierto, y las
        # pestanas se asocian a sus unidades por orden, no por nombre: repetir
        # aqui la identificacion abre la puerta a que contradiga a la del caso.
        libro.remove(libro.active)
    # La refinería no tiene pestana: sus filas son resultado de lo que producen
    # las minas, y sus dos supuestos —capacidad y recuperacion— viven en la
    # hoja Supuestos del libro corporativo, no en produccion.
    for unidad in unidades:
        if unidad.es_fundicion:
            continue
        hoja_produccion_de_unidad(libro, unidad.nombre, args.primer_ano, args.anos)
    if args.bloque == "completo":
        # Capex y precios siguen en hojas unicas con las unidades apiladas. Les
        # toca su propia plantilla mas adelante; el opex ya tiene la suya.
        hoja_capex(libro, unidades, args.primer_ano, args.anos)
        hoja_precios(libro, unidades, args.primer_ano, args.anos)
    hoja_instrucciones(libro, unidades)

    return _guardar(libro, args)


def _guardar(libro: Workbook, args: argparse.Namespace) -> int:
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    libro.save(args.salida)
    print(f"Plantilla escrita en {args.salida}")
    print(f"  {args.anos} anos desde {args.primer_ano}")
    print(f"  hojas: {', '.join(libro.sheetnames)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
