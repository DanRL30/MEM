"""Pruebas de las tres reglas de producción leídas del modelo de referencia.

Cada prueba nombra la regla del libro que verifica. Cuando el contraste N1
señale una discrepancia en la línea de producción, esta es la primera parada:
si estas pruebas pasan y el contraste falla, el problema está en los datos o
en un bloque posterior, no aquí.
"""

from __future__ import annotations

import pytest

from minsur_engine.horizonte import ErrorHorizonte, Horizonte, anos_con_dato
from minsur_engine.parametros import ErrorParametros, ParametrosCorporativos
from minsur_engine.produccion import (
    ErrorProduccion,
    alimentacion_a_la_refineria,
    excedente_por_capacidad,
    ley_agregada,
    tratamiento_limitado,
)


@pytest.fixture
def horizonte() -> Horizonte:
    return Horizonte(primer_ano=2027, anos=5)


class TestLeyAgregada:
    """SUMPRODUCT(tonelaje, ley) / SUM(tonelaje), tal como lo hace el libro."""

    def test_pondera_por_tonelaje_y_no_promedia_leyes(self) -> None:
        # Con 90 t al 1 % y 10 t al 5 %, la media simple daria 3 %.
        assert ley_agregada([90.0, 10.0], [0.01, 0.05]) == pytest.approx(0.014)

    def test_tonelaje_nulo_devuelve_cero_y_no_falla(self) -> None:
        # Regla 008: el libro envuelve la division en IFERROR y Finanzas
        # confirmo que cero es el resultado esperado.
        assert ley_agregada([0.0, 0.0], [0.02, 0.03]) == 0.0

    def test_un_ano_sin_produccion_no_arrastra_su_ley(self) -> None:
        assert ley_agregada([100.0, 0.0], [0.02, 0.9]) == pytest.approx(0.02)

    def test_longitudes_distintas_son_error(self) -> None:
        with pytest.raises(ErrorProduccion, match="misma longitud"):
            ley_agregada([1.0, 2.0], [0.01])


class TestCapacidadDeLaRefineria:
    """min(alimentado, capacidad) y su complementaria, filas 90 a 100 del libro."""

    def test_sin_restriccion_trata_todo_lo_alimentado(self) -> None:
        alimentado = (80_000.0, 85_000.0)
        capacidad = (90_000.0, 90_000.0)
        assert tratamiento_limitado(alimentado, capacidad) == alimentado
        assert excedente_por_capacidad(alimentado, capacidad) == (0.0, 0.0)

    def test_con_restriccion_trata_la_capacidad_y_separa_el_excedente(self) -> None:
        alimentado = (95_000.0, 120_000.0)
        capacidad = (90_000.0, 90_000.0)
        assert tratamiento_limitado(alimentado, capacidad) == (90_000.0, 90_000.0)
        assert excedente_por_capacidad(alimentado, capacidad) == (5_000.0, 30_000.0)

    def test_lo_tratado_mas_lo_excedente_es_lo_alimentado(self) -> None:
        alimentado = (95_000.0, 40_000.0, 90_000.0)
        capacidad = (90_000.0, 90_000.0, 90_000.0)
        tratado = tratamiento_limitado(alimentado, capacidad)
        excedente = excedente_por_capacidad(alimentado, capacidad)
        for a, t, e in zip(alimentado, tratado, excedente, strict=True):
            assert t + e == pytest.approx(a)

    def test_la_capacidad_puede_cambiar_ano_a_ano(self) -> None:
        # Es lo que habilita la respuesta de Finanzas del 01/09/2026: la
        # capacidad dejo de ser una constante y es un dato del caso.
        alimentado = (95_000.0, 95_000.0)
        assert tratamiento_limitado(alimentado, (90_000.0, 110_000.0)) == (90_000.0, 95_000.0)

    def test_capacidad_negativa_es_error(self) -> None:
        with pytest.raises(ErrorProduccion, match="Capacidad negativa"):
            tratamiento_limitado((10.0,), (-1.0,))


class TestAlimentacionALaRefineria:
    def test_suma_los_aportes_de_las_unidades(self, horizonte: Horizonte) -> None:
        sr = horizonte.serie([10.0, 10.0, 10.0, 10.0, 10.0], nombre="SR")
        nazareth = horizonte.serie([0.0, 0.0, 5.0, 5.0, 5.0], nombre="Nazareth")
        assert alimentacion_a_la_refineria(horizonte, [sr, nazareth]) == (
            10.0,
            10.0,
            15.0,
            15.0,
            15.0,
        )

    def test_un_caso_sin_unidades_da_serie_nula(self, horizonte: Horizonte) -> None:
        assert alimentacion_a_la_refineria(horizonte, []) == (0.0, 0.0, 0.0, 0.0, 0.0)

    def test_aporte_desalineado_es_error(self, horizonte: Horizonte) -> None:
        with pytest.raises(ErrorProduccion, match="horizonte tiene 5 anos"):
            alimentacion_a_la_refineria(horizonte, [(1.0, 2.0)])


class TestHorizonte:
    def test_los_factores_descuentan_a_fin_de_ano(self) -> None:
        # Regla 005: 1/(1+r)^t con t entero desde 0, no desde 0,5.
        factores = Horizonte(primer_ano=2027, anos=3).factores_descuento(0.10)
        assert factores[0] == 1.0
        assert factores[1] == pytest.approx(1 / 1.10)
        assert factores[2] == pytest.approx(1 / 1.21)

    def test_una_serie_desalineada_no_entra(self, horizonte: Horizonte) -> None:
        with pytest.raises(ErrorHorizonte, match="trae 2 valores"):
            horizonte.serie([1.0, 2.0], nombre="produccion")

    def test_un_valor_no_finito_se_detiene_en_la_frontera(self, horizonte: Horizonte) -> None:
        with pytest.raises(ErrorHorizonte, match="no finito en el ano 2029"):
            horizonte.serie([1.0, 1.0, float("nan"), 1.0, 1.0], nombre="ley")

    def test_horizonte_desmesurado_se_rechaza(self) -> None:
        with pytest.raises(ErrorHorizonte, match="maximo"):
            Horizonte(primer_ano=2027, anos=200)

    def test_la_participacion_se_deriva_de_los_datos(self) -> None:
        # Criterio de Finanzas del 01/09/2026: una unidad entra en el caso en
        # los anos en que tiene valores, sin interruptor que la active.
        assert anos_con_dato([0.0, 0.0, 12.0, 15.0, 0.0]) == (2, 3)
        assert anos_con_dato([0.0, 0.0]) == ()


class TestParametrosCorporativos:
    def test_una_tasa_en_porcentaje_se_rechaza(self) -> None:
        with pytest.raises(ErrorParametros, match="tanto por uno"):
            ParametrosCorporativos(
                version_datos_maestros="CP-2026-08",
                tasa_descuento=10.0,
                participacion_trabajadores=0.08,
                impuesto_renta=0.295,
                regalia_minima=0.01,
                osinergmin=0.0014,
                oefa=0.001,
                fondo_jubilacion_minera=0.005,
            )

    def test_sin_version_de_datos_maestros_no_hay_parametros(self) -> None:
        with pytest.raises(ErrorParametros, match="version de datos maestros"):
            ParametrosCorporativos(
                version_datos_maestros="  ",
                tasa_descuento=0.10,
                participacion_trabajadores=0.08,
                impuesto_renta=0.295,
                regalia_minima=0.01,
                osinergmin=0.0014,
                oefa=0.001,
                fondo_jubilacion_minera=0.005,
            )
