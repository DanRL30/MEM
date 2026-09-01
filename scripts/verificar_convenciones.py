"""Verifica las convenciones de escritura del repositorio.

`docs/convenciones.md` prohibe emojis, caracteres de dibujo de caja y atribucion
a herramientas de asistencia en todo el arbol que se entrega a MINSUR. Hasta
ahora la regla se sostenia por disciplina; esto la hace comprobable.

Se ejecuta en cada integracion y en local:

    python scripts/verificar_convenciones.py

Devuelve 1 si encuentra una infraccion, con la ruta y la linea exactas.

Dos decisiones de implementacion que no son cosmeticas:

- Los rangos prohibidos se declaran por punto de codigo y la expresion se arma
  en tiempo de ejecucion. Asi este archivo es ASCII puro y pasa su propia
  verificacion; con los caracteres literales se marcaria a si mismo.
- Los hallazgos tambien se reportan por punto de codigo. La consola de Windows
  usa cp1252 y aborta al imprimir un caracter que no puede representar, que es
  justamente el caso de todo lo que este script busca.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

EXTENSIONES = {
    ".md",
    ".py",
    ".yml",
    ".yaml",
    ".bicep",
    ".bicepparam",
    ".ts",
    ".tsx",
    ".json",
    ".css",
    ".html",
    ".sh",
    ".ps1",
}

DIRECTORIOS_EXCLUIDOS = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}

RANGOS_DECORATIVOS = (
    (0x2190, 0x21FF),  # flechas
    (0x2300, 0x23FF),  # simbolos tecnicos
    (0x2500, 0x257F),  # dibujo de caja
    (0x2580, 0x259F),  # bloques
    (0x25A0, 0x25FF),  # formas geometricas
    (0x2600, 0x27BF),  # simbolos varios y dingbats
    (0x2B00, 0x2BFF),  # flechas suplementarias
    (0xFE0F, 0xFE0F),  # selector de variacion emoji
    (0x1F000, 0x1FAFF),  # emoji
)

DECORATIVOS = re.compile(
    "[" + "".join(f"{chr(inicio)}-{chr(fin)}" for inicio, fin in RANGOS_DECORATIVOS) + "]"
)

# Los triangulos de delta son parte del vocabulario de la interfaz: marcan si un
# indicador sube o baja, y el design system de MINSUR los usa asi.
DECORATIVOS_PERMITIDOS = {chr(0x25B2), chr(0x25BC)}

ATRIBUCION = re.compile(
    r"co-authored-by:\s*(claude|anthropic)|generated with \[?claude|"
    r"\bclaude\s+(code|opus|sonnet|haiku)\b",
    re.IGNORECASE,
)

# CLAUDE.md conserva su encabezado de origen: ver docs/adr/0008. La excepcion
# es deliberada y se acota a esta regla, de modo que el archivo sigue
# auditandose por caracteres decorativos y ningun otro queda exento de nada.
# El conjunto guarda rutas relativas a RAIZ, no nombres: comparar por nombre
# eximiria a cualquier CLAUDE.md de cualquier subdirectorio, que es mas de lo
# que decide el ADR.
# Si el encabezado se retira, esta linea sobra y se elimina con el.
SIN_REGLA_DE_ATRIBUCION = {"CLAUDE.md"}


def archivos_candidatos():
    for ruta in RAIZ.rglob("*"):
        if not ruta.is_file() or ruta.suffix not in EXTENSIONES:
            continue
        if DIRECTORIOS_EXCLUIDOS & set(ruta.relative_to(RAIZ).parts):
            continue
        yield ruta


def revisar(ruta: Path) -> list[str]:
    relativa = ruta.relative_to(RAIZ).as_posix()
    try:
        contenido = ruta.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as error:
        return [f"{relativa}: no se pudo leer ({error})"]

    revisar_atribucion = relativa not in SIN_REGLA_DE_ATRIBUCION

    infracciones = []
    for numero, linea in enumerate(contenido.splitlines(), 1):
        for caracter in DECORATIVOS.findall(linea):
            if caracter in DECORATIVOS_PERMITIDOS:
                continue
            nombre = unicodedata.name(caracter, "sin nombre")
            infracciones.append(
                f"{relativa}:{numero}: caracter decorativo U+{ord(caracter):04X} "
                f"({nombre}). Usa ASCII; para diagramas, ASCII."
            )

        if revisar_atribucion and ATRIBUCION.search(linea):
            infracciones.append(
                f"{relativa}:{numero}: atribucion a una herramienta de asistencia. "
                "El codigo se entrega bajo titularidad de MINSUR y no la menciona."
            )

    return infracciones


def main() -> int:
    infracciones = [fallo for ruta in archivos_candidatos() for fallo in revisar(ruta)]

    for fallo in infracciones:
        print(fallo)

    if infracciones:
        print(f"\n{len(infracciones)} infracciones de docs/convenciones.md")
        return 1

    print("Convenciones de escritura: sin infracciones")
    return 0


if __name__ == "__main__":
    sys.exit(main())
