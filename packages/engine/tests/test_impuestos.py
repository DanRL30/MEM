"""Pruebas del bloque tributario y de la circularidad.

La prueba que sostiene el [ADR 0009](../../../docs/adr/0009-resolucion-de-la-circularidad-tributaria.md)
es `test_coincide_con_el_punto_fijo`: la solución cerrada y una aproximación
independiente tienen que dar el mismo número. Si divergen, la derivación del
sistema está mal, y eso es un fallo del motor aunque el resultado parezca
razonable.

Las escalas de estas pruebas son sintéticas. Las reales son dato maestro que
mantiene MINSUR (`R-32`) y no viven en el código.
"""

from __future__ import annotations

import pytest

from minsur_engine.impuestos import (
    EntradasTributarias,
    ErrorTributos,
    EscalaProgresiva,
    Tramo,
    resolver,
    resolver_por_punto_fijo,
)

ESCALA_REGALIA = EscalaProgresiva(
    tramos=(
        Tramo(0.0, 0.10, 0.01),
        Tramo(0.10, 0.20, 0.02),
        Tramo(0.20, 0.40, 0.04),
        Tramo(0.40, 10.0, 0.08),
    )
)
ESCALA_IEM = EscalaProgresiva(
    tramos=(
        Tramo(0.0, 0.10, 0.02),
        Tramo(0.10, 0.30, 0.03),
        Tramo(0.30, 10.0, 0.05),
    )
)


def entradas(**cambios: float) -> EntradasTributarias:
    base: dict[str, float] = {
        "ventas_totales": 1_000_000.0,
        "base_operativa": 400_000.0,
        "base_imponible": 380_000.0,
        "saldo_perdidas": 0.0,
        "tasa_regalia_ventas": 0.01,
        "tasa_fondo_jubilacion": 0.005,
        "tasa_participacion": 0.08,
        "tasa_impuesto_renta": 0.295,
    }
    base.update(cambios)
    return EntradasTributarias(
        ventas_totales=base["ventas_totales"],
        base_operativa=base["base_operativa"],
        base_imponible=base["base_imponible"],
        saldo_perdidas=base["saldo_perdidas"],
        escala_regalia=ESCALA_REGALIA,
        escala_iem=ESCALA_IEM,
        tasa_regalia_ventas=base["tasa_regalia_ventas"],
        tasa_fondo_jubilacion=base["tasa_fondo_jubilacion"],
        tasa_participacion=base["tasa_participacion"],
        tasa_impuesto_renta=base["tasa_impuesto_renta"],
    )


class TestEscalaProgresiva:
    def test_acumula_los_tramos_completos_y_la_fraccion_del_ultimo(self) -> None:
        # Margen 0,25: 10 % al 1 %, 10 % al 2 %, y 5 % al 4 %.
        esperado = 0.10 * 0.01 + 0.10 * 0.02 + 0.05 * 0.04
        assert ESCALA_REGALIA.suma_de_tramos(0.25) == pytest.approx(esperado)

    def test_los_coeficientes_describen_la_recta_del_tramo(self) -> None:
        constante, pendiente = ESCALA_REGALIA.coeficientes(0.25)
        for margen in (0.21, 0.25, 0.39):
            assert constante + pendiente * margen == pytest.approx(
                ESCALA_REGALIA.suma_de_tramos(margen)
            )

    def test_la_regalia_es_afin_en_la_utilidad_operativa(self) -> None:
        # Es la propiedad que hace posible la solucion cerrada: la tasa
        # efectiva divide por el margen y despues se multiplica por la
        # utilidad, de modo que el margen se cancela contra si mismo.
        ventas = 1_000_000.0
        constante, pendiente = ESCALA_REGALIA.coeficientes(0.25)
        for utilidad in (210_000.0, 250_000.0, 390_000.0):
            regalia = ESCALA_REGALIA.suma_de_tramos(utilidad / ventas) * ventas
            assert regalia == pytest.approx(ventas * constante + pendiente * utilidad)

    def test_una_escala_con_hueco_no_se_construye(self) -> None:
        with pytest.raises(ErrorTributos, match="hueco"):
            EscalaProgresiva(tramos=(Tramo(0.0, 0.1, 0.01), Tramo(0.2, 0.3, 0.02)))

    def test_un_tramo_invertido_no_se_construye(self) -> None:
        with pytest.raises(ErrorTributos, match="invertido"):
            Tramo(0.3, 0.1, 0.01)


class TestCircularidad:
    def test_coincide_con_el_punto_fijo(self) -> None:
        # El requisito del ADR 0009: exacta y aproximada dan el mismo numero.
        datos = entradas()
        exacta = resolver(datos)
        aproximada = resolver_por_punto_fijo(datos)
        assert exacta.utilidad_operativa == pytest.approx(aproximada.utilidad_operativa, rel=1e-12)
        assert exacta.regalia == pytest.approx(aproximada.regalia, rel=1e-12)
        assert exacta.impuesto_renta == pytest.approx(aproximada.impuesto_renta, rel=1e-12)

    @pytest.mark.parametrize(
        "base_operativa",
        [50_000.0, 150_000.0, 250_000.0, 400_000.0, 700_000.0],
    )
    def test_coincide_con_el_punto_fijo_en_todos_los_tramos(self, base_operativa: float) -> None:
        datos = entradas(base_operativa=base_operativa, base_imponible=base_operativa - 20_000.0)
        assert resolver(datos).utilidad_operativa == pytest.approx(
            resolver_por_punto_fijo(datos).utilidad_operativa, rel=1e-12
        )

    def test_la_solucion_cierra_el_lazo(self) -> None:
        # El fondo de jubilacion es gasto de la utilidad operativa que lo
        # determina: la solucion tiene que satisfacer esa igualdad.
        datos = entradas()
        r = resolver(datos)
        assert r.utilidad_operativa == pytest.approx(
            datos.base_operativa - r.fondo_jubilacion_minera
        )

    def test_el_margen_es_la_utilidad_sobre_las_ventas(self) -> None:
        datos = entradas()
        r = resolver(datos)
        assert r.margen_operativo == pytest.approx(r.utilidad_operativa / datos.ventas_totales)


class TestRegalia:
    def test_la_regalia_minima_sobre_ventas_manda_cuando_el_margen_es_bajo(self) -> None:
        # Con margen pequeno la escala progresiva rinde menos que el 1 % de
        # ventas, y el libro toma el mayor de los dos.
        datos = entradas(base_operativa=30_000.0, base_imponible=25_000.0)
        r = resolver(datos)
        assert r.regalia == pytest.approx(datos.tasa_regalia_ventas * datos.ventas_totales)

    def test_con_margen_alto_manda_la_escala_progresiva(self) -> None:
        datos = entradas(base_operativa=700_000.0, base_imponible=680_000.0)
        r = resolver(datos)
        assert r.regalia > datos.tasa_regalia_ventas * datos.ventas_totales


class TestDeduccionesYSalidas:
    def test_las_perdidas_acumuladas_se_deducen_hasta_la_mitad_de_la_utilidad(self) -> None:
        sin_perdidas = resolver(entradas())
        con_perdidas = resolver(entradas(saldo_perdidas=1_000_000.0))
        assert con_perdidas.deduccion_perdidas == pytest.approx(
            -con_perdidas.utilidad_imponible * 0.5
        )
        assert con_perdidas.impuesto_renta < sin_perdidas.impuesto_renta

    def test_un_saldo_menor_que_el_limite_se_deduce_entero(self) -> None:
        r = resolver(entradas(saldo_perdidas=1_000.0))
        assert r.deduccion_perdidas == pytest.approx(-1_000.0)

    def test_sin_utilidad_no_hay_participacion_ni_renta(self) -> None:
        r = resolver(entradas(base_operativa=-50_000.0, base_imponible=-80_000.0))
        assert r.participacion_trabajadores == 0.0
        assert r.impuesto_renta == 0.0
        assert r.fondo_jubilacion_minera == 0.0

    def test_sin_ventas_no_hay_regalia_ni_margen(self) -> None:
        r = resolver(entradas(ventas_totales=0.0, base_operativa=0.0, base_imponible=0.0))
        assert r.regalia == 0.0
        assert r.margen_operativo == 0.0

    def test_la_renta_se_calcula_despues_de_participaciones(self) -> None:
        datos = entradas()
        r = resolver(datos)
        neta = r.utilidad_imponible + r.deduccion_perdidas
        esperado = (
            neta - r.fondo_jubilacion_minera - r.participacion_trabajadores
        ) * datos.tasa_impuesto_renta
        assert r.impuesto_renta == pytest.approx(esperado)
