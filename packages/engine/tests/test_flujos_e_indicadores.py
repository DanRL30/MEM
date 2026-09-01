"""Pruebas del flujo, del capital de trabajo y de los indicadores.

Los indicadores son lo que el contraste N3 verifica con tolerancias estrechas,
así que aquí se comprueban las convenciones antes que los valores: dónde cae la
participación de trabajadores, con cuántos días se divide el año comercial y
desde qué exponente descuenta el factor.
"""

from __future__ import annotations

import pytest

from minsur_engine.capital_trabajo import (
    DIAS_DEL_ANO_COMERCIAL,
    ErrorCapitalTrabajo,
    credito_y_pago_de_igv,
    igv,
    saldo_por_dias,
    variacion_de_capital_trabajo,
    variacion_de_cuenta,
)
from minsur_engine.flujos import (
    ComponentesDeInversion,
    ComponentesOperativos,
    ErrorFlujos,
    flujo_del_caso,
)
from minsur_engine.horizonte import Horizonte
from minsur_engine.indicadores import (
    ErrorIndicadores,
    capital_intensity,
    factores_de_descuento,
    npv,
    payback,
    payback_descontado,
    tir,
)


@pytest.fixture
def horizonte() -> Horizonte:
    return Horizonte(primer_ano=2027, anos=4)


class TestFlujo:
    def test_la_participacion_entra_en_el_ebitda(self) -> None:
        # El libro la resta antes del EBITDA ajustado, no con los tributos.
        con = ComponentesOperativos(
            ventas=1_000.0, cash_cost=400.0, participacion_trabajadores=50.0
        )
        sin = ComponentesOperativos(ventas=1_000.0, cash_cost=400.0)
        assert con.ebitda_ajustado == pytest.approx(550.0)
        assert sin.ebitda_ajustado == pytest.approx(600.0)

    def test_el_flujo_operativo_descuenta_tributos_y_suma_el_capital_de_trabajo(self) -> None:
        operativos = ComponentesOperativos(
            ventas=1_000.0,
            cash_cost=400.0,
            impuestos=100.0,
            variacion_capital_trabajo=-30.0,
        )
        assert operativos.flujo_operativo == pytest.approx(600.0 - 30.0 - 100.0)

    def test_una_inversion_siempre_sale_de_caja(self) -> None:
        inversion = ComponentesDeInversion(capex_inicial=500.0, estudios=20.0)
        assert inversion.flujo_de_inversiones == pytest.approx(-520.0)

    def test_un_egreso_negativo_es_error(self) -> None:
        # El signo lo pone la formula; un costo en negativo es un dato mal cargado.
        with pytest.raises(ErrorFlujos, match="magnitud"):
            ComponentesOperativos(ventas=1_000.0, cash_cost=-400.0)

    def test_el_flujo_economico_suma_operacion_e_inversion(self, horizonte: Horizonte) -> None:
        operativos = [ComponentesOperativos(ventas=1_000.0, cash_cost=400.0)] * 4
        inversiones = [ComponentesDeInversion(capex_inicial=200.0)] + [ComponentesDeInversion()] * 3
        flujo = flujo_del_caso(horizonte, operativos, inversiones)
        assert flujo.flujo_economico[0] == pytest.approx(400.0)
        assert flujo.flujo_economico[1] == pytest.approx(600.0)

    def test_un_horizonte_desalineado_es_error(self, horizonte: Horizonte) -> None:
        with pytest.raises(ErrorFlujos, match="4 anos"):
            flujo_del_caso(horizonte, [ComponentesOperativos(ventas=1.0, cash_cost=0.0)], [])


class TestCapitalDeTrabajo:
    def test_el_ano_comercial_es_de_360_dias(self) -> None:
        assert DIAS_DEL_ANO_COMERCIAL == 360.0
        saldos = saldo_por_dias((3_600.0,), (40.0,))
        assert saldos[0] == pytest.approx(400.0)

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

    def test_el_interruptor_apaga_las_cuentas_comerciales(self, horizonte: Horizonte) -> None:
        # Reproduce Control!$G$21 del libro.
        argumentos = {
            "por_cobrar": horizonte.serie([-10.0] * 4, nombre="cxc"),
            "por_pagar": horizonte.serie([5.0] * 4, nombre="cxp"),
        }
        encendido = variacion_de_capital_trabajo(horizonte, cuentas_activas=True, **argumentos)
        apagado = variacion_de_capital_trabajo(horizonte, cuentas_activas=False, **argumentos)
        assert encendido[0] == pytest.approx(-5.0)
        assert apagado[0] == pytest.approx(0.0)

    def test_el_igv_se_calcula_y_no_entra_en_el_flujo(self, horizonte: Horizonte) -> None:
        # Regla 014: el libro lo multiplica por cero al llevarlo al flujo.
        ventas = horizonte.serie([1_000.0] * 4, nombre="ventas")
        assert igv(ventas, 0.18)[0] == pytest.approx(180.0)
        sin_igv = variacion_de_capital_trabajo(
            horizonte,
            por_cobrar=horizonte.ceros(),
            por_pagar=horizonte.ceros(),
        )
        assert sin_igv == horizonte.ceros()

    def test_el_credito_fiscal_se_acumula_y_se_consume(self) -> None:
        # Ano 1: el IGV de compras supera al de ventas, se desembolsan 50 y
        # queda ese credito acumulado. Ano 2: el neto es 80, se consume el
        # credito y se paga la diferencia, 30. El pago no llega a cero porque
        # el credito no alcanza a cubrir todo el saldo del ejercicio.
        credito, pagos = credito_y_pago_de_igv((10.0, 100.0), (60.0, 20.0))
        assert credito == pytest.approx((50.0, 0.0))
        assert pagos == pytest.approx((-50.0, -30.0))

    def test_un_credito_mayor_que_el_saldo_evita_el_pago(self) -> None:
        credito, pagos = credito_y_pago_de_igv((10.0, 30.0), (60.0, 20.0))
        assert pagos == pytest.approx((-50.0, 0.0))
        assert credito[1] == pytest.approx(40.0)

    def test_dias_negativos_son_error(self) -> None:
        with pytest.raises(ErrorCapitalTrabajo, match="negativos"):
            saldo_por_dias((100.0,), (-1.0,))


class TestIndicadores:
    def test_el_factor_descuenta_a_fin_de_ano(self) -> None:
        factores = factores_de_descuento(0.10, 3)
        assert factores == pytest.approx((1.0, 1 / 1.1, 1 / 1.21))

    def test_el_npv_descuenta_cada_ano_con_su_factor(self) -> None:
        assert npv([-100.0, 110.0], 0.10) == pytest.approx(0.0)

    def test_la_tir_anula_el_npv(self) -> None:
        flujo = [-1_000.0, 300.0, 400.0, 500.0]
        tasa = tir(flujo)
        assert npv(flujo, tasa) == pytest.approx(0.0, abs=1e-6)

    def test_la_tir_es_reproducible(self) -> None:
        # Es la condicion del sellado: dos corridas, el mismo numero.
        flujo = [-1_000.0, 300.0, 400.0, 500.0]
        assert tir(flujo) == tir(flujo)

    def test_un_flujo_sin_cambio_de_signo_no_tiene_tir(self) -> None:
        with pytest.raises(ErrorIndicadores, match="no cambia de signo"):
            tir([100.0, 200.0, 300.0])

    def test_el_payback_interpola_dentro_del_ano(self) -> None:
        # Se recuperan 100 el primer ano y quedan 100 por recuperar de un flujo
        # de 200: el cruce cae a la mitad del segundo ejercicio.
        resultado = payback([-200.0, 100.0, 200.0])
        assert resultado.alcanzado
        assert resultado.anos == pytest.approx(2.5)

    def test_el_payback_avisa_cuando_no_se_alcanza(self) -> None:
        resultado = payback([-500.0, 100.0, 100.0])
        assert not resultado.alcanzado

    def test_el_payback_descontado_tarda_mas_que_el_simple(self) -> None:
        flujo = [-1_000.0, 400.0, 400.0, 400.0, 400.0]
        assert payback_descontado(flujo, 0.10).anos > payback(flujo).anos

    def test_la_intensidad_de_capital_exige_capacidad(self) -> None:
        assert capital_intensity(1_000.0, 50.0) == pytest.approx(20.0)
        with pytest.raises(ErrorIndicadores, match="Capacidad anual invalida"):
            capital_intensity(1_000.0, 0.0)
