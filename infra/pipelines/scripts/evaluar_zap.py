"""Clasifica los hallazgos de OWASP ZAP y produce el resumen para SecOps.

ZAP reporta el riesgo como texto ("High", "Medium", "Low", "Informational").
Este script lo normaliza, cuenta por severidad y escribe un resumen en Markdown
que entra al paquete de evidencia de PT6.10.

No bloquea: en este punto del proceso se recolecta. La compuerta se aplica en
`evaluar_hallazgos.py` durante la integración.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ORDEN = ["High", "Medium", "Low", "Informational"]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reporte", type=Path, required=True)
    p.add_argument("--resumen", type=Path, required=True)
    args = p.parse_args()

    if not args.reporte.exists():
        print(f"No se encontró {args.reporte}. ZAP no produjo reporte.")
        args.resumen.parent.mkdir(parents=True, exist_ok=True)
        args.resumen.write_text(
            "# Resumen DAST\n\nZAP no produjo reporte en esta ejecución.\n", encoding="utf-8"
        )
        return 0

    datos = json.loads(args.reporte.read_text(encoding="utf-8"))

    por_severidad: dict[str, list[dict]] = defaultdict(list)
    for sitio in datos.get("site", []):
        for alerta in sitio.get("alerts", []):
            riesgo = (alerta.get("riskdesc") or "Informational").split(" ")[0]
            por_severidad[riesgo].append(alerta)

    lineas = ["# Resumen DAST · OWASP ZAP", ""]
    lineas.append("| Severidad | Hallazgos |")
    lineas.append("|---|---|")
    for sev in ORDEN:
        lineas.append(f"| {sev} | {len(por_severidad.get(sev, []))} |")
    lineas.append("")

    bloqueantes = por_severidad.get("High", [])
    if bloqueantes:
        lineas.append("## Hallazgos que bloquean el pase")
        lineas.append("")
        for a in bloqueantes:
            instancias = len(a.get("instances", []))
            lineas.append(
                f"- **{a.get('alert')}** · {instancias} instancia(s) · CWE-{a.get('cweid')}"
            )
        lineas.append("")

    diferibles = por_severidad.get("Medium", []) + por_severidad.get("Low", [])
    if diferibles:
        lineas.append("## Hallazgos diferibles a segunda fase (R-29)")
        lineas.append("")
        for a in diferibles:
            lineas.append(f"- {a.get('alert')} · CWE-{a.get('cweid')}")
        lineas.append("")

    args.resumen.parent.mkdir(parents=True, exist_ok=True)
    args.resumen.write_text("\n".join(lineas), encoding="utf-8")

    print("\n".join(lineas[:12]))
    print(f"\nResumen escrito en {args.resumen}")
    if bloqueantes:
        print(f"##vso[task.logissue type=warning]{len(bloqueantes)} hallazgo(s) High en DAST")
    return 0


if __name__ == "__main__":
    sys.exit(main())
