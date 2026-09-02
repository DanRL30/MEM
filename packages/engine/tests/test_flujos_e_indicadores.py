"""Pruebas del flujo y de los indicadores.

Los indicadores son lo que el contraste N3 verifica con tolerancias estrechas,
así que aquí se comprueban las convenciones antes que los valores: dónde cae la
participación de trabajadores y desde qué exponente descuenta el factor. El
capital de trabajo tiene su propio módulo, `test_capital_trabajo.py`.
"""

from __future__ import annotations

import pytest

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
