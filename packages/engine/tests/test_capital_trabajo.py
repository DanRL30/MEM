"""Pruebas del capital de trabajo y del bloque de IGV, hoja `Otros` 57 a 84.

Las cifras son sintéticas y elegidas para que la aritmética se siga a mano. Lo
que se verifica no son los valores del modelo, que son confidenciales, sino las
reglas: con cuántos días se divide el año, en qué ejercicio se liquida el saldo,
qué entra dentro del interruptor y qué se queda fuera.
"""

from __future__ import annotations

import pytest

from minsur_engine.capital_trabajo import (
    DIAS_DEL_ANO_COMERCIAL,
    PESO_DEL_IGV_EN_EL_FLUJO,
    ErrorCapitalTrabajo,
    bloque_de_igv,
    credito_y_pago_de_igv,
    cuenta,
    igv,
    saldo_por_dias,
    variacion_de_capital_trabajo,
    variacion_de_cuenta,
)
from minsur_engine.horizonte import Horizonte


@pytest.fixture
def horizonte() -> Horizonte:
    return Horizonte(primer_ano=2027, anos=4)


class TestCuentasComerciales:
    def test_el_ano_comercial_es_de_360_dias(self) -> None:
        assert DIAS_DEL_ANO_COMERCIAL == 360.0
        saldos = saldo_por_dias((3_600.0,), (40.0,))
        assert saldos[0] == pytest.approx(400.0)

    def test_el_ano_comercial_lo_declara_el_caso_y_no_el_codigo(self) -> None:
        # El libro divide entre 360 y esa es la cifra por defecto, pero es dato:
        # un caso que trabaje sobre 365 lo dice en su plantilla de supuestos y no
        # obliga a tocar el motor.
        assert saldo_por_dias((3_600.0,), (36.0,), dias_del_ano=360.0) == (360.0,)
        assert saldo_por_dias((3_650.0,), (36.5,), dias_del_ano=365.0) == (365.0,)
        # Y el divisor mueve el saldo, que es la prueba de que se usa.
        a = saldo_por_dias((3_600.0,), (40.0,), dias_del_ano=360.0)
        b = saldo_por_dias((3_600.0,), (40.0,), dias_del_ano=365.0)
        assert a != b

    def test_un_ano_comercial_no_positivo_es_error(self) -> None:
        with pytest.raises(ErrorCapitalTrabajo, match="ano comercial"):
            saldo_por_dias((100.0,), (30.0,), dias_del_ano=0.0)

    def test_la_cartera_se_recupera_en_el_ultimo_ano_productivo(self) -> None:
        saldos = (100.0, 150.0, 150.0)
        produce = (True, True, False)
        variaciones = variacion_de_cuenta(saldos, produce, es_por_cobrar=True)
        assert variaciones[0] == pytest.approx(-100.0)
        assert variaciones[1] == pytest.approx(-50.0 + 150.0)
        assert variaciones[2] == pytest.approx(0.0)

    def test_cobrar_y_pagar_entran_con_signos_opuestos(self) -> None:
        saldos = (100.0, 100.0)
        produce = (True, True)
        cobrar = variacion_de_cuenta(saldos, produce, es_por_cobrar=True)
        pagar = variacion_de_cuenta(saldos, produce, es_por_cobrar=False)
        assert cobrar[0] == pytest.approx(-pagar[0])

    def test_la_cuenta_devuelve_el_saldo_y_su_variacion(self) -> None:
        # El saldo es fila propia del libro: sin el, una diferencia no se puede
        # atribuir al saldo o al delta.
        comercial = cuenta((3_600.0, 3_600.0), (40.0, 40.0), (True, True), es_por_cobrar=True)
        assert comercial.saldos == pytest.approx((400.0, 400.0))
        assert comercial.variaciones[0] == pytest.approx(-400.0)
        assert comercial.variaciones[1] == pytest.approx(400.0)

    def test_dias_negativos_son_error(self) -> None:
        with pytest.raises(ErrorCapitalTrabajo, match="negativos"):
            saldo_por_dias((100.0,), (-1.0,))


class TestElInterruptor:
    """`Control!$G$21` apaga las cuentas comerciales y deja el resto intacto."""

    def test_apaga_las_cuentas_comerciales(self, horizonte: Horizonte) -> None:
        argumentos = {
            "por_cobrar": horizonte.serie([-10.0] * 4, nombre="cxc"),
            "por_pagar": horizonte.serie([5.0] * 4, nombre="cxp"),
        }
        encendido = variacion_de_capital_trabajo(horizonte, cuentas_activas=True, **argumentos)
        apagado = variacion_de_capital_trabajo(horizonte, cuentas_activas=False, **argumentos)
        assert encendido[0] == pytest.approx(-5.0)
        assert apagado[0] == pytest.approx(0.0)

    def test_las_otras_cuentas_entran_dentro_del_interruptor(self, horizonte: Horizonte) -> None:
        # El libro las escribe dentro del parentesis, junto a las dos
        # variaciones, y con su propio signo: es la regla 050.
        ceros = horizonte.ceros()
        con_otras = variacion_de_capital_trabajo(
            horizonte,
            por_cobrar=ceros,
            por_pagar=ceros,
            otras_por_cobrar=horizonte.serie([7.0] * 4, nombre="otras cxc"),
            otras_por_pagar=horizonte.serie([3.0] * 4, nombre="otras cxp"),
        )
        assert con_otras[0] == pytest.approx(10.0)

    def test_el_igv_se_queda_fuera_del_interruptor(self, horizonte: Horizonte) -> None:
        # En el libro la variacion de IGV va fuera del parentesis: apagar las
        # cuentas comerciales no la apaga a ella.
        ceros = horizonte.ceros()
        apagado = variacion_de_capital_trabajo(
            horizonte,
            por_cobrar=horizonte.serie([-10.0] * 4, nombre="cxc"),
            por_pagar=ceros,
            variacion_igv=horizonte.serie([2.0] * 4, nombre="igv"),
            cuentas_activas=False,
        )
        assert apagado[0] == pytest.approx(2.0)


class TestBloqueDeIgv:
    """Se calcula entero y llega al flujo multiplicado por cero: regla 014."""

    def test_las_bases_son_la_venta_y_la_bolsa_por_su_porcentaje(
        self, horizonte: Horizonte
    ) -> None:
        bloque = bloque_de_igv(
            horizonte,
            ventas=horizonte.serie([1_000.0] * 4, nombre="ventas"),
            bolsa_de_egresos=horizonte.serie([500.0] * 4, nombre="bolsa"),
            tasa=0.18,
            porcentaje_de_ventas=0.60,
            porcentaje_de_compras=0.80,
        )
        assert bloque.ventas_gravadas[0] == pytest.approx(600.0)
        assert bloque.compras_gravadas[0] == pytest.approx(400.0)
        assert bloque.igv_de_ventas[0] == pytest.approx(108.0)
        assert bloque.igv_de_compras[0] == pytest.approx(72.0)

    def test_el_credito_o_pago_es_la_diferencia_de_los_dos_igv(self, horizonte: Horizonte) -> None:
        # `Otros!63`, la fila que dice si el ejercicio genera credito o deuda. Se
        # calculaba dentro de `credito_y_pago_de_igv` y se descartaba, de modo
        # que el salto del acumulado al pago llegaba sin derivacion.
        bloque = bloque_de_igv(
            horizonte,
            ventas=horizonte.serie([0.0, 1_000.0, 1_000.0, 0.0], nombre="ventas"),
            bolsa_de_egresos=horizonte.serie([900.0, 200.0, 200.0, 0.0], nombre="bolsa"),
            tasa=0.18,
            porcentaje_de_ventas=1.0,
            porcentaje_de_compras=1.0,
        )
        esperado = tuple(
            v - c for v, c in zip(bloque.igv_de_ventas, bloque.igv_de_compras, strict=True)
        )
        assert bloque.credito_o_pago == pytest.approx(esperado)
        assert bloque.credito_o_pago[0] == pytest.approx(-162.0)

    def test_el_bloque_tiene_cifras_y_no_mueve_el_flujo(self, horizonte: Horizonte) -> None:
        # Las dos mitades de la regla 014, juntas: si se borrara el bloque
        # fallaria la primera, y si el cero se volviera un interruptor de
        # negocio fallaria la segunda.
        bloque = bloque_de_igv(
            horizonte,
            ventas=horizonte.serie([0.0, 1_000.0, 1_000.0, 0.0], nombre="ventas"),
            bolsa_de_egresos=horizonte.serie([900.0, 200.0, 200.0, 0.0], nombre="bolsa"),
            tasa=0.18,
            porcentaje_de_ventas=1.0,
            porcentaje_de_compras=1.0,
        )
        assert any(x != 0.0 for x in bloque.credito_acumulado)
        assert bloque.variacion_para_el_flujo == horizonte.ceros()
        assert PESO_DEL_IGV_EN_EL_FLUJO == 0.0

    def test_el_credito_fiscal_se_acumula_y_se_consume(self) -> None:
        # Ano 1: el IGV de compras supera al de ventas, se desembolsan 50 y
        # queda ese credito acumulado. Ano 2: el neto es 80, se consume el
        # credito y se paga la diferencia, 30.
        credito, pagos = credito_y_pago_de_igv((10.0, 100.0), (60.0, 20.0))
        assert credito == pytest.approx((50.0, 0.0))
        assert pagos == pytest.approx((-50.0, -30.0))

    def test_un_credito_mayor_que_el_saldo_evita_el_pago(self) -> None:
        credito, pagos = credito_y_pago_de_igv((10.0, 30.0), (60.0, 20.0))
        assert pagos == pytest.approx((-50.0, 0.0))
        assert credito[1] == pytest.approx(40.0)

    def test_una_tasa_fuera_de_rango_es_error(self) -> None:
        with pytest.raises(ErrorCapitalTrabajo, match="Tasa de IGV"):
            igv((100.0,), 1.4)
