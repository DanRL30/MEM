"""Verificación posterior al despliegue en producción.

Las cinco comprobaciones obligatorias de la ventana de pase, definidas en el
Plan de Trabajo. Se ejecutan **dentro de la misma ventana de mantenimiento**
(domingo 00:00-06:00). Si alguna falla y no se resuelve dentro de la ventana,
se revierte el despliegue de la aplicación y se reprograma a la ventana
siguiente. La infraestructura permanece: es idempotente y está codificada.

    1. Autenticación efectiva con una cuenta de cada uno de los seis perfiles
    2. Caso base de contraste dentro de la tolerancia certificada
    3. Tablero y estados financieros dentro del nivel de servicio
    4. Exportación a Excel y publicación en SharePoint
    5. Registro en el historial con su bitácora de auditoría

La decisión de reversión corresponde al Project Manager de INVA en acuerdo con
el responsable de TI presente en la ventana, y no se escala durante su
ejecución. Este script no decide: informa con evidencia para que decidan.

Sin dependencias externas a propósito: corre en el agente antes de que exista
un entorno Python del proyecto.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

PERFILES = [
    "administrador",
    "finanzas",
    "lider-de-estudio",
    "ingeniero-de-proyecto",
    "consulta-ejecutiva",
    "auditor",
]

# Nivel de servicio comprometido en el alcance.
SLO_TABLERO_S = 5.0
# La cifra de la evaluación estándar la fija MINSUR (R-51). Hasta entonces se
# usa este valor como referencia operativa, no como criterio de aceptación.
SLO_EVALUACION_S = float(os.environ.get("SLO_EVALUACION_S", "30"))


@dataclass
class Resultado:
    numero: int
    nombre: str
    ok: bool
    detalle: str
    segundos: float = 0.0


def _pedir(url: str, token: str | None = None, timeout: int = 60) -> tuple[int, bytes, float]:
    # El destino llega por linea de comandos. urllib acepta file: y esquemas
    # personalizados, de modo que un argumento mal formado convertiria la
    # verificacion del pase en una lectura del disco del agente que ademas
    # reportaria exito. Aqui solo hay un destino valido y lleva el token de un
    # perfil real: la API productiva sobre TLS.
    if not url.startswith("https://"):
        raise ValueError(
            f"La verificacion del pase solo consulta https. Recibido: {url!r}. "
            "Revisa el argumento --url del pipeline."
        )
    req = urllib.request.Request(url, headers={"Accept": "application/json"})  # noqa: S310
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    ctx = ssl.create_default_context()
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:  # noqa: S310
            return r.status, r.read(), time.perf_counter() - inicio
    except urllib.error.HTTPError as e:
        return e.code, e.read(), time.perf_counter() - inicio
    except Exception as e:  # red, DNS, TLS
        return 0, str(e).encode(), time.perf_counter() - inicio


def token_de(perfil: str) -> str | None:
    """Token de prueba del perfil, inyectado desde Key Vault por el pipeline."""
    return os.environ.get(f"TOKEN_{perfil.upper().replace('-', '_')}")


def c1_autenticacion(base: str) -> Resultado:
    faltantes, rechazados = [], []
    for perfil in PERFILES:
        token = token_de(perfil)
        if not token:
            faltantes.append(perfil)
            continue
        codigo, _, _ = _pedir(f"{base}/api/yo", token)
        if codigo != 200:
            rechazados.append(f"{perfil} (HTTP {codigo})")
    if faltantes:
        return Resultado(1, "Autenticación de los seis perfiles", False,
                         f"Sin token de prueba para: {', '.join(faltantes)}. "
                         "Cárgalos en Key Vault antes de la ventana.")
    if rechazados:
        return Resultado(1, "Autenticación de los seis perfiles", False,
                         f"Perfiles rechazados: {', '.join(rechazados)}")
    return Resultado(1, "Autenticación de los seis perfiles", True,
                     "Los seis perfiles autenticaron con cuenta corporativa")


def c2_caso_base(base: str) -> Resultado:
    token = token_de("finanzas")
    caso = os.environ.get("CASO_BASE_ID", "CASO-BASE-SIN-PROYECTO")
    codigo, cuerpo, seg = _pedir(f"{base}/api/casos/{caso}/verificar-fidelidad", token, timeout=300)
    if codigo != 200:
        return Resultado(2, "Caso base dentro de tolerancia", False,
                         f"HTTP {codigo}: {cuerpo[:200].decode(errors='replace')}", seg)
    try:
        d = json.loads(cuerpo)
    except json.JSONDecodeError:
        return Resultado(2, "Caso base dentro de tolerancia", False, "Respuesta no es JSON", seg)
    if not d.get("dentro_de_tolerancia"):
        return Resultado(2, "Caso base dentro de tolerancia", False,
                         f"Fuera de tolerancia: {d.get('desviaciones')}", seg)
    return Resultado(2, "Caso base dentro de tolerancia", True,
                     f"Conciliado en los cuatro niveles (motor {d.get('version_motor')})", seg)


def c3_tablero(base: str) -> Resultado:
    token = token_de("lider-de-estudio")
    codigo, _, seg_tab = _pedir(f"{base}/api/tablero", token)
    if codigo != 200:
        return Resultado(3, "Tablero y estados dentro del SLO", False, f"Tablero HTTP {codigo}", seg_tab)
    if seg_tab > SLO_TABLERO_S:
        return Resultado(3, "Tablero y estados dentro del SLO", False,
                         f"Tablero en {seg_tab:.2f} s, sobre el objetivo de {SLO_TABLERO_S} s", seg_tab)
    codigo, _, seg_eef = _pedir(f"{base}/api/estados-financieros", token)
    if codigo != 200:
        return Resultado(3, "Tablero y estados dentro del SLO", False, f"Estados HTTP {codigo}", seg_eef)
    return Resultado(3, "Tablero y estados dentro del SLO", True,
                     f"Tablero {seg_tab:.2f} s · estados {seg_eef:.2f} s", seg_tab + seg_eef)


def c4_exportacion(base: str) -> Resultado:
    token = token_de("lider-de-estudio")
    caso = os.environ.get("CASO_BASE_ID", "CASO-BASE-SIN-PROYECTO")
    codigo, cuerpo, seg = _pedir(f"{base}/api/casos/{caso}/exportar?destino=sharepoint", token, timeout=180)
    if codigo not in (200, 201, 202):
        return Resultado(4, "Exportación a Excel y SharePoint", False, f"HTTP {codigo}", seg)
    try:
        d = json.loads(cuerpo)
    except json.JSONDecodeError:
        d = {}
    if not d.get("url_sharepoint"):
        # El sitio de SharePoint es R-44. Si TI aún no lo habilitó, la
        # exportación queda limitada a descarga local y esto no debe leerse
        # como un defecto de la plataforma.
        return Resultado(4, "Exportación a Excel y SharePoint", False,
                         "Exportó pero no publicó en SharePoint. Verificar R-44.", seg)
    return Resultado(4, "Exportación a Excel y SharePoint", True, d["url_sharepoint"], seg)


def c5_historial(base: str) -> Resultado:
    token = token_de("auditor")
    codigo, cuerpo, seg = _pedir(f"{base}/api/historial?limite=1", token)
    if codigo != 200:
        return Resultado(5, "Historial y bitácora de auditoría", False, f"HTTP {codigo}", seg)
    try:
        d = json.loads(cuerpo)
    except json.JSONDecodeError:
        return Resultado(5, "Historial y bitácora de auditoría", False, "Respuesta no es JSON", seg)
    corridas = d.get("corridas") or []
    if not corridas:
        return Resultado(5, "Historial y bitácora de auditoría", False, "El historial está vacío", seg)
    ultima = corridas[0]
    faltan = [c for c in ("id_corrida", "usuario", "marca_tiempo", "version_motor") if not ultima.get(c)]
    if faltan:
        return Resultado(5, "Historial y bitácora de auditoría", False,
                         f"Bitácora incompleta, faltan: {', '.join(faltan)}", seg)
    return Resultado(5, "Historial y bitácora de auditoría", True,
                     f"Corrida {ultima['id_corrida']} registrada con trazabilidad completa", seg)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True, help="URL base del entorno productivo")
    p.add_argument("--salida", type=Path, help="Ruta del informe JSON")
    args = p.parse_args()
    base = args.url.rstrip("/")

    print(f"Verificación posterior al despliegue · {base}\n")
    resultados = [
        c1_autenticacion(base),
        c2_caso_base(base),
        c3_tablero(base),
        c4_exportacion(base),
        c5_historial(base),
    ]

    for r in resultados:
        marca = "OK   " if r.ok else "FALLA"
        print(f"  {marca} {r.numero}. {r.nombre}")
        print(f"        {r.detalle}" + (f"  ({r.segundos:.2f} s)" if r.segundos else ""))

    fallidas = [r for r in resultados if not r.ok]

    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(
            json.dumps({"url": base, "comprobaciones": [asdict(r) for r in resultados],
                        "aprobado": not fallidas}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    if fallidas:
        print(f"\n{len(fallidas)} de 5 comprobaciones fallaron.")
        print("Criterio de la ventana: si no se resuelven dentro de las seis horas,")
        print("se revierte el despliegue de la aplicación y se reprograma al domingo siguiente.")
        return 1

    print("\nLas cinco comprobaciones pasaron. Procede el acta de pase.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
