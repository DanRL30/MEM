"""Pruebas del capital y de la depreciación.

Tres reglas del libro se verifican aquí y conviene nombrarlas: el cuadre de las
dos clasificaciones del capital, el ajuste de la última cuota al saldo, y que la
depreciación no corre antes de que la unidad produzca.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from minsur_engine.capex import (
    CapitalDeUnidad,
    ErrorCapex,
    capex_de_etapa,
    capex_de_sostenimiento,
    capex_total,
)
from minsur_engine.depreciacion import (
    ErrorDepreciacion,
    TasasDeDepreciacion,
    cronograma_de_inversion,
    cuota,
    depreciacion_de_unidad,
    depreciacion_por_mina,
    depreciar,
    total_depreciado,
)
from minsur_engine.horizonte import Horizonte

TASAS = TasasDeDepreciacion(maquinaria=0.20, instalaciones=0.10, edificaciones=0.05)


@pytest.fixture
def horizonte() -> Horizonte:
    return Horizonte(primer_ano=2027, anos=8)


def capital(
    horizonte: Horizonte,
    *,
    unidad: str = "San Rafael",
    inicial: Sequence[float] | None = None,
) -> CapitalDeUnidad:
    """Unidad con 100 de maquinaria en el primer año, cuadrada por construcción."""
    valores = list(inicial) if inicial is not None else [100.0] + [0.0] * (horizonte.anos - 1)
    serie = horizonte.serie(valores, nombre="inicial")
    return CapitalDeUnidad(
        unidad=unidad,
        por_etapa={"inicial": serie},
        por_naturaleza={"maquinaria": serie},
    )


class TestCuadreDelCapital:
    def test_las_dos_clasificaciones_deben_sumar_lo_mismo(self, horizonte: Horizonte) -> None:
        with pytest.raises(ErrorCapex, match="no cuadran"):
            CapitalDeUnidad(
                unidad="San Rafael",
                por_etapa={"inicial": horizonte.serie([100.0] + [0.0] * 7, nombre="inicial")},
                por_naturaleza={
                    "maquinaria": horizonte.serie([90.0] + [0.0] * 7, nombre="maquinaria")
                },
            )

    def test_una_etapa_desconocida_es_error(self, horizonte: Horizonte) -> None:
        with pytest.raises(ErrorCapex, match="desconocida"):
            CapitalDeUnidad(
                unidad="San Rafael",
                por_etapa={"ampliacion": horizonte.ceros()},
                por_naturaleza={"maquinaria": horizonte.ceros()},
            )

    def test_el_sostenimiento_del_flujo_es_el_total_menos_el_inicial(
        self, horizonte: Horizonte
    ) -> None:
        # El libro no lee la fila de sostenimiento: la deduce restando.
        unidad = CapitalDeUnidad(
            unidad="San Rafael",
            por_etapa={
                "inicial": horizonte.serie([100.0] + [0.0] * 7, nombre="inicial"),
                "cierre": horizonte.serie([0.0] * 7 + [30.0], nombre="cierre"),
            },
            por_naturaleza={
                "maquinaria": horizonte.serie([100.0] + [0.0] * 7, nombre="maquinaria"),
                "instalaciones": horizonte.serie([0.0] * 7 + [30.0], nombre="instalaciones"),
            },
        )
        sostenimiento = capex_de_sostenimiento(horizonte, [unidad])
        assert sostenimiento[0] == pytest.approx(0.0)
        assert sostenimiento[7] == pytest.approx(30.0)

    def test_los_totales_suman_las_unidades(self, horizonte: Horizonte) -> None:
        unidades = [capital(horizonte), capital(horizonte, unidad="Nazareth")]
        assert capex_total(horizonte, unidades)[0] == pytest.approx(200.0)
        assert capex_de_etapa(horizonte, unidades, "inicial")[0] == pytest.approx(200.0)

    def test_un_caso_sin_unidades_no_tiene_capital(self, horizonte: Horizonte) -> None:
        assert capex_total(horizonte, []) == horizonte.ceros()


class TestCuota:
    def test_la_cuota_corriente_es_lineal_sobre_el_valor_original(self) -> None:
        assert cuota(base=100.0, tasa=0.20, acumulado=0.0) == pytest.approx(20.0)
        assert cuota(base=100.0, tasa=0.20, acumulado=40.0) == pytest.approx(20.0)

    def test_la_ultima_cuota_se_ajusta_al_saldo(self) -> None:
        # Sin este ajuste el activo nunca llega a cero y el contraste ve una
        # diferencia pequena y persistente.
        assert cuota(base=100.0, tasa=0.30, acumulado=90.0) == pytest.approx(10.0)

    def test_un_activo_depreciado_no_genera_mas_cuota(self) -> None:
        assert cuota(base=100.0, tasa=0.20, acumulado=100.0) == 0.0

    def test_el_cronograma_agota_exactamente_la_base(self) -> None:
        cuotas = cronograma_de_inversion(base=100.0, tasa=0.30, ejercicios=8)
        assert sum(cuotas) == pytest.approx(100.0)
        assert cuotas[:3] == pytest.approx((30.0, 30.0, 30.0))
        assert cuotas[3] == pytest.approx(10.0)
        assert cuotas[4] == 0.0

    def test_un_horizonte_corto_deja_capital_sin_depreciar(self) -> None:
        # No es un defecto: es lo que ocurre cuando la vida util excede el
        # horizonte, y el valor residual lo recoge otro bloque.
        assert sum(cronograma_de_inversion(base=100.0, tasa=0.10, ejercicios=5)) == pytest.approx(
            50.0
        )


class TestDepreciacion:
    def test_las_inversiones_de_anos_distintos_se_superponen(self, horizonte: Horizonte) -> None:
        inversiones = horizonte.serie([100.0, 0.0, 100.0, 0.0, 0.0, 0.0, 0.0, 0.0], nombre="capex")
        serie = depreciar(horizonte, inversiones, tasa=0.50)
        assert serie[0] == pytest.approx(50.0)
        assert serie[1] == pytest.approx(50.0)
        assert serie[2] == pytest.approx(50.0)  # solo la segunda inversion
        assert serie[3] == pytest.approx(50.0)
        assert serie[4] == 0.0

    def test_no_deprecia_antes_de_que_la_unidad_produzca(self, horizonte: Horizonte) -> None:
        unidad = capital(horizonte)
        sin_gate = depreciacion_de_unidad(horizonte, unidad, TASAS)
        produccion = horizonte.serie([0.0, 0.0, 500.0, 500.0, 0.0, 0.0, 0.0, 0.0], nombre="prod")
        con_gate = depreciacion_de_unidad(horizonte, unidad, TASAS, produccion=produccion)
        assert sin_gate[0] > 0.0
        assert con_gate[:2] == (0.0, 0.0)
        assert con_gate[2] == pytest.approx(sin_gate[2])

    def test_lo_no_depreciable_no_genera_depreciacion(self, horizonte: Horizonte) -> None:
        unidad = CapitalDeUnidad(
            unidad="San Rafael",
            por_etapa={"inicial": horizonte.serie([100.0] + [0.0] * 7, nombre="inicial")},
            por_naturaleza={
                "no_depreciable": horizonte.serie([100.0] + [0.0] * 7, nombre="terreno")
            },
        )
        assert depreciacion_de_unidad(horizonte, unidad, TASAS) == horizonte.ceros()

    def test_una_tasa_en_porcentaje_se_rechaza(self) -> None:
        with pytest.raises(ErrorDepreciacion, match="fraccion"):
            TasasDeDepreciacion(maquinaria=20.0, instalaciones=0.10, edificaciones=0.05)


class TestDesglosePorMina:
    def test_devuelve_una_serie_por_unidad(self, horizonte: Horizonte) -> None:
        # D-04: MINSUR pidio el calculo separado por mina en todos los casos.
        unidades = [capital(horizonte), capital(horizonte, unidad="Nazareth")]
        por_mina = depreciacion_por_mina(horizonte, unidades, TASAS)
        assert set(por_mina) == {"San Rafael", "Nazareth"}

    def test_el_total_es_la_suma_del_desglose(self, horizonte: Horizonte) -> None:
        unidades = [capital(horizonte), capital(horizonte, unidad="Nazareth")]
        por_mina = depreciacion_por_mina(horizonte, unidades, TASAS)
        total = total_depreciado(horizonte, por_mina)
        assert total[0] == pytest.approx(por_mina["San Rafael"][0] + por_mina["Nazareth"][0])

    def test_el_gate_de_produccion_se_aplica_por_unidad(self, horizonte: Horizonte) -> None:
        unidades = [capital(horizonte), capital(horizonte, unidad="Nazareth")]
        produccion = {
            "Nazareth": horizonte.serie([0.0, 0.0, 0.0, 700.0] + [0.0] * 4, nombre="prod")
        }
        por_mina = depreciacion_por_mina(horizonte, unidades, TASAS, produccion=produccion)
        assert por_mina["San Rafael"][0] > 0.0
        assert por_mina["Nazareth"][:3] == (0.0, 0.0, 0.0)
