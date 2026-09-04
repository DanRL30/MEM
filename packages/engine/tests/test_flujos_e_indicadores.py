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
    FlujoDelCaso,
    flujo_del_caso,
)
from minsur_engine.horizonte import Horizonte
from minsur_engine.indicadores import (
    TASA_MAXIMA_BUSCADA,
    TASA_MINIMA_BUSCADA,
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


class TestLaHojaSaleEntera:
    """`FC NZ` publica sus veinte filas y no solo las cuatro de cierre.

    De las diecisiete lineas de entrada salian cero: se componian dentro de
    `corrida.calcular` y morian ahi, de modo que una discrepancia en el flujo no
    se podia atribuir a la fila que la causaba.
    """

    @pytest.fixture
    def flujo(self, horizonte: Horizonte) -> FlujoDelCaso:
        operativos = [
            ComponentesOperativos(
                ventas=1_000.0,
                cash_cost=400.0,
                fletes=20.0,
                gasto_de_ventas=10.0,
                gasto_administrativo=30.0,
                gestion_social=15.0,
                otros_gastos=5.0,
                participacion_trabajadores=40.0,
                impuestos=90.0,
                intereses=25.0,
                otros=3.0,
                variacion_capital_trabajo=-12.0,
            )
        ] * 4
        inversiones = [
            ComponentesDeInversion(
                capex_inicial=200.0,
                capex_sostenimiento=50.0,
                estudios=8.0,
                exploraciones=6.0,
                predios=4.0,
            )
        ] * 4
        return flujo_del_caso(
            horizonte,
            operativos,
            inversiones,
            tasa_descuento=0.10,
            produce=(False, True, True, True),
        )

    def test_los_egresos_salen_con_el_signo_del_libro(self, flujo: FlujoDelCaso) -> None:
        # La hoja los escribe en negativo y los suma; el motor los lleva en
        # magnitud positiva. Si el signo no se pusiera aqui, cada total tendria
        # que restarse a mano y dejaria de ser la suma de lo que tiene encima.
        assert flujo.ventas[0] == pytest.approx(1_000.0)
        assert flujo.cash_cost[0] == pytest.approx(-400.0)
        assert flujo.participaciones[0] == pytest.approx(-40.0)
        assert flujo.capex_inicial[0] == pytest.approx(-200.0)
        # La variacion de capital de trabajo pasa como viene: ya lleva signo.
        assert flujo.variacion_capital_trabajo[0] == pytest.approx(-12.0)

    def test_los_tres_cierres_suman_sus_filas(self, flujo: FlujoDelCaso) -> None:
        cierres = (
            (flujo.ebitda_ajustado, flujo.sumandos_del_ebitda),
            (flujo.flujo_operativo, flujo.sumandos_del_operativo),
            (flujo.flujo_de_inversiones, flujo.sumandos_de_inversiones),
        )
        for total, sumandos in cierres:
            for ano, obtenido in enumerate(total):
                assert obtenido == pytest.approx(sum(s[ano] for s in sumandos)), f"ano {ano}"

    def test_el_flujo_economico_devuelve_los_intereses(self, flujo: FlujoDelCaso) -> None:
        """`FC NZ!35` es `27 + 33 - 25`: el economico es anterior al financiamiento.

        El flujo operativo ya descontó los intereses y esta línea los devuelve.
        Hasta el 04/09/2026 el motor los dejaba dentro, y no se veía porque los
        intereses valen cero en todos los casos del arnés. Es la regla `095`.
        """
        for ano, economico in enumerate(flujo.flujo_economico):
            esperado = (
                flujo.flujo_operativo[ano] + flujo.flujo_de_inversiones[ano] - flujo.intereses[ano]
            )
            assert economico == pytest.approx(esperado), f"ano {ano}"
        # Y con intereses el economico queda por encima del operativo mas la
        # inversion, que es lo que delata que se han devuelto.
        assert flujo.flujo_economico[0] > flujo.flujo_operativo[0] + flujo.flujo_de_inversiones[0]

    def test_las_banderas_reproducen_las_tres_filas_vivas(self, flujo: FlujoDelCaso) -> None:
        # El libro lleva cinco y dos estan muertas: `Periodo pre-operativo` son
        # ceros tecleados y `Ano cierre` no lo lee ninguna celda. Regla `092`.
        assert flujo.banderas is not None
        assert flujo.banderas.periodo_proyecto == (0.0, 1.0, 2.0, 3.0)
        assert flujo.banderas.periodo_con_gastos == (1.0,) * 4
        assert flujo.banderas.periodo_operativo == (0.0, 1.0, 1.0, 1.0)

    def test_el_flujo_descontado_reconstruye_el_npv(self, flujo: FlujoDelCaso) -> None:
        # `FC NZ!40` es `39 x 35`, y su suma es la fila `41`. Que el acumulado de
        # esa fila sea el NPV es lo que permite no emitirlo como una fila aparte.
        for ano, descontado in enumerate(flujo.flujo_descontado):
            esperado = flujo.factor_de_descuento[ano] * flujo.flujo_economico[ano]
            assert descontado == pytest.approx(esperado), f"ano {ano}"
        assert sum(flujo.flujo_descontado) == pytest.approx(npv(flujo.flujo_economico, 0.10))

    def test_el_factor_del_primer_ejercicio_vale_uno(self, flujo: FlujoDelCaso) -> None:
        # Aqui la plataforma **no** reproduce el libro, que teclea un cero en esa
        # celda y ademas suma el NPV desde la segunda columna. Son dos candados
        # independientes: es la regla `062`, consultada y sin respuesta, y la
        # `090`. Con el cero, este ejercicio quedaria fuera del NPV.
        assert flujo.factor_de_descuento[0] == pytest.approx(1.0)
        assert flujo.factor_de_descuento[1] == pytest.approx(1.0 / 1.1)


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

    def test_la_tir_aparece_aunque_los_extremos_no_la_encierren(self) -> None:
        # Perfil de un proyecto con desembolso inicial y ejercicio de cierre: el
        # NPV queda negativo en los dos extremos del intervalo buscado y positivo
        # en medio. Corcheteando con los bordes, la TIR existia y no se hallaba.
        flujo = [0.0, -100.0, -300.0, -500.0, 200.0, 300.0, 300.0, 300.0, 300.0, -50.0]
        assert npv(flujo, TASA_MINIMA_BUSCADA) < 0.0
        assert npv(flujo, TASA_MAXIMA_BUSCADA) < 0.0
        tasa = tir(flujo)
        assert tasa > 0.0
        assert npv(flujo, tasa) == pytest.approx(0.0, abs=1e-6)

    def test_un_flujo_que_abre_en_positivo_no_tiene_tir(self) -> None:
        # Operacion en marcha que solo baja de cero en los ejercicios de cierre:
        # su unica raiz es negativa y no es una rentabilidad. El libro responde
        # lo mismo con el guion de su `IFERROR`.
        with pytest.raises(ErrorIndicadores, match="operacion en marcha"):
            tir([100.0, 100.0, 100.0, -5.0])

    def test_una_inversion_que_no_se_recupera_no_tiene_tir(self) -> None:
        # Hay desembolso inicial, pero el NPV no cruza cero en ninguna tasa no
        # negativa. Se dice, en vez de entregar una tasa por debajo de cero.
        with pytest.raises(ErrorIndicadores, match="tasa no negativa"):
            tir([-1_000.0, 100.0, 100.0])

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
