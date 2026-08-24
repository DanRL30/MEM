"""Disección del modelo económico de referencia.

PT1.4 tiene tres días en ruta crítica y arranca el día que Finanzas entregue el
libro corporativo (`R-02`). Ese análisis, hecho a mano, se va en abrir hojas y
rastrear fórmulas. Esta herramienta lo hace en minutos y deja al modelador el
trabajo que sí requiere criterio: decidir qué reglas son intencionales y cuáles
son accidentes que Finanzas debe confirmar.

Lo que busca es, específicamente, lo que después causa discrepancias en el
contraste N0–N3:

  - Constantes incrustadas en fórmulas (una tasa escrita a mano en una celda)
  - Redondeos explícitos, que cambian el resultado y rara vez están documentados
  - Referencias circulares, típicas en el cálculo de participación e impuestos
  - Macros VBA, que pueden alterar valores fuera de la cadena de fórmulas
  - Nombres definidos rotos y referencias a libros externos
  - Celdas de entrada mezcladas con celdas calculadas

Uso:
    python scripts/diseccionar_modelo.py <modelo.xlsx> --salida informe/

No modifica el archivo de entrada. Lo abre en solo lectura.

IMPORTANTE: el modelo de referencia es confidencial. El informe que produce
esta herramienta contiene fórmulas y valores del modelo, así que hereda esa
clasificación: va a 00-gestion/03-insumos-minsur/, nunca al repositorio.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("Falta openpyxl. Instálalo con: uv sync")
    sys.exit(1)


# Funciones cuyo uso conviene inventariar: son las que suelen esconder reglas
# no documentadas o comportamiento difícil de reproducir.
FUNCIONES_DE_INTERES = [
    "ROUND", "ROUNDUP", "ROUNDDOWN", "MROUND", "TRUNC", "INT",
    "REDONDEAR", "REDONDEAR.MAS", "REDONDEAR.MENOS", "TRUNCAR", "ENTERO",
    "IRR", "XIRR", "NPV", "XNPV", "TIR", "TIR.NO.PER", "VNA", "VNA.NO.PER",
    "OFFSET", "INDIRECT", "DESREF", "INDIRECTO",
    "IFERROR", "SI.ERROR", "NA", "ND",
    "VLOOKUP", "BUSCARV", "INDEX", "INDICE", "MATCH", "COINCIDIR",
    "SUMIF", "SUMIFS", "SUMAR.SI", "SUMAR.SI.CONJUNTO",
]

# Un número dentro de una fórmula, ignorando referencias de celda (A1, $B$2),
# índices de función y los valores triviales 0 y 1.
NUMERO_EN_FORMULA = re.compile(r"(?<![A-Za-z0-9_$:.])(\d+\.\d+|\d{2,})(?![0-9:])")
REFERENCIA_EXTERNA = re.compile(r"\[([^\]]+)\]")
NOMBRE_FUNCION = re.compile(r"([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9._]*)\s*\(")

# Errores de Excel que sobreviven dentro de una fórmula guardada.
ERRORES_EXCEL = ["#REF!", "#VALUE!", "#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#¡REF!", "#¡VALOR!", "#¡DIV/0!"]


@dataclass
class Hallazgo:
    hoja: str
    celda: str
    tipo: str
    detalle: str
    formula: str = ""


@dataclass
class Informe:
    archivo: str = ""
    hojas: list[dict] = field(default_factory=list)
    hallazgos: list[Hallazgo] = field(default_factory=list)
    funciones: Counter = field(default_factory=Counter)
    nombres_definidos: list[dict] = field(default_factory=list)
    libros_externos: set[str] = field(default_factory=set)
    tiene_macros: bool = False
    modulos_vba: list[str] = field(default_factory=list)
    formulas_unicas: dict[str, int] = field(default_factory=dict)


def detectar_macros(ruta: Path, informe: Informe) -> None:
    """Un .xlsm es un zip: el proyecto VBA se detecta sin ejecutarlo."""
    informe.tiene_macros = ruta.suffix.lower() in {".xlsm", ".xlsb", ".xltm"}
    try:
        with zipfile.ZipFile(ruta) as z:
            nombres = z.namelist()
            if "xl/vbaProject.bin" in nombres:
                informe.tiene_macros = True
                informe.modulos_vba.append("xl/vbaProject.bin")
            informe.modulos_vba.extend(n for n in nombres if "vba" in n.lower())
    except zipfile.BadZipFile:
        pass


def normalizar_formula(f: str) -> str:
    """Reemplaza referencias por marcadores para agrupar fórmulas equivalentes.

    Una fila de 30 años con la misma fórmula arrastrada son 30 celdas y una sola
    regla. Agrupar así reduce cientos de celdas a unas pocas decenas de reglas
    reales, que es lo que hay que reproducir en el motor.
    """
    return re.sub(r"\$?[A-Z]{1,3}\$?\d+", "@", f)


def analizar_hoja(ws, informe: Informe) -> dict:
    conteo = {"celdas": 0, "formulas": 0, "constantes": 0, "vacias": 0}
    formulas_norm: Counter = Counter()

    for fila in ws.iter_rows():
        for celda in fila:
            v = celda.value
            if v is None:
                conteo["vacias"] += 1
                continue
            conteo["celdas"] += 1

            if not (isinstance(v, str) and v.startswith("=")):
                if isinstance(v, (int, float)):
                    conteo["constantes"] += 1
                continue

            conteo["formulas"] += 1
            formulas_norm[normalizar_formula(v)] += 1

            for fn in NOMBRE_FUNCION.findall(v.upper()):
                informe.funciones[fn] += 1

            arriba = v.upper()

            # Fórmulas rotas. Es lo primero que hay que reportar: una fórmula
            # con #REF! no calcula nada, y si alimenta una línea del contraste,
            # esa línea no tiene contra qué compararse. No se corrige — se
            # reporta a Finanzas conforme a las exclusiones del alcance.
            errores = [e for e in ERRORES_EXCEL if e in arriba]
            if errores:
                informe.hallazgos.append(
                    Hallazgo(ws.title, celda.coordinate, "formula-rota",
                             f"Contiene {', '.join(errores)}", v[:160])
                )

            # Redondeos: cambian el resultado y casi nunca están documentados.
            for fn in ("ROUND", "REDONDEAR", "TRUNC", "TRUNCAR", "MROUND", "INT(", "ENTERO("):
                if fn in arriba:
                    informe.hallazgos.append(
                        Hallazgo(ws.title, celda.coordinate, "redondeo",
                                 f"Usa {fn.rstrip('(')}", v[:160])
                    )
                    break

            # Constantes incrustadas: una tasa escrita a mano dentro de una
            # fórmula es la fuente más común de divergencia con el motor,
            # porque no aparece en ninguna hoja de parámetros.
            numeros = [n for n in NUMERO_EN_FORMULA.findall(v) if n not in {"100", "12", "365"}]
            if numeros:
                informe.hallazgos.append(
                    Hallazgo(ws.title, celda.coordinate, "constante-incrustada",
                             f"Valores: {', '.join(sorted(set(numeros))[:6])}", v[:160])
                )

            # Volatilidad e indirección: dificultan reproducir la cadena.
            if "INDIRECT" in arriba or "INDIRECTO" in arriba or "OFFSET" in arriba or "DESREF" in arriba:
                informe.hallazgos.append(
                    Hallazgo(ws.title, celda.coordinate, "referencia-indirecta",
                             "Referencia calculada en tiempo de ejecución", v[:160])
                )

            # Errores silenciados: ocultan que algo no cuadra.
            if "IFERROR" in arriba or "SI.ERROR" in arriba:
                informe.hallazgos.append(
                    Hallazgo(ws.title, celda.coordinate, "error-silenciado",
                             "Un fallo aquí devuelve un valor sin avisar", v[:160])
                )

            for ext in REFERENCIA_EXTERNA.findall(v):
                informe.libros_externos.add(ext)
                informe.hallazgos.append(
                    Hallazgo(ws.title, celda.coordinate, "libro-externo",
                             f"Depende del libro {ext}", v[:160])
                )

    for f, n in formulas_norm.items():
        informe.formulas_unicas[f] = informe.formulas_unicas.get(f, 0) + n

    return {
        "nombre": ws.title,
        "estado": ws.sheet_state,
        "dimensiones": ws.dimensions,
        "filas": ws.max_row,
        "columnas": ws.max_column,
        "reglas_unicas": len(formulas_norm),
        **conteo,
    }


def analizar_nombres(wb, informe: Informe) -> None:
    for nombre, definicion in wb.defined_names.items():
        destino = str(getattr(definicion, "value", ""))
        informe.nombres_definidos.append({
            "nombre": nombre,
            "destino": destino,
            "roto": "#REF" in destino,
        })
        if "#REF" in destino:
            informe.hallazgos.append(
                Hallazgo("(libro)", nombre, "nombre-roto",
                         f"El nombre definido apunta a {destino}")
            )


def escribir_informe(informe: Informe, salida: Path) -> None:
    salida.mkdir(parents=True, exist_ok=True)

    (salida / "diseccion.json").write_text(
        json.dumps(
            {
                "archivo": informe.archivo,
                "tiene_macros": informe.tiene_macros,
                "modulos_vba": informe.modulos_vba,
                "hojas": informe.hojas,
                "funciones": dict(informe.funciones.most_common()),
                "nombres_definidos": informe.nombres_definidos,
                "libros_externos": sorted(informe.libros_externos),
                "total_reglas_unicas": len(informe.formulas_unicas),
                "hallazgos": [h.__dict__ for h in informe.hallazgos],
            },
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    por_tipo: dict[str, list[Hallazgo]] = defaultdict(list)
    for h in informe.hallazgos:
        por_tipo[h.tipo].append(h)

    total_celdas = sum(h["celdas"] for h in informe.hojas)
    total_formulas = sum(h["formulas"] for h in informe.hojas)

    lineas = [
        "# Disección del modelo de referencia",
        "",
        "> **Confidencial.** Contiene fórmulas y valores del modelo económico de",
        "> MINSUR. Se archiva en `00-gestion/03-insumos-minsur/`, nunca en el",
        "> repositorio de código.",
        "",
        f"Archivo: `{informe.archivo}`",
        "",
        "## Resumen",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Hojas | {len(informe.hojas)} |",
        f"| Celdas con contenido | {total_celdas:,} |",
        f"| Celdas con fórmula | {total_formulas:,} |",
        f"| **Reglas únicas a reproducir** | **{len(informe.formulas_unicas):,}** |",
        f"| Nombres definidos | {len(informe.nombres_definidos)} |",
        f"| Macros VBA | {'Sí' if informe.tiene_macros else 'No'} |",
        f"| Libros externos referenciados | {len(informe.libros_externos)} |",
        "",
        "La cifra que importa es **reglas únicas**: una fórmula arrastrada sobre",
        "treinta años son treinta celdas y una sola regla. Ese número es el que",
        "dimensiona el trabajo real del motor.",
        "",
        "## Hojas",
        "",
        "| Hoja | Estado | Filas | Cols | Fórmulas | Constantes | Reglas únicas |",
        "|---|---|---|---|---|---|---|",
    ]
    for h in informe.hojas:
        lineas.append(
            f"| {h['nombre']} | {h['estado']} | {h['filas']} | {h['columnas']} | "
            f"{h['formulas']:,} | {h['constantes']:,} | {h['reglas_unicas']} |"
        )

    lineas += ["", "## Hallazgos que requieren confirmación de Finanzas", ""]
    if not por_tipo:
        lineas.append("Ninguno.")
    else:
        prioridad = ["formula-rota", "libro-externo", "nombre-roto", "referencia-indirecta",
                     "constante-incrustada", "redondeo", "error-silenciado"]
        explicacion = {
            "formula-rota": "No calcula. Si alimenta una línea del contraste, esa línea no tiene contra qué compararse.",
            "libro-externo": "Dependencia de otro archivo. Si no se entrega, el modelo no es autocontenido.",
            "nombre-roto": "Nombre definido que apunta a una referencia inválida.",
            "referencia-indirecta": "La referencia se calcula en ejecución; reproducirla exige entender el patrón.",
            "constante-incrustada": "Valor escrito dentro de la fórmula. No aparece en ninguna hoja de parámetros.",
            "redondeo": "Cambia el resultado y rara vez está documentado. Debe replicarse exactamente.",
            "error-silenciado": "Un fallo devuelve un valor sin avisar; puede ocultar una inconsistencia.",
        }
        for tipo in prioridad:
            items = por_tipo.get(tipo, [])
            if not items:
                continue
            lineas += [f"### {tipo} ({len(items)})", "", f"_{explicacion[tipo]}_", ""]
            lineas += ["| Celda | Detalle | Fórmula |", "|---|---|---|"]
            for h in items[:40]:
                f = h.formula.replace("|", "\\|")
                lineas.append(f"| `{h.hoja}!{h.celda}` | {h.detalle} | `{f}` |")
            if len(items) > 40:
                lineas.append(f"| … | _{len(items) - 40} más en diseccion.json_ | |")
            lineas.append("")

    lineas += ["## Funciones utilizadas", "", "| Función | Usos |", "|---|---|"]
    for fn, n in informe.funciones.most_common(30):
        marca = " Atencion:" if fn in FUNCIONES_DE_INTERES else ""
        lineas.append(f"| {fn}{marca} | {n:,} |")

    if informe.tiene_macros:
        lineas += [
            "", "## Macros",
            "",
            "El libro contiene un proyecto VBA. Las macros pueden alterar valores",
            "fuera de la cadena de fórmulas, así que la disección estática no basta:",
            "hay que preguntar a Finanzas qué hacen y cuándo se ejecutan. Cada",
            "comportamiento que se confirme entra como regla explícita en",
            "`docs/modelo-economico/reglas-no-documentadas.md`.",
            "",
        ]

    lineas += [
        "", "## Siguiente paso",
        "",
        "Llevar los hallazgos de esta lista a la sesión con el interlocutor de",
        "Finanzas (`R-01`). Cada uno se cierra de una de cuatro formas, según el",
        "protocolo de discrepancias del Plan de Trabajo: regla intencional que se",
        "documenta, inconsistencia que se reporta sin corregir, diferencia de",
        "precisión aceptable, o defecto de implementación de INVA.",
        "",
    ]

    (salida / "diseccion.md").write_text("\n".join(lineas), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("modelo", type=Path, help="Libro de Excel del modelo de referencia")
    p.add_argument("--salida", type=Path, default=Path("informe-diseccion"))
    args = p.parse_args()

    if not args.modelo.exists():
        print(f"No existe {args.modelo}")
        return 1

    print(f"Analizando {args.modelo.name} …\n")
    informe = Informe(archivo=args.modelo.name)
    detectar_macros(args.modelo, informe)

    # data_only=False conserva las fórmulas, que es lo que se va a reproducir.
    wb = openpyxl.load_workbook(args.modelo, data_only=False, read_only=False, keep_vba=False)

    for ws in wb.worksheets:
        print(f"  {ws.title} …", end=" ", flush=True)
        resumen = analizar_hoja(ws, informe)
        informe.hojas.append(resumen)
        print(f"{resumen['formulas']:,} fórmulas · {resumen['reglas_unicas']} reglas únicas")

    analizar_nombres(wb, informe)
    wb.close()

    escribir_informe(informe, args.salida)

    print(f"\n{len(informe.hallazgos)} hallazgo(s) para revisar con Finanzas.")
    print(f"Reglas únicas a reproducir en el motor: {len(informe.formulas_unicas):,}")
    if informe.tiene_macros:
        print("El libro tiene macros: la disección estática no las cubre.")
    if informe.libros_externos:
        print(f"Depende de {len(informe.libros_externos)} libro(s) externo(s): no es autocontenido.")
    print(f"\nInforme en {args.salida}/diseccion.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
