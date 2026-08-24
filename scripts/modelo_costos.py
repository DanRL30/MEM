"""Modelo de costos de consumo de Azure para la plataforma.

El consumo corre por cuenta de MINSUR conforme al alcance, así que la
elección de SKU es una decisión con impacto directo en el cliente y conviene
sustentarla con aritmética y no con intuición.

Precios de lista de East US 2, sin descuentos de acuerdo empresarial. Se
modela el consumo a partir del dimensionamiento del alcance: 17 usuarios
nominales, 7 concurrentes, ~100 evaluaciones al año, archivos de 1 a 10 MB,
retención de 5 años.

Uso:
    python scripts/modelo_costos.py
    python scripts/modelo_costos.py --detalle
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

# ── Dimensionamiento declarado en el alcance ──────────────────────────────
USUARIOS_NOMINALES = 17
USUARIOS_CONCURRENTES = 7
EVALUACIONES_ANIO = 100
MB_POR_EVALUACION = 10
ANIOS_RETENCION = 5
HORAS_LABORALES_MES = 22 * 9  # 198 h · lunes a viernes, 9 h
HORAS_MES = 730

# ── Precios unitarios · East US 2 · lista ─────────────────────────────────
P = {
    "apim_consumption_millon": 3.50,      # primer millón de llamadas sin costo
    "apim_developer_mes": 48.36,
    "apim_basicv2_mes": 147.00,
    "apim_standardv2_mes": 701.00,
    "ep1_mes": 150.00,                    # Elastic Premium EP1
    "flex_alwaysready_gb_s": 0.0000173,   # instancia siempre lista
    "flex_ejecucion_gb_s": 0.0000173,
    "sql_serverless_vcore_s": 0.000145,
    "sql_gp_gen5_2_hora": 0.5044,         # aprovisionada, 2 vCore
    "sql_almacenamiento_gb": 0.115,
    "frontdoor_premium_mes": 330.00,
    "frontdoor_standard_mes": 35.00,
    "swa_standard_mes": 9.00,
    "storage_gzrs_gb": 0.0288,
    "storage_transacciones_10k": 0.0065,
    "private_endpoint_hora": 0.01,
    "log_analytics_gb": 2.76,
    "key_vault_10k_ops": 0.03,
}


@dataclass
class Linea:
    concepto: str
    mensual: float
    nota: str = ""


@dataclass
class Entorno:
    nombre: str
    lineas: list[Linea] = field(default_factory=list)

    def agregar(self, concepto: str, mensual: float, nota: str = "") -> None:
        self.lineas.append(Linea(concepto, mensual, nota))

    @property
    def total(self) -> float:
        return sum(l.mensual for l in self.lineas)


# ── Componentes ───────────────────────────────────────────────────────────

def costo_almacenamiento() -> float:
    """El volumen del alcance es minúsculo; domina el costo de transacción."""
    gb = EVALUACIONES_ANIO * MB_POR_EVALUACION * ANIOS_RETENCION / 1024
    datos = gb * P["storage_gzrs_gb"]
    # Estimación gruesa de operaciones: lecturas del historial y del tablero.
    transacciones = 500_000 / 10_000 * P["storage_transacciones_10k"]
    return datos + transacciones


def costo_sql(modo: str) -> float:
    if modo == "aprovisionada_2vcore":
        return P["sql_gp_gen5_2_hora"] * HORAS_MES + 32 * P["sql_almacenamiento_gb"]
    if modo == "serverless_sin_pausa":
        # 0.5 vCore mínimo continuo, picos a 1.
        return 0.5 * HORAS_MES * 3600 * P["sql_serverless_vcore_s"] + 32 * P["sql_almacenamiento_gb"]
    if modo == "serverless_con_pausa":
        # Activa solo en horario laboral, promedio 0.75 vCore.
        return 0.75 * HORAS_LABORALES_MES * 3600 * P["sql_serverless_vcore_s"] + 32 * P["sql_almacenamiento_gb"]
    if modo == "serverless_dev":
        # Uso esporádico del equipo: unas 40 h al mes.
        return 0.5 * 40 * 3600 * P["sql_serverless_vcore_s"] + 8 * P["sql_almacenamiento_gb"]
    raise ValueError(modo)


def costo_apim(sku: str) -> float:
    if sku == "consumption":
        # 17 usuarios generando, con holgura, 200 000 llamadas al mes.
        # El primer millón no tiene costo.
        return 0.0
    return {
        "developer": P["apim_developer_mes"],
        "basicv2": P["apim_basicv2_mes"],
        "standardv2": P["apim_standardv2_mes"],
    }[sku]


def costo_computo(modo: str) -> float:
    if modo == "ep1":
        return P["ep1_mes"]
    if modo == "flex_siempre_listo":
        # Una instancia de 2 GB permanentemente lista: sin arranque en frío.
        return 2 * HORAS_MES * 3600 * P["flex_alwaysready_gb_s"]
    if modo == "flex_bajo_demanda":
        # Solo ejecución. ~100 evaluaciones/año más navegación del tablero.
        segundos_gb = 40_000
        return segundos_gb * P["flex_ejecucion_gb_s"]
    raise ValueError(modo)


def costo_pe(cantidad: int) -> float:
    return cantidad * P["private_endpoint_hora"] * HORAS_MES


def costo_observabilidad(gb_mes: float) -> float:
    return gb_mes * P["log_analytics_gb"]


# ── Escenarios ────────────────────────────────────────────────────────────

def escenario_a() -> list[Entorno]:
    """Línea base. Todas las garantías, sin optimizar."""
    prod = Entorno("Producción")
    prod.agregar("API Management Standard v2", costo_apim("standardv2"), "SLA 99,95 % · integración a red virtual")
    prod.agregar("Cómputo Elastic Premium EP1", costo_computo("ep1"), "Ranuras de despliegue · sin arranque en frío")
    prod.agregar("Azure SQL aprovisionada 2 vCore", costo_sql("aprovisionada_2vcore"), "Costo fijo y predecible")
    prod.agregar("Front Door Premium", P["frontdoor_premium_mes"], "WAF gestionado DRS · Private Link al origen")
    prod.agregar("Puntos de conexión privados (4)", costo_pe(4))
    prod.agregar("Observabilidad", costo_observabilidad(7))
    prod.agregar("Almacenamiento", costo_almacenamiento())
    prod.agregar("Static Web Apps Standard", P["swa_standard_mes"])
    prod.agregar("Key Vault", 1.0)

    qa = Entorno("Calidad")
    qa.agregar("API Management Developer", costo_apim("developer"), "Sin SLA · aceptable fuera de producción")
    qa.agregar("Cómputo Elastic Premium EP1", costo_computo("ep1"))
    qa.agregar("Azure SQL serverless con pausa", costo_sql("serverless_con_pausa"))
    qa.agregar("Front Door Premium", P["frontdoor_premium_mes"], "Igual a producción para el ethical hacking")
    qa.agregar("Puntos de conexión privados (4)", costo_pe(4))
    qa.agregar("Observabilidad", costo_observabilidad(4))
    qa.agregar("Almacenamiento", costo_almacenamiento() * 0.6)
    qa.agregar("Static Web Apps Standard", P["swa_standard_mes"])
    qa.agregar("Key Vault", 1.0)

    dev = Entorno("Desarrollo")
    dev.agregar("API Management Developer", costo_apim("developer"))
    dev.agregar("Cómputo Elastic Premium EP1", costo_computo("ep1"))
    dev.agregar("Azure SQL serverless esporádica", costo_sql("serverless_dev"))
    dev.agregar("Sin borde", 0.0, "Ya optimizado: no acceden usuarios finales")
    dev.agregar("Puntos de conexión privados (4)", costo_pe(4))
    dev.agregar("Observabilidad", costo_observabilidad(2))
    dev.agregar("Almacenamiento", costo_almacenamiento() * 0.3)
    dev.agregar("Static Web Apps Free", 0.0, "Ya optimizado")
    dev.agregar("Key Vault", 1.0)
    return [prod, qa, dev]


def escenario_b() -> list[Entorno]:
    """Equilibrado. Cede lo que no compromete el alcance contractual."""
    prod = Entorno("Producción")
    prod.agregar("API Management Basic v2", costo_apim("basicv2"), "Conserva SLA 99,95 % · sin red virtual")
    prod.agregar("Cómputo Elastic Premium EP1", costo_computo("ep1"), "Se conservan las ranuras")
    prod.agregar("Azure SQL serverless sin pausa", costo_sql("serverless_sin_pausa"), "Sin latencia de reanudación")
    prod.agregar("Front Door Premium", P["frontdoor_premium_mes"], "Se conserva el WAF gestionado")
    prod.agregar("Puntos de conexión privados (4)", costo_pe(4))
    prod.agregar("Observabilidad", costo_observabilidad(5))
    prod.agregar("Almacenamiento", costo_almacenamiento())
    prod.agregar("Static Web Apps Standard", P["swa_standard_mes"])
    prod.agregar("Key Vault", 1.0)

    qa = Entorno("Calidad")
    qa.agregar("API Management Consumption", costo_apim("consumption"), "Pago por llamada · primer millón sin costo")
    qa.agregar("Cómputo Flex bajo demanda", costo_computo("flex_bajo_demanda"))
    qa.agregar("Azure SQL serverless con pausa", costo_sql("serverless_con_pausa"))
    qa.agregar("Front Door Premium", P["frontdoor_premium_mes"], "Igual a producción para el ethical hacking")
    qa.agregar("Puntos de conexión privados (4)", costo_pe(4))
    qa.agregar("Observabilidad", costo_observabilidad(3))
    qa.agregar("Almacenamiento", costo_almacenamiento() * 0.6)
    qa.agregar("Static Web Apps Standard", P["swa_standard_mes"])
    qa.agregar("Key Vault", 1.0)

    dev = Entorno("Desarrollo")
    dev.agregar("API Management Consumption", costo_apim("consumption"))
    dev.agregar("Cómputo Flex bajo demanda", costo_computo("flex_bajo_demanda"))
    dev.agregar("Azure SQL serverless esporádica", costo_sql("serverless_dev"))
    dev.agregar("Sin borde", 0.0)
    dev.agregar("Puntos de conexión de servicio", 0.0, "Sin costo · menor aislamiento que los privados")
    dev.agregar("Observabilidad", costo_observabilidad(1.5))
    dev.agregar("Almacenamiento", costo_almacenamiento() * 0.3)
    dev.agregar("Static Web Apps Free", 0.0)
    dev.agregar("Key Vault", 1.0)
    return [prod, qa, dev]


def escenario_c() -> list[Entorno]:
    """Mínimo. Cuestiona los supuestos de raíz, conservando el alcance."""
    prod = Entorno("Producción")
    prod.agregar("API Management Consumption", costo_apim("consumption"), "SLA 99,95 % · escala a cero")
    prod.agregar("Cómputo Flex, 1 instancia siempre lista", costo_computo("flex_siempre_listo"), "Evita el arranque en frío")
    prod.agregar("Azure SQL serverless con pausa y calentamiento", costo_sql("serverless_con_pausa"))
    prod.agregar("Front Door Standard", P["frontdoor_standard_mes"], "WAF con reglas propias · sin DRS gestionado")
    prod.agregar("Puntos de conexión privados (4)", costo_pe(4))
    prod.agregar("Observabilidad con tope diario", costo_observabilidad(4))
    prod.agregar("Almacenamiento", costo_almacenamiento())
    prod.agregar("Static Web Apps Standard", P["swa_standard_mes"])
    prod.agregar("Key Vault", 1.0)

    qa = Entorno("Calidad")
    qa.agregar("API Management Consumption", costo_apim("consumption"))
    qa.agregar("Cómputo Flex bajo demanda", costo_computo("flex_bajo_demanda"))
    qa.agregar("Azure SQL serverless con pausa", costo_sql("serverless_con_pausa"))
    qa.agregar("Front Door Standard", P["frontdoor_standard_mes"], "Igual a producción")
    qa.agregar("Puntos de conexión privados (4)", costo_pe(4))
    qa.agregar("Observabilidad", costo_observabilidad(2))
    qa.agregar("Almacenamiento", costo_almacenamiento() * 0.6)
    qa.agregar("Static Web Apps Standard", P["swa_standard_mes"])
    qa.agregar("Key Vault", 1.0)

    dev = Entorno("Desarrollo · efímero")
    dev.agregar("Recreado por IaC cuando se necesita", 0.0, "~12 días al mes de vigencia media")
    dev.agregar("API Management Consumption", costo_apim("consumption"))
    dev.agregar("Cómputo Flex bajo demanda", costo_computo("flex_bajo_demanda") * 0.4)
    dev.agregar("Azure SQL serverless esporádica", costo_sql("serverless_dev") * 0.4)
    dev.agregar("Puntos de conexión de servicio", 0.0)
    dev.agregar("Observabilidad", costo_observabilidad(0.6))
    dev.agregar("Almacenamiento", costo_almacenamiento() * 0.3)
    dev.agregar("Static Web Apps Free", 0.0)
    dev.agregar("Key Vault", 1.0)
    return [prod, qa, dev]


ESCENARIOS = {
    "A · Línea base": escenario_a,
    "B · Equilibrado": escenario_b,
    "C · Mínimo": escenario_c,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--detalle", action="store_true", help="Desglose por componente")
    args = ap.parse_args()

    gb = EVALUACIONES_ANIO * MB_POR_EVALUACION * ANIOS_RETENCION / 1024
    print("Dimensionamiento del alcance")
    print(f"  {USUARIOS_NOMINALES} usuarios · {USUARIOS_CONCURRENTES} concurrentes · "
          f"{EVALUACIONES_ANIO} evaluaciones/año")
    print(f"  Volumen a {ANIOS_RETENCION} años: {gb:.1f} GB\n")

    totales = {}
    for nombre, fn in ESCENARIOS.items():
        entornos = fn()
        total = sum(e.total for e in entornos)
        totales[nombre] = (total, entornos)

        print("=" * 74)
        print(f"{nombre}")
        print("=" * 74)
        for e in entornos:
            if args.detalle:
                print(f"\n  {e.nombre}")
                for l in e.lineas:
                    if l.mensual > 0 or l.nota:
                        nota = f"   {l.nota}" if l.nota else ""
                        print(f"    {l.concepto:<46} {l.mensual:>8,.0f}{nota}")
                print(f"    {'':<46} {'—' * 8}")
                print(f"    {'Subtotal':<46} {e.total:>8,.0f}")
            else:
                print(f"  {e.nombre:<24} US$ {e.total:>8,.0f} / mes")
        print(f"\n  {'TOTAL':<24} US$ {total:>8,.0f} / mes   ·   US$ {total*12:>9,.0f} / año\n")

    base = totales["A · Línea base"][0]
    print("=" * 74)
    print("Comparativa")
    print("=" * 74)
    print(f"{'Escenario':<20}{'US$/mes':>10}{'US$/año':>12}{'Ahorro/año':>13}{'Reducción':>11}")
    for nombre, (total, _) in totales.items():
        ahorro = base - total
        pct = ahorro / base * 100
        print(f"{nombre:<20}{total:>10,.0f}{total*12:>12,.0f}{ahorro*12:>13,.0f}{pct:>10.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
