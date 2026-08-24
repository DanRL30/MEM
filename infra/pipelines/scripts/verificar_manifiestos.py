"""Verifica que los casos de contraste descargados coinciden con su manifiesto.

Los tres casos certificados son la referencia contra la que se declara la
fidelidad del motor. Si uno se altera —por una recarga, una corrección de
Finanzas o un error de copia— el contraste deja de significar lo que dice
significar y la certificación pierde sustento.

Este script compara el SHA-256 de cada archivo descargado contra el registrado
en `fixtures/certificados/*/manifiesto.json`. Los manifiestos viven en el
repositorio; los datos, nunca.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256(ruta: Path, bloque: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        while trozo := f.read(bloque):
            h.update(trozo)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifiestos", type=Path, required=True)
    p.add_argument("--datos", type=Path, required=True)
    args = p.parse_args()

    manifiestos = sorted(args.manifiestos.rglob("manifiesto.json"))
    if not manifiestos:
        print(f"No hay manifiestos en {args.manifiestos}.")
        print("Sin manifiestos no hay contraste verificable: se detiene.")
        return 1

    problemas: list[str] = []
    verificados = 0

    for m in manifiestos:
        d = json.loads(m.read_text(encoding="utf-8"))
        caso = d.get("caso_id", m.parent.name)

        for clave, nombre in (("sha256_inputs", "inputs"), ("sha256_resultados", "resultados")):
            esperado = (d.get(clave) or "").strip().lower()
            if not esperado:
                problemas.append(f"{caso}: {clave} vacío en el manifiesto")
                continue

            candidatos = sorted((args.datos / caso).glob(f"{nombre}*"))
            if not candidatos:
                problemas.append(f"{caso}: no se descargó ningún archivo de {nombre}")
                continue

            real = sha256(candidatos[0])
            if real != esperado:
                problemas.append(
                    f"{caso}/{nombre}: hash no coincide\n"
                    f"      esperado {esperado}\n"
                    f"      obtenido {real}"
                )
            else:
                verificados += 1
                print(f"  OK  {caso}/{nombre}")

    if problemas:
        print(f"\n{len(problemas)} problema(s) de integridad:")
        for x in problemas:
            print(f"  - {x}")
        print("\nEl contraste no se ejecuta sobre datos cuya integridad no se pudo confirmar.")
        print("Si Finanzas actualizó un caso, hay que recertificarlo y actualizar el manifiesto.")
        return 1

    print(f"\n{verificados} archivo(s) verificados contra {len(manifiestos)} manifiesto(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
