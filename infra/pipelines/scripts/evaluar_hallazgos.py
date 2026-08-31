"""Compuerta de seguridad de las canalizaciones.

Consolida los reportes de Bandit, pip-audit y pnpm audit, y decide si la
integración continúa.

El criterio es el escalonado que se acordó llevar a MINSUR como `R-29`:
los hallazgos **críticos y altos bloquean**; los medios y bajos se registran,
se publican como evidencia y se difieren a una segunda fase. Sin ese
escalonamiento, cualquier vulnerabilidad menor en una librería de terceros
detiene el pase, y el propio cliente advirtió en el KOM que con Python y
librerías de terceros eso es frecuente.

Un reporte ausente, vacío o ilegible **no es ausencia de hallazgos**: es una
corrida rota. La compuerta lo trata como falta de evidencia y se detiene, con
`--fallar-en-altos` en cualquier valor. Ese interruptor gradúa la severidad que
bloquea; no autoriza a pronunciarse sobre un análisis que no llegó a correr.

Salida: código 0 si la integración puede continuar, 1 si debe detenerse.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

BLOQUEANTES = {"CRITICAL", "HIGH"}

# Cada reporte que la compuerta espera encontrar, con el paso que lo produce.
# El nombre del paso viaja en el diagnóstico porque es lo que se busca en el
# registro de la canalización cuando el archivo no aparece.
REPORTES_ESPERADOS = {
    "bandit.json": "SAST · Bandit",
    "pip-audit.json": "SCA · pip-audit (Python)",
    "pnpm-audit.json": "SCA · pnpm audit (Node)",
}


@dataclass
class Evidencia:
    """Reportes que no se pudieron leer, con el motivo."""

    faltas: list[str] = field(default_factory=list)

    def registrar(self, ruta: Path, motivo: str) -> None:
        paso = REPORTES_ESPERADOS.get(ruta.name, "paso desconocido")
        self.faltas.append(f"{ruta.name}: {motivo} (lo produce: {paso})")


@dataclass
class Resumen:
    conteo: dict[str, int] = field(default_factory=dict)
    bloqueantes: list[str] = field(default_factory=list)

    def registrar(self, severidad: str, descripcion: str) -> None:
        sev = (severidad or "UNKNOWN").upper()
        self.conteo[sev] = self.conteo.get(sev, 0) + 1
        if sev in BLOQUEANTES:
            self.bloqueantes.append(f"[{sev}] {descripcion}")


def _cargar(ruta: Path, evidencia: Evidencia) -> dict | list | None:
    if not ruta.exists():
        evidencia.registrar(ruta, "no existe")
        return None
    if ruta.stat().st_size == 0:
        evidencia.registrar(ruta, "está vacío")
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        evidencia.registrar(ruta, f"no es JSON válido ({error})")
        return None
    except OSError as error:
        evidencia.registrar(ruta, f"no se pudo leer ({error})")
        return None


def leer_bandit(directorio: Path, resumen: Resumen, evidencia: Evidencia) -> None:
    datos = _cargar(directorio / "bandit.json", evidencia)
    if not isinstance(datos, dict):
        return
    for r in datos.get("results", []):
        resumen.registrar(
            r.get("issue_severity", ""),
            f"Bandit {r.get('test_id')} · {r.get('filename')}:{r.get('line_number')} · {r.get('issue_text')}",
        )


def leer_pip_audit(directorio: Path, resumen: Resumen, evidencia: Evidencia) -> None:
    datos = _cargar(directorio / "pip-audit.json", evidencia)
    dependencias = datos.get("dependencies", []) if isinstance(datos, dict) else datos or []
    for dep in dependencias:
        if not isinstance(dep, dict):
            continue
        for vuln in dep.get("vulns", []):
            # pip-audit no siempre expone severidad; sin ella no se puede
            # afirmar que sea bloqueante, así que se clasifica como UNKNOWN
            # y queda visible en la evidencia para revisión manual.
            resumen.registrar(
                str(vuln.get("severity") or "UNKNOWN"),
                f"pip-audit {vuln.get('id')} · {dep.get('name')} {dep.get('version')}",
            )


def leer_pnpm_audit(directorio: Path, resumen: Resumen, evidencia: Evidencia) -> None:
    datos = _cargar(directorio / "pnpm-audit.json", evidencia)
    if not isinstance(datos, dict):
        return
    for clave, aviso in (datos.get("advisories") or {}).items():
        resumen.registrar(
            str(aviso.get("severity", "")),
            f"pnpm {clave} · {aviso.get('module_name')} · {aviso.get('title')}",
        )
    # Formato agregado de pnpm 8+
    for severidad, cantidad in (datos.get("metadata", {}).get("vulnerabilities") or {}).items():
        if cantidad and severidad.upper() in BLOQUEANTES and not datos.get("advisories"):
            resumen.registrar(severidad, f"pnpm audit · {cantidad} hallazgo(s) {severidad}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directorio", type=Path, required=True)
    p.add_argument("--fallar-en-altos", default="true")
    args = p.parse_args()

    resumen = Resumen()
    evidencia = Evidencia()
    leer_bandit(args.directorio, resumen, evidencia)
    leer_pip_audit(args.directorio, resumen, evidencia)
    leer_pnpm_audit(args.directorio, resumen, evidencia)

    print("Hallazgos por severidad:")
    if not resumen.conteo:
        print("  ninguno")
    for sev in sorted(resumen.conteo):
        print(f"  {sev:<10} {resumen.conteo[sev]}")

    if evidencia.faltas:
        print(f"\nEvidencia incompleta, {len(evidencia.faltas)} reporte(s):")
        for falta in evidencia.faltas:
            print(f"  - {falta}")
        print(
            "\nLa compuerta no se pronuncia sobre un análisis que no dejó reporte: "
            "un archivo ausente no es ausencia de hallazgos. Revisa que el paso que "
            "lo produce haya corrido y que el entorno tenga el grupo `security` "
            "sincronizado (uv sync --all-packages --group security)."
        )
        print("##vso[task.logissue type=error]Evidencia de seguridad incompleta")
        return 1

    if not resumen.bloqueantes:
        print("\nSin hallazgos críticos ni altos. La integración continúa.")
        return 0

    print(f"\n{len(resumen.bloqueantes)} hallazgo(s) crítico(s) o alto(s):")
    for h in resumen.bloqueantes:
        print(f"  - {h}")

    bloquear = str(args.fallar_en_altos).strip().lower() in {"true", "1", "yes", "si", "sí"}
    if bloquear:
        print("\nCompuerta cerrada: corrige los críticos y altos antes de continuar.")
        return 1

    # Modo informativo: se usa en las ramas de trabajo para no detener al
    # equipo, pero nunca en la rama que alimenta el pase a producción.
    print("\nCompuerta en modo informativo. No bloquea, pero queda en la evidencia.")
    print("##vso[task.logissue type=warning]Hallazgos críticos o altos sin remediar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
