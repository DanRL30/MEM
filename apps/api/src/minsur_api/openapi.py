"""Generador del esquema OpenAPI.

`pnpm contracts` invoca este módulo para producir el esquema del que salen
los tipos TypeScript del frontend, y la canalización de despliegue importa
ese mismo archivo a API Management.

Que ambos consuman la misma fuente es lo que impide que la puerta de enlace
exponga un contrato distinto del que sirve el backend.

    python -m minsur_api.openapi --salida packages/contracts/openapi.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


def esquema() -> dict[str, Any]:
    from .main import crear_app

    documento = crear_app().openapi()

    # Servidor relativo: la interfaz llama a través de la puerta de enlace y
    # el origen depende del entorno. Fijar uno absoluto haría que el cliente
    # generado apuntara siempre al mismo.
    documento["servers"] = [{"url": "/", "description": "A través de API Management"}]
    return documento


def main() -> int:
    p = argparse.ArgumentParser(description="Genera el esquema OpenAPI.")
    p.add_argument(
        "--salida",
        type=pathlib.Path,
        help=(
            "Archivo destino. Preferible a redirigir la salida estándar: la "
            "redirección usa la codificación de la consola, que en Windows no "
            "es UTF-8 y corrompe los acentos del esquema."
        ),
    )
    args = p.parse_args()

    documento = json.dumps(esquema(), indent=2, ensure_ascii=False, sort_keys=True)

    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(documento + "\n", encoding="utf-8")
        print(f"Esquema escrito en {args.salida}", file=sys.stderr)
    else:
        # Se escriben los bytes ya codificados en lugar de fijar la
        # codificacion del flujo: reconfigure solo existe en TextIOWrapper, y
        # la salida estandar no siempre lo es. La consola de Windows no usa
        # UTF-8 y corromperia los acentos del esquema.
        sys.stdout.buffer.write((documento + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
