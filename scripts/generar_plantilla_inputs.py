"""Genera la plantilla canónica de inputs de un caso.

La plantilla no es un archivo fijo: se construye a partir de las unidades
productivas que el caso declare, porque el catálogo de inputs demostró que las
hojas del modelo repiten el mismo bloque de conceptos por unidad. Un proyecto
con una mina y un metal recibe la misma estructura que uno con cuatro unidades
y tres metales, instanciada menos veces.

Se genera desde `docs/modelo-economico/catalogo-inputs.md`, del que este script
es la contraparte ejecutable: los conceptos de aquí y los del catálogo son los
mismos, y si divergen, manda el catálogo y este archivo se corrige.

Uso:
    python scripts/generar_plantilla_inputs.py --salida plantilla.xlsx \
        --unidad "Proyecto X:mina:Sn,Cu" \
        --unidad "San Rafael:mina:Sn:preconcentracion,concentradora" \
        --primer-ano 2027 --anos 20

El cuarto campo declara las etapas de tratamiento de la unidad y es opcional.
Sin el, una mina se describe con su concentradora y nada mas, que es el caso
general: la preconcentracion y la relavera existen en algunas unidades y pedir
sus datos a un proyecto que no las tiene es pedir un dato que no existe.

La plantilla sale **vacía**. Llenarla con datos de un caso real la convierte en
información confidencial de MINSUR: no vuelve al repositorio.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.worksheet import Worksheet
except ImportError:  # pragma: no cover - entorno sin sincronizar
    print("Falta openpyxl. Sincroniza el entorno con: uv sync --all-packages")
    raise SystemExit(1) from None

TIPOS_DE_UNIDAD = ("mina", "preconcentracion", "concentradora", "relavera", "fundicion")
ETAPAS = ("preconcentracion", "concentradora", "relavera", "fundicion")
ETAPAS_POR_DEFECTO = ("concentradora",)

# Conceptos por dominio. El orden reproduce el del libro corporativo, que es el
# que Finanzas reconoce al revisar la plantilla. La tercera posicion es la etapa
# que condiciona la fila: None significa que la fila va siempre.
PRODUCCION_POR_UNIDAD = [
    ("Mineral extraido", "t", None),
    ("Mineral tratado en preconcentracion", "t", "preconcentracion"),
    ("Mineral preconcentrado a concentradora", "t", "preconcentracion"),
    ("Mineral directo a planta concentradora", "t", "concentradora"),
    ("Mineral tratado total en concentradora", "t", "concentradora"),
    ("Mineral tratado total para cash cost", "t", None),
    ("Mineral tratado de relaves", "t", "relavera"),
    # El libro encadena unidades: el concentrado de una alimenta a otra, y el
    # sobrante se vende. Sin estas dos filas, una unidad no puede describir de
    # donde recibe ni a donde entrega.
    ("Concentrado alimentado desde otra unidad", "t", None),
    ("Concentrado excedente", "t", None),
    ("Toneladas alimentadas mas escoria", "t", "fundicion"),
    # Regla 002: el libro escribia la capacidad dentro de la formula. Finanzas
    # confirmo el 01/09/2026 que es dato editable, y por eso es una fila mas.
    ("Capacidad maxima de tratamiento", "t", "fundicion"),
]
PRODUCCION_POR_METAL = [
    ("Ley de cabeza", "%", None),
    ("Ley de entrada a preconcentracion", "%", "preconcentracion"),
    ("Recuperacion", "%", None),
    ("Toneladas finas", "tmf", None),
    ("Ley del concentrado", "%", None),
    ("Produccion de concentrado", "t", None),
    ("Metal contenido en el concentrado", "tmf", None),
    ("Produccion de metal refinado", "tmf", "fundicion"),
]
OPEX_POR_UNIDAD = [
    ("Exploraciones", None),
    ("Geologia", None),
    ("Mina", None),
    ("Planta de preconcentracion", "preconcentracion"),
    ("Planta concentradora", "concentradora"),
    ("Fundicion", "fundicion"),
    ("Refineria", "fundicion"),
    ("Planta de subproductos", "fundicion"),
    ("Mantenimiento", None),
    ("Energia", None),
    ("Linea de transmision", None),
    ("Agua potable", None),
    ("Planilla", None),
    ("Apoyo", None),
    ("Gestion social", None),
    ("Predios, servidumbres y usufructos", None),
    ("Estudios y optimizaciones", None),
    ("Relavera", "relavera"),
]
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

TITULO = Font(bold=True, size=12)
CABECERA = Font(bold=True)
SECCION = PatternFill("solid", fgColor="DDDDDD")
ENTRADA = PatternFill("solid", fgColor="FFF6CC")


@dataclass(frozen=True)
class Unidad:
    """Una unidad productiva declarada por el caso."""

    nombre: str
    tipo: str
    metales: tuple[str, ...]
    etapas: tuple[str, ...]

    @classmethod
    def desde_texto(cls, texto: str) -> Unidad:
        partes = texto.split(":")
        if len(partes) not in (3, 4):
            raise ValueError(f"Formato esperado nombre:tipo:metales[:etapas], recibido {texto!r}")
        nombre, tipo, metales = (p.strip() for p in partes[:3])
        if tipo not in TIPOS_DE_UNIDAD:
            raise ValueError(f"Tipo {tipo!r} desconocido. Use uno de {', '.join(TIPOS_DE_UNIDAD)}")
        lista = tuple(m.strip() for m in metales.split(",") if m.strip())
        if not lista:
            raise ValueError(f"La unidad {nombre!r} no declara metales")

        if len(partes) == 4:
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
            etapas = (tipo,)
        return cls(nombre, tipo, lista, etapas)

    def aplica(self, etapa: str | None) -> bool:
        return etapa is None or etapa in self.etapas


def encabezar(hoja: Worksheet, titulo: str, primer_ano: int, anos: int) -> None:
    """Escribe el título y la fila de años, y fija los paneles."""
    hoja["A1"] = titulo
    hoja["A1"].font = TITULO
    hoja["A3"] = "Concepto"
    hoja["B3"] = "Unidad"
    hoja["A3"].font = CABECERA
    hoja["B3"].font = CABECERA
    for i in range(anos):
        celda = hoja.cell(row=3, column=3 + i, value=primer_ano + i)
        celda.font = CABECERA
        celda.alignment = Alignment(horizontal="center")
    hoja.column_dimensions["A"].width = 52
    hoja.column_dimensions["B"].width = 12
    for i in range(anos):
        hoja.column_dimensions[get_column_letter(3 + i)].width = 11
    hoja.freeze_panes = "C4"


def fila_de_seccion(hoja: Worksheet, fila: int, texto: str, anos: int) -> int:
    celda = hoja.cell(row=fila, column=1, value=texto)
    celda.font = CABECERA
    for col in range(1, 3 + anos):
        hoja.cell(row=fila, column=col).fill = SECCION
    return fila + 1


def fila_de_entrada(hoja: Worksheet, fila: int, concepto: str, unidad: str, anos: int) -> int:
    hoja.cell(row=fila, column=1, value=concepto)
    hoja.cell(row=fila, column=2, value=unidad)
    for col in range(3, 3 + anos):
        hoja.cell(row=fila, column=col).fill = ENTRADA
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
        celda.fill = ENTRADA

    fila = len(campos) + 5
    hoja.cell(row=fila, column=1, value="Unidades productivas declaradas").font = TITULO
    fila += 2
    for columna, titulo in enumerate(("Unidad", "Tipo", "Metales"), start=1):
        hoja.cell(row=fila, column=columna, value=titulo).font = CABECERA
    fila += 1
    for unidad in unidades:
        hoja.cell(row=fila, column=1, value=unidad.nombre)
        hoja.cell(row=fila, column=2, value=unidad.tipo)
        hoja.cell(row=fila, column=3, value=", ".join(unidad.metales))
        fila += 1

    fila += 2
    hoja.cell(row=fila, column=1, value="Datos comunes al caso").font = TITULO
    fila += 2
    for concepto, unidad_medida in DATOS_COMUNES:
        hoja.cell(row=fila, column=1, value=concepto)
        hoja.cell(row=fila, column=2, value=unidad_medida)
        hoja.cell(row=fila, column=3).fill = ENTRADA
        fila += 1

    hoja.column_dimensions["A"].width = 52
    hoja.column_dimensions["B"].width = 22
    hoja.column_dimensions["C"].width = 22


def hoja_produccion(libro: Workbook, unidades: list[Unidad], primer_ano: int, anos: int) -> None:
    hoja = libro.create_sheet("Produccion")
    encabezar(hoja, "Produccion por unidad productiva", primer_ano, anos)
    fila, numericas = 5, []
    for unidad in unidades:
        fila = fila_de_seccion(hoja, fila, f"{unidad.nombre} ({unidad.tipo})", anos)
        for concepto, medida, etapa in PRODUCCION_POR_UNIDAD:
            if not unidad.aplica(etapa):
                continue
            numericas.append(fila)
            fila = fila_de_entrada(hoja, fila, concepto, medida, anos)
        for metal in unidad.metales:
            for concepto, medida, etapa in PRODUCCION_POR_METAL:
                if not unidad.aplica(etapa):
                    continue
                numericas.append(fila)
                fila = fila_de_entrada(hoja, fila, f"{concepto} de {metal}", medida, anos)
        fila += 1
    validacion_numerica(hoja, numericas, anos)


def hoja_opex(libro: Workbook, unidades: list[Unidad], primer_ano: int, anos: int) -> None:
    hoja = libro.create_sheet("Opex")
    encabezar(hoja, "Costo operativo por unidad productiva, en US$", primer_ano, anos)
    fila, numericas = 5, []
    for unidad in unidades:
        fila = fila_de_seccion(hoja, fila, f"{unidad.nombre} ({unidad.tipo})", anos)
        for concepto, etapa in OPEX_POR_UNIDAD:
            if not unidad.aplica(etapa):
                continue
            numericas.append(fila)
            fila = fila_de_entrada(hoja, fila, concepto, "US$", anos)
        # El acuerdo 6 de la minuta del 27/08/2026 exige que la lista sea
        # extensible: estas filas quedan para conceptos propios del proyecto.
        for _ in range(3):
            numericas.append(fila)
            fila = fila_de_entrada(hoja, fila, "", "US$", anos)
        fila += 1
    validacion_numerica(hoja, numericas, anos)


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


def hoja_instrucciones(libro: Workbook, unidades: list[Unidad]) -> None:
    hoja = libro.create_sheet("Leeme")
    lineas = [
        ("Plantilla canonica de inputs", TITULO),
        ("", None),
        ("Las celdas con fondo crema son las que se llenan. El resto es estructura.", None),
        ("Una celda vacia significa que el concepto no aplica ese ano.", None),
        ("", None),
        ("La estructura la determinan las unidades productivas declaradas al generar", None),
        ("la plantilla. Si el caso necesita otra unidad, se vuelve a generar; no se", None),
        ("agregan filas a mano, porque el motor lee la estructura, no el formato.", None),
        ("", None),
        ("Unidades de este caso:", CABECERA),
    ]
    for unidad in unidades:
        lineas.append(
            (
                f"  {unidad.nombre} — {unidad.tipo} — metales: {', '.join(unidad.metales)}"
                f" — etapas: {', '.join(unidad.etapas)}",
                None,
            )
        )
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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--salida", type=Path, required=True, help="Ruta del .xlsx a escribir")
    p.add_argument(
        "--unidad",
        action="append",
        required=True,
        metavar="NOMBRE:TIPO:METALES",
        help=f"Unidad productiva. TIPO en {{{', '.join(TIPOS_DE_UNIDAD)}}}",
    )
    p.add_argument("--primer-ano", type=int, required=True)
    p.add_argument("--anos", type=int, default=36)
    args = p.parse_args()

    try:
        unidades = [Unidad.desde_texto(u) for u in args.unidad]
    except ValueError as error:
        print(f"Declaracion de unidad invalida: {error}")
        return 1

    if not 1 <= args.anos <= 60:
        print("El horizonte debe estar entre 1 y 60 anos.")
        return 1

    libro = Workbook()
    hoja_caso(libro, unidades, args.primer_ano, args.anos)
    hoja_produccion(libro, unidades, args.primer_ano, args.anos)
    hoja_opex(libro, unidades, args.primer_ano, args.anos)
    hoja_capex(libro, unidades, args.primer_ano, args.anos)
    hoja_precios(libro, unidades, args.primer_ano, args.anos)
    hoja_instrucciones(libro, unidades)

    args.salida.parent.mkdir(parents=True, exist_ok=True)
    libro.save(args.salida)

    print(f"Plantilla escrita en {args.salida}")
    print(f"  {len(unidades)} unidad(es), {args.anos} anos desde {args.primer_ano}")
    print(f"  hojas: {', '.join(libro.sheetnames)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
