"""Pruebas del recálculo que audita los datos cargados por el usuario.

Cada prueba fija una de las dos mitades de la señal: que una cadena coherente no
reporta nada, y que una cadena alterada reporta esa celda y solo esa. Comprobar
únicamente la primera dejaría pasar un corroborador que nunca encuentra nada, que
es el modo de fallo peor: el informe sale limpio y nadie revisa.
"""

from __future__ import annotations

import pytest

from minsur_engine.caso import (
    Caso,
    ConcentradoDeMetal,
    CorrienteDeMineral,
    DatosComunes,
    ProduccionDeUnidad,
    TerminosComerciales,
    UnidadProductiva,
)
from minsur_engine.corroboracion import Discrepancia, corroborar
from minsur_engine.horizonte import Horizonte

HORIZONTE = Horizonte(primer_ano=2027, anos=3)


def _mina(
    *,
    preconcentrado: tuple[float, ...] = (400.0, 400.0, 400.0),
    directo: tuple[float, ...] = (600.0, 600.0, 600.0),
    tratado_total: tuple[float, ...] = (1_000.0, 1_000.0, 1_000.0),
    ley_preconcentrado: tuple[float, ...] = (0.02, 0.02, 0.02),
    ley_directo: tuple[float, ...] = (0.01, 0.01, 0.01),
    ley_total: tuple[float, ...] = (0.014, 0.014, 0.014),
    finas: tuple[float, ...] = (14.0, 14.0, 14.0),
    concentrado: tuple[float, ...] = (28.0, 28.0, 28.0),
) -> UnidadProductiva:
    """Una mina coherente de punta a punta.

    Los números se eligen para poder seguirlos a mano: 400 t al 2 % y 600 t al
    1 % dan 1 000 t al 1,4 %, que son 14 tmf; con 80 % de recuperación y un
    concentrado al 40 %, salen 28 t de concentrado.
    """
    serie = HORIZONTE.serie
    return UnidadProductiva(
        nombre="Mina Norte",
        tipo="mina",
        etapas=("preconcentracion", "concentradora"),
        produccion=ProduccionDeUnidad(
            mineral_tratado=serie(tratado_total, nombre="tratado"),
            concentrado_producido=serie(concentrado, nombre="concentrado"),
            preconcentrado_a_concentradora=CorrienteDeMineral(
                toneladas=serie(preconcentrado, nombre="preconcentrado"),
                leyes={"Sn": serie(ley_preconcentrado, nombre="ley preconcentrado")},
            ),
            directo_a_concentradora=CorrienteDeMineral(
                toneladas=serie(directo, nombre="directo"),
                leyes={"Sn": serie(ley_directo, nombre="ley directo")},
            ),
            tratado_total=CorrienteDeMineral(
                toneladas=serie(tratado_total, nombre="tratado total"),
                leyes={"Sn": serie(ley_total, nombre="ley total")},
            ),
            leyes_del_tratado={"Sn": serie(ley_total, nombre="ley cash cost")},
            concentrados={
                "Sn": ConcentradoDeMetal(
                    toneladas=serie(concentrado, nombre="concentrado Sn"),
                    ley=serie((0.40, 0.40, 0.40), nombre="ley del concentrado"),
                    recuperacion=serie((0.80, 0.80, 0.80), nombre="recuperacion"),
                    toneladas_finas=serie(finas, nombre="finas"),
                )
            },
        ),
    )


def _caso(*unidades: UnidadProductiva) -> Caso:
    ceros = HORIZONTE.ceros()
    return Caso(
        nombre="Caso de prueba",
        horizonte=HORIZONTE,
        unidades=unidades,
        terminos=TerminosComerciales(
            precio_metal_refinado=ceros,
            premio_metal_refinado=ceros,
            precio_metal_en_concentrado=ceros,
            factor_metal_pagable=ceros,
        ),
        datos_comunes=DatosComunes(gastos_administrativos=ceros),
    )


def conceptos(halladas: tuple[Discrepancia, ...]) -> set[str]:
    return {d.concepto for d in halladas}


class TestCadenaCoherente:
    def test_una_cadena_que_cuadra_no_reporta_nada(self) -> None:
        assert corroborar(_caso(_mina())) == ()

    def test_una_unidad_que_no_declara_la_cadena_no_reporta_nada(self) -> None:
        # Una serie ausente significa que el concepto no aplica, no que valga
        # cero. Tratarla como cero llenaria el informe de falsos positivos.
        unidad = UnidadProductiva(
            nombre="Mina Simple",
            tipo="mina",
            produccion=ProduccionDeUnidad(
                mineral_tratado=HORIZONTE.serie((1_000.0, 1_000.0, 1_000.0), nombre="tratado"),
                concentrado_producido=HORIZONTE.ceros(),
            ),
        )
        assert corroborar(_caso(unidad)) == ()


class TestCadenaAlterada:
    def test_el_tratado_total_que_no_es_la_suma_se_reporta(self) -> None:
        halladas = corroborar(_caso(_mina(tratado_total=(1_000.0, 1_200.0, 1_000.0))))
        assert "Mineral tratado total en concentradora" in conceptos(halladas)
        del_tratado = [d for d in halladas if d.concepto.startswith("Mineral tratado")]
        assert [d.ano for d in del_tratado] == [2028]
        assert del_tratado[0].cargado == 1_200.0
        assert del_tratado[0].recalculado == 1_000.0

    def test_la_ley_promediada_en_vez_de_ponderada_se_reporta(self) -> None:
        # El error clasico: 2 % y 1 % promediados dan 1,5 %; ponderados por
        # 400 y 600 toneladas dan 1,4 %. El libro usa SUMPRODUCT.
        halladas = corroborar(_caso(_mina(ley_total=(0.015, 0.015, 0.015))))
        assert "Ley de Sn del tratado total" in conceptos(halladas)
        leyes = [d for d in halladas if d.concepto.startswith("Ley de Sn")]
        assert len(leyes) == 3
        assert leyes[0].recalculado == pytest.approx(0.014)

    def test_las_finas_que_no_salen_de_tratado_por_ley_se_reportan(self) -> None:
        halladas = corroborar(_caso(_mina(finas=(14.0, 20.0, 14.0))))
        assert "Toneladas finas de Sn" in conceptos(halladas)

    def test_el_concentrado_que_no_sale_de_finas_y_recuperacion_se_reporta(self) -> None:
        halladas = corroborar(_caso(_mina(concentrado=(28.0, 28.0, 35.0))))
        assert "Produccion de concentrado de Sn" in conceptos(halladas)

    def test_la_discrepancia_dice_cuanto_se_desvia(self) -> None:
        halladas = corroborar(_caso(_mina(tratado_total=(1_000.0, 1_100.0, 1_000.0))))
        del_tratado = next(d for d in halladas if d.concepto.startswith("Mineral tratado"))
        assert del_tratado.diferencia == pytest.approx(100.0)
        assert del_tratado.diferencia_relativa == pytest.approx(100.0 / 1_100.0)


class TestTolerancia:
    def test_una_diferencia_bajo_la_tolerancia_no_se_reporta(self) -> None:
        # Una milesima sobre 1 000 toneladas es ruido de redondeo del Excel,
        # no un error de carga.
        assert corroborar(_caso(_mina(tratado_total=(1_000.0, 1_001.0, 1_000.0)))) == ()

    def test_la_tolerancia_es_configurable(self) -> None:
        caso = _caso(_mina(tratado_total=(1_000.0, 1_001.0, 1_000.0)))
        assert corroborar(caso, tolerancia=0.0001) != ()


class TestComplejo:
    def test_lo_que_el_complejo_dice_recibir_es_lo_que_la_mina_entrega(self) -> None:
        mina = _mina()
        fundicion = UnidadProductiva(
            nombre="Fundicion",
            tipo="fundicion",
            produccion=ProduccionDeUnidad(
                mineral_tratado=HORIZONTE.ceros(),
                concentrado_producido=HORIZONTE.ceros(),
                alimentacion_recibida={
                    "Mina Norte": CorrienteDeMineral(
                        toneladas=HORIZONTE.serie((28.0, 28.0, 28.0), nombre="alimentado")
                    )
                },
            ),
        )
        assert corroborar(_caso(mina, fundicion)) == ()

    def test_una_alimentacion_que_no_cuadra_con_el_origen_se_reporta(self) -> None:
        mina = _mina()
        fundicion = UnidadProductiva(
            nombre="Fundicion",
            tipo="fundicion",
            produccion=ProduccionDeUnidad(
                mineral_tratado=HORIZONTE.ceros(),
                concentrado_producido=HORIZONTE.ceros(),
                alimentacion_recibida={
                    "Mina Norte": CorrienteDeMineral(
                        toneladas=HORIZONTE.serie((28.0, 40.0, 28.0), nombre="alimentado")
                    )
                },
            ),
        )
        halladas = corroborar(_caso(mina, fundicion))
        assert "Concentrado alimentado desde Mina Norte" in conceptos(halladas)
