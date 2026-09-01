"""Pruebas de ventas y de costos, contra las reglas leídas de la hoja `Ventas`.

Los números de estas pruebas son sintéticos y elegidos para que la aritmética
se pueda seguir a mano. Lo que se verifica no son los valores del modelo, que
son confidenciales, sino las reglas: qué se multiplica por qué, con qué
toneladas y con qué conversión.
"""

from __future__ import annotations

import pytest

from minsur_engine.cash_cost import (
    CostoDeUnidad,
    ErrorCashCost,
    cash_cost_por_unidad,
    cash_cost_total,
    cash_cost_unitario,
    flete,
    gasto_de_ventas,
    total_de_conceptos,
)
from minsur_engine.ventas import (
    GRAMOS_POR_ONZA_TROY,
    ErrorVentas,
    LiquidacionConcentrado,
    MetalPagable,
    liquidar_concentrado,
    venta_de_metal_en_concentrado,
    venta_de_metal_refinado,
    venta_total,
)


def concentrado_de_prueba(
    *,
    toneladas_vendidas: float = 1_000.0,
    merma: float = 0.03,
    maquila_por_tonelada: float = 200.0,
    penalidades: float = 0.0,
) -> LiquidacionConcentrado:
    """Embarque de prueba con un metal base y uno precioso."""
    return liquidar_concentrado(
        toneladas_vendidas=toneladas_vendidas,
        merma=merma,
        metales=[
            MetalPagable(nombre="Cu", ley_pagable=0.25, precio=9_000.0, cargo_de_refinacion=50.0),
            MetalPagable(
                nombre="Ag",
                ley_pagable=100.0,
                precio=30.0,
                cargo_de_refinacion=10.0,
                en_onzas_troy=True,
            ),
        ],
        maquila_por_tonelada=maquila_por_tonelada,
        penalidades=penalidades,
    )


class TestVentaDeEstano:
    def test_el_refinado_suma_el_premio_al_spot(self) -> None:
        assert venta_de_metal_refinado(100.0, 30_000.0, 500.0) == pytest.approx(3_050_000.0)

    def test_el_concentrado_aplica_el_factor_de_metal_pagable(self) -> None:
        # El comprador no paga el contenido entero del concentrado.
        assert venta_de_metal_en_concentrado(100.0, 30_000.0, 0.965) == pytest.approx(2_895_000.0)

    def test_un_factor_fuera_de_rango_es_error(self) -> None:
        with pytest.raises(ErrorVentas, match="factor de metal pagable"):
            venta_de_metal_en_concentrado(100.0, 30_000.0, 1.4)


class TestLiquidacionDelConcentrado:
    def test_la_plata_se_convierte_a_onzas_troy_y_el_cobre_no(self) -> None:
        liquidacion = concentrado_de_prueba()
        cobre, plata = liquidacion.metales
        assert cobre.valor_pagable == pytest.approx(0.25 * 9_000.0 * 1_000.0)
        assert plata.valor_pagable == pytest.approx(100.0 / GRAMOS_POR_ONZA_TROY * 30.0 * 1_000.0)

    def test_el_contenido_usa_toneladas_vendidas_y_los_cargos_las_netas(self) -> None:
        # Es la asimetria del libro: la merma descuenta cargos, no contenido.
        liquidacion = concentrado_de_prueba()
        assert liquidacion.toneladas_netas == pytest.approx(970.0)
        cobre, _ = liquidacion.metales
        assert cobre.cargo_de_refinacion == pytest.approx(50.0 * 970.0)
        assert liquidacion.maquila == pytest.approx(200.0 * 970.0)

    def test_el_valor_neto_descuenta_maquila_y_refinacion(self) -> None:
        liquidacion = concentrado_de_prueba()
        esperado = liquidacion.valor_pagable - liquidacion.cargos
        assert liquidacion.valor_neto == pytest.approx(esperado)

    def test_las_penalidades_no_entran_en_el_valor_neto(self) -> None:
        # Regla 010: el libro las calcula y las deja fuera de la venta.
        sin_penalidad = concentrado_de_prueba()
        con_penalidad = concentrado_de_prueba(penalidades=50_000.0)
        assert con_penalidad.valor_neto == pytest.approx(sin_penalidad.valor_neto)
        assert con_penalidad.total_con_penalidades == pytest.approx(
            sin_penalidad.valor_neto - 50_000.0
        )

    def test_una_merma_fuera_de_rango_es_error(self) -> None:
        with pytest.raises(ErrorVentas, match="merma"):
            concentrado_de_prueba(merma=1.2)

    def test_un_embarque_nulo_no_produce_valor(self) -> None:
        liquidacion = concentrado_de_prueba(toneladas_vendidas=0.0)
        assert liquidacion.valor_neto == 0.0


class TestVentaTotal:
    def test_suma_los_tres_caminos_de_ingreso(self) -> None:
        liquidacion = concentrado_de_prueba()
        total = venta_total(
            metal_refinado=1_000_000.0,
            metal_en_concentrado=500_000.0,
            concentrado=liquidacion,
            ajustes=25_000.0,
        )
        assert total == pytest.approx(1_525_000.0 + liquidacion.valor_neto)

    def test_un_caso_sin_polimetalico_no_necesita_liquidacion(self) -> None:
        assert venta_total(
            metal_refinado=1_000_000.0, metal_en_concentrado=0.0, concentrado=None
        ) == pytest.approx(1_000_000.0)


class TestCashCost:
    def test_suma_las_unidades_que_participan(self) -> None:
        unidades = [
            CostoDeUnidad("San Rafael", {"Mina": 100.0, "Planta": 50.0}),
            CostoDeUnidad("Nazareth", {"Mina": 70.0}),
        ]
        assert cash_cost_total(unidades) == pytest.approx(220.0)
        assert cash_cost_por_unidad(unidades) == {"San Rafael": 150.0, "Nazareth": 70.0}

    def test_una_unidad_repetida_es_error(self) -> None:
        unidades = [CostoDeUnidad("San Rafael", {"Mina": 1.0})] * 2
        with pytest.raises(ErrorCashCost, match="dos veces"):
            cash_cost_por_unidad(unidades)

    def test_un_costo_negativo_es_error(self) -> None:
        # El signo lo pone el flujo, no el costo.
        with pytest.raises(ErrorCashCost, match="se expresan en positivo"):
            CostoDeUnidad("San Rafael", {"Mina": -100.0})

    def test_el_unitario_con_cero_toneladas_da_cero(self) -> None:
        # Regla 008, confirmada por Finanzas el 01/09/2026.
        assert cash_cost_unitario(150.0, 0.0) == 0.0
        assert cash_cost_unitario(150.0, 3.0) == pytest.approx(50.0)

    def test_los_conceptos_adicionales_suman_sin_tocar_el_motor(self) -> None:
        # Acuerdo 6 de la minuta del 27/08/2026: la lista es abierta.
        base = {"Mina": 100.0, "Energia": 30.0}
        assert total_de_conceptos({**base, "Consultoria del proyecto": 20.0}) == pytest.approx(
            150.0
        )

    def test_gasto_de_ventas_y_flete_son_volumen_por_tarifa(self) -> None:
        assert gasto_de_ventas(1_200.0, 15.0) == pytest.approx(18_000.0)
        assert flete(1_200.0, 40.0) == pytest.approx(48_000.0)
