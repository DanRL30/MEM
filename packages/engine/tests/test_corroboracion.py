"""Pruebas del recálculo que audita los datos cargados por el usuario.

Las cifras salen del bloque `Cálculo Interno` del libro de producción de MINSUR:
1 000 t extraídas al 2 %, de las que 600 pasan por preconcentración al 1,2 % y
salen 300 t de preconcentrado al 2,4 %. De ahí el directo son 400 t y su ley
sale del balance metalúrgico; el tratado total, 700 t; y con 90 % de
recuperación y un concentrado al 40 % salen las toneladas finas y el concentrado.

Cada prueba fija las dos mitades de la señal: que una cadena coherente no reporta
nada, y que una cadena alterada reporta esa celda y solo esa. Comprobar solo la
primera dejaría pasar un corroborador que nunca encuentra nada, que es el modo de
fallo peor: el informe sale limpio y nadie revisa.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from minsur_engine.caso import (
    Caso,
    DatosComunes,
    DatosMaestros,
    MetalDelConcentrado,
    ProduccionDeUnidad,
    TerminosComerciales,
    TerminosDelConcentrado,
    UnidadProductiva,
    campos_con_dato,
)
from minsur_engine.corrida import Corrida, calcular
from minsur_engine.corroboracion import Discrepancia, corroborar, series_calculadas
from minsur_engine.depreciacion import TasasDeDepreciacion
from minsur_engine.horizonte import Horizonte
from minsur_engine.parametros import ParametrosCorporativos
from minsur_engine.tributos import EscalaProgresiva, Tramo
from minsur_engine.ventas import GRAMOS_POR_ONZA_TROY

MAESTROS = DatosMaestros(
    parametros=ParametrosCorporativos(
        version_datos_maestros="CP-PRUEBA",
        tasa_descuento=0.10,
        participacion_trabajadores=0.08,
        impuesto_renta=0.295,
        regalia_minima=0.01,
        osinergmin=0.0,
        oefa=0.0,
        fondo_jubilacion_minera=0.005,
    ),
    tasas_tributarias=TasasDeDepreciacion(maquinaria=0.5, instalaciones=0.1, edificaciones=0.05),
    tasas_financieras=TasasDeDepreciacion(maquinaria=0.5, instalaciones=0.1, edificaciones=0.05),
    escala_regalia=EscalaProgresiva(tramos=(Tramo(0.0, 10.0, 0.01),)),
    escala_iem=EscalaProgresiva(tramos=(Tramo(0.0, 10.0, 0.0),)),
)

HORIZONTE = Horizonte(primer_ano=2027, anos=2)

EXTRAIDO = 1_000.0
LEY_CABEZA = 0.02
PRECONC_TRATADO = 600.0
LEY_ENTRADA = 0.012
PRECONCENTRADO = 300.0
LEY_PRECONCENTRADO = 0.024

# Directo = 1 000 - 600 = 400. Su ley sale del balance: el fino que entra a la
# mina menos el que se va a preconcentracion, repartido sobre el directo.
DIRECTO = EXTRAIDO - PRECONC_TRATADO
LEY_DIRECTO = (EXTRAIDO * LEY_CABEZA - PRECONC_TRATADO * LEY_ENTRADA) / DIRECTO
TRATADO_TOTAL = DIRECTO + PRECONCENTRADO
LEY_TRATADO = (PRECONCENTRADO * LEY_PRECONCENTRADO + DIRECTO * LEY_DIRECTO) / TRATADO_TOTAL
RECUPERACION = 0.90
LEY_CONCENTRADO = 0.40
FINAS = TRATADO_TOTAL * LEY_TRATADO * RECUPERACION
CONCENTRADO = FINAS / LEY_CONCENTRADO


def _par(valor: float) -> tuple[float, ...]:
    return (valor, valor)


def _unidad(**cambios: tuple[float, ...]) -> UnidadProductiva:
    """La cadena completa y coherente, con los cambios que pida la prueba."""
    campos: dict[str, tuple[float, ...]] = {
        "mineral_extraido": _par(EXTRAIDO),
        "ley_de_cabeza": _par(LEY_CABEZA),
        "tratado_en_preconcentracion": _par(PRECONC_TRATADO),
        "ley_de_entrada": _par(LEY_ENTRADA),
        "preconcentrado": _par(PRECONCENTRADO),
        "ley_del_preconcentrado": _par(LEY_PRECONCENTRADO),
        "directo": _par(DIRECTO),
        "ley_del_directo": _par(LEY_DIRECTO),
        "tratado_total": _par(TRATADO_TOTAL),
        "ley_del_tratado_total": _par(LEY_TRATADO),
        "mineral_tratado": _par(EXTRAIDO),
        "ley_del_cash_cost": _par(LEY_CABEZA),
        "toneladas_finas": _par(FINAS),
        "ley_del_concentrado": _par(LEY_CONCENTRADO),
        "recuperacion": _par(RECUPERACION),
        "concentrado_producido": _par(CONCENTRADO),
    }
    campos.update(cambios)
    return UnidadProductiva(
        nombre="Proyecto X", tipo="mina", produccion=ProduccionDeUnidad(**campos)
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


# --- Bloque comercial ---------------------------------------------------------
#
# El concentrado de cobre de la unidad al 20 %, con una deduccion minima de un
# punto y un factor pagable del 90 %: la ley pagable la fija el factor, 0,18. La
# tarifa del cobre son dos centavos por libra y la de la plata, sesenta centavos
# por onza troy sobre una ley pagable de 100 g/t.

LEY_CU = 0.20
DEDUCCION_CU = 0.01
FACTOR_CU = 0.90
LEY_PAGABLE_CU = LEY_CU * FACTOR_CU
TARIFA_CU = 0.02
LEY_PAGABLE_AG = 100.0
TARIFA_AG = 0.60


def _unidad_polimetalica(**declaradas: tuple[float, ...]) -> UnidadProductiva:
    """La misma unidad, con concentrado de cobre y su bloque comercial cuadrado."""
    base = _unidad()
    return replace(
        base,
        produccion=replace(
            base.produccion,
            concentrado_de_cu=_par(500.0),
            ley_cu=declaradas.get("ley_cu", _par(LEY_CU)),
        ),
        ley_pagable_declarada={
            "Cu": declaradas.get("ley_pagable_cu", _par(LEY_PAGABLE_CU)),
            "Ag": declaradas.get("ley_pagable_ag", _par(LEY_PAGABLE_AG)),
        },
        refinacion_declarada={
            "Ag": declaradas.get(
                "refinacion_ag", _par(LEY_PAGABLE_AG / GRAMOS_POR_ONZA_TROY * TARIFA_AG)
            ),
        },
    )


def _caso_polimetalico(unidad: UnidadProductiva) -> Caso:
    ceros = HORIZONTE.ceros()
    return Caso(
        nombre="Caso polimetalico",
        horizonte=HORIZONTE,
        unidades=(unidad,),
        terminos=TerminosComerciales(
            precio_metal_refinado=ceros,
            premio_metal_refinado=ceros,
            precio_metal_en_concentrado=ceros,
            factor_metal_pagable=ceros,
            concentrado=TerminosDelConcentrado(
                merma=_par(0.05),
                maquila_por_tonelada=_par(100.0),
                metales=(
                    MetalDelConcentrado(
                        nombre="Cu",
                        ley_pagable=(),
                        precio=_par(9_000.0),
                        cargo_de_refinacion=(),
                        deduccion_minima=_par(DEDUCCION_CU),
                        factor_pagable=_par(FACTOR_CU),
                        tarifa_de_refinacion=_par(TARIFA_CU),
                    ),
                    MetalDelConcentrado(
                        nombre="Ag",
                        ley_pagable=(),
                        precio=_par(30.0),
                        cargo_de_refinacion=(),
                        en_onzas_troy=True,
                        tarifa_de_refinacion=_par(TARIFA_AG),
                    ),
                ),
            ),
        ),
        datos_comunes=DatosComunes(gastos_administrativos=ceros),
    )


class TestElBloqueComercial:
    """Las tres filas que el libro presenta como supuesto y son calculo.

    La hoja `Supuestos` declara la ley pagable y los dos cargos de refinacion
    como si fueran datos. Salen de una formula, y aqui se rehacen igual que las
    ocho de produccion: se avisa y no se corrige.
    """

    def test_un_bloque_comercial_que_cuadra_no_reporta_nada(self) -> None:
        assert corroborar(_caso_polimetalico(_unidad_polimetalica())) == ()

    def test_una_ley_pagable_de_cobre_alterada_se_reporta(self) -> None:
        # Regla 023: sale de la ley del concentrado, su deduccion y su factor.
        unidad = _unidad_polimetalica(ley_pagable_cu=_par(LEY_PAGABLE_CU * 2))
        assert conceptos(corroborar(_caso_polimetalico(unidad))) == {"Ley Pagable Cu"}

    def test_el_cargo_de_la_plata_sigue_a_su_ley_pagable(self) -> None:
        # Regla 022: no es un dato, se deriva de la ley pagable de esa unidad.
        unidad = _unidad_polimetalica(refinacion_ag=_par(5.0))
        assert conceptos(corroborar(_caso_polimetalico(unidad))) == {"Refinacion Ag"}

    def test_la_ley_pagable_de_la_plata_no_se_corrobora(self) -> None:
        # Regla 045: la formula del libro le aplica un factor cien sobre una ley
        # en onzas por tonelada. Sin respuesta de Finanzas no hay contra que
        # compararla, y una alarma inventada seria peor que ninguna.
        unidad = _unidad_polimetalica(ley_pagable_ag=_par(LEY_PAGABLE_AG * 3))
        assert "Ley Pagable Ag" not in conceptos(corroborar(_caso_polimetalico(unidad)))

    def test_una_unidad_sin_concentrado_no_reporta_nada_comercial(self) -> None:
        # La estructura es la misma para todos: un caso de solo estano no tiene
        # ley pagable que corroborar y callar es lo correcto.
        assert conceptos(corroborar(_caso_polimetalico(_unidad()))) == set()

    def test_el_dato_comercial_cargado_es_el_que_liquida(self) -> None:
        # La otra mitad de la propiedad: el aviso no cambia la cifra. La ley
        # pagable alterada mueve la venta **como mueve el dato**, no como dice
        # el recalculo.
        cargada = calcular(
            _caso_polimetalico(_unidad_polimetalica(ley_pagable_cu=_par(LEY_PAGABLE_CU * 2))),
            MAESTROS,
        )
        coherente = calcular(_caso_polimetalico(_unidad_polimetalica()), MAESTROS)
        cobre_de_mas = LEY_PAGABLE_CU * 9_000.0 * 500.0
        assert cargada.ventas[0] - coherente.ventas[0] == pytest.approx(cobre_de_mas)
        assert cargada.discrepancias != ()


class TestCadenaCoherente:
    def test_una_cadena_que_cuadra_no_reporta_nada(self) -> None:
        assert corroborar(_caso(_unidad())) == ()

    def test_una_unidad_sin_preconcentracion_tambien_cuadra(self) -> None:
        # La estructura es la misma para todos: un proyecto sin preconcentracion
        # deja esas filas en cero y el directo pasa a ser todo lo extraido.
        finas = EXTRAIDO * LEY_CABEZA * RECUPERACION
        unidad = _unidad(
            tratado_en_preconcentracion=_par(0.0),
            ley_de_entrada=_par(0.0),
            preconcentrado=_par(0.0),
            ley_del_preconcentrado=_par(0.0),
            directo=_par(EXTRAIDO),
            ley_del_directo=_par(LEY_CABEZA),
            tratado_total=_par(EXTRAIDO),
            ley_del_tratado_total=_par(LEY_CABEZA),
            toneladas_finas=_par(finas),
            concentrado_producido=_par(finas / LEY_CONCENTRADO),
        )
        assert corroborar(_caso(unidad)) == ()

    def test_una_fila_calculada_vacia_no_reporta_nada(self) -> None:
        # Una serie que no se lleno no es un error: significa que el concepto no
        # aplica. Tratarla como cero llenaria el informe de falsos positivos.
        assert corroborar(_caso(_unidad(toneladas_finas=()))) == ()


class TestLasOchoReglas:
    def test_el_directo_es_lo_extraido_menos_lo_preconcentrado(self) -> None:
        halladas = corroborar(_caso(_unidad(directo=_par(500.0))))
        assert "Mineral Directo a Planta Concentradora" in conceptos(halladas)
        assert halladas[0].recalculado == pytest.approx(400.0)

    def test_la_ley_del_directo_sale_del_balance_metalurgico(self) -> None:
        halladas = corroborar(_caso(_unidad(ley_del_directo=_par(0.02))))
        assert "Ley de Sn del mineral directo" in conceptos(halladas)
        # 1 000 x 2 % son 20 t de fino; 600 x 1,2 % son 7,2. Quedan 12,8 sobre
        # 400 toneladas, que son 3,2 %.
        recalculado = next(d.recalculado for d in halladas if d.concepto.startswith("Ley de Sn"))
        assert recalculado == pytest.approx(0.032)

    def test_el_tratado_total_es_directo_mas_preconcentrado(self) -> None:
        halladas = corroborar(_caso(_unidad(tratado_total=_par(800.0))))
        assert "Mineral Tratado Total en Concentradora" in conceptos(halladas)

    def test_la_ley_del_tratado_se_pondera_por_tonelaje(self) -> None:
        # El error clasico: promediar 2,4 % y 3,2 % da 2,8 %; ponderar por 300 y
        # 400 toneladas da 2,857 %. El libro usa SUMPRODUCT.
        halladas = corroborar(_caso(_unidad(ley_del_tratado_total=_par(0.028))))
        assert "Ley Sn del tratado total" in conceptos(halladas)

    def test_el_tratado_para_cash_cost_es_lo_extraido(self) -> None:
        halladas = corroborar(_caso(_unidad(mineral_tratado=_par(700.0))))
        assert "Mineral Tratado Total (Cash Cost)" in conceptos(halladas)
        assert halladas[0].recalculado == pytest.approx(EXTRAIDO)

    def test_la_ley_del_cash_cost_es_la_de_cabeza(self) -> None:
        halladas = corroborar(_caso(_unidad(ley_del_cash_cost=_par(0.03))))
        assert "Ley Sn del cash cost" in conceptos(halladas)

    def test_las_finas_llevan_la_recuperacion(self) -> None:
        # Sin el factor de recuperacion darian 20 t en vez de 18.
        halladas = corroborar(_caso(_unidad(toneladas_finas=_par(TRATADO_TOTAL * LEY_TRATADO))))
        assert "Toneladas finas" in conceptos(halladas)
        assert halladas[0].recalculado == pytest.approx(FINAS)

    def test_el_concentrado_es_las_finas_entre_su_ley(self) -> None:
        # Y no las finas por la recuperacion otra vez: ya viene aplicada.
        halladas = corroborar(_caso(_unidad(concentrado_producido=_par(CONCENTRADO * 0.9))))
        assert "Produccion Concentrado" in conceptos(halladas)
        assert halladas[0].recalculado == pytest.approx(CONCENTRADO)


class TestTolerancia:
    def test_una_diferencia_bajo_la_tolerancia_no_se_reporta(self) -> None:
        assert corroborar(_caso(_unidad(directo=_par(400.4)))) == ()

    def test_la_tolerancia_es_configurable(self) -> None:
        assert corroborar(_caso(_unidad(directo=_par(400.4))), tolerancia=0.0001) != ()

    def test_la_discrepancia_dice_cuanto_se_desvia(self) -> None:
        hallada = corroborar(_caso(_unidad(directo=_par(500.0))))[0]
        assert hallada.diferencia == pytest.approx(100.0)
        assert hallada.diferencia_relativa == pytest.approx(0.2)
        assert hallada.ano == 2027


class TestDivisionPorCero:
    def test_un_denominador_nulo_devuelve_cero_y_no_falla(self) -> None:
        # El libro envuelve estas divisiones en IFERROR y Finanzas confirmo que
        # cero es el resultado esperado: una indeterminacion no detiene la
        # corrida.
        unidad = _unidad(
            mineral_extraido=_par(0.0),
            tratado_en_preconcentracion=_par(0.0),
            preconcentrado=_par(0.0),
            ley_del_concentrado=_par(0.0),
        )
        assert corroborar(_caso(unidad)) != ()


class TestSeriesCalculadas:
    def test_devuelve_lo_que_el_sistema_esperaba(self) -> None:
        # Es la vista que la plataforma pone al lado del dato cargado: sin el
        # valor recalculado, la alarma no dice que esperaba.
        calculadas = series_calculadas(_unidad().produccion, HORIZONTE.anos)
        assert calculadas["directo"] == [DIRECTO, DIRECTO]
        assert calculadas["toneladas_finas"][0] == pytest.approx(FINAS)
        assert calculadas["concentrado_producido"][0] == pytest.approx(CONCENTRADO)


class TestElDatoDelUsuarioEsElQueManda:
    """La propiedad que sostiene todo el diseño, y que es fácil romper.

    El recálculo **audita** el dato cargado; no lo sustituye. Si un día alguien
    decidiera "arreglar" una serie incoherente con su valor recalculado, el
    motor dejaría de reproducir lo que el usuario cargó y el contraste de
    fidelidad perdería sentido: estaría comparando contra un dato que la
    plataforma se inventó.

    Estas pruebas alteran una fila corroborable y comprueban que **el flujo
    sigue el valor cargado**, no el que el sistema esperaba.
    """

    def _corrida(self, **cambios: tuple[float, ...]) -> Corrida:
        return calcular(_caso(_unidad(**cambios)), MAESTROS)

    def test_la_refineria_recibe_lo_que_la_mina_declara_aunque_no_cuadre(self) -> None:
        # El concentrado cargado es el doble del que sale de la cadena. La
        # refineria debe recibir el cargado, y la corrida debe avisar.
        alterado = self._corrida(concentrado_producido=_par(CONCENTRADO * 2))
        assert alterado.refineria.concentrado_entregado[0] == pytest.approx(CONCENTRADO * 2)
        assert "Produccion Concentrado" in {d.concepto for d in alterado.discrepancias}

        coherente = self._corrida()
        assert coherente.refineria.concentrado_entregado[0] == pytest.approx(CONCENTRADO)
        assert coherente.discrepancias == ()

    def test_el_cash_cost_usa_el_tonelaje_cargado(self) -> None:
        # `Mineral Tratado Total (Cash Cost)` es corroborable: el sistema espera
        # el mineral extraido. Cargar otro no cambia lo que el motor usa.
        alterado = self._corrida(mineral_tratado=_par(EXTRAIDO / 2))
        assert alterado.mineral_tratado_por_unidad["Proyecto X"][0] == pytest.approx(EXTRAIDO / 2)
        assert "Mineral Tratado Total (Cash Cost)" in {d.concepto for d in alterado.discrepancias}

    def test_advertir_no_cambia_ninguna_cifra_del_resultado(self) -> None:
        # `Ley Sn del cash cost` la lee el corroborador y nadie mas: no alimenta
        # ninguna linea del flujo. Alterarla tiene que producir un aviso y dejar
        # el resultado intacto hasta el ultimo decimal. Si algun dia una cifra
        # cambiara aqui, seria porque el recalculo se colo en el calculo.
        sin_aviso = self._corrida()
        con_aviso = self._corrida(ley_del_cash_cost=_par(LEY_CABEZA * 2))

        assert sin_aviso.discrepancias == ()
        assert [d.concepto for d in con_aviso.discrepancias] == ["Ley Sn del cash cost"] * 2

        assert con_aviso.ventas == sin_aviso.ventas
        assert con_aviso.cash_cost == sin_aviso.cash_cost
        assert con_aviso.refineria.concentrado_entregado == (
            sin_aviso.refineria.concentrado_entregado
        )
        assert con_aviso.flujo.flujo_economico == sin_aviso.flujo.flujo_economico
        assert con_aviso.indicadores.npv == sin_aviso.indicadores.npv


class TestFilasQueNoAplican:
    """Una fila entera en cero no se muestra: el concepto no aplica.

    Es lo que ocurre con el cobre y la plata en un caso de solo estaño. La
    plantilla los trae porque la estructura es la misma para todos los
    proyectos, y la pantalla los oculta porque en ese caso no significan nada.
    """

    def test_el_cobre_y_la_plata_no_aparecen_en_un_caso_de_estano(self) -> None:
        con_dato = campos_con_dato(_unidad().produccion)
        assert "concentrado_de_cu" not in con_dato
        assert "ley_cu" not in con_dato
        assert "ley_ag" not in con_dato

    def test_lo_que_si_se_llena_aparece(self) -> None:
        con_dato = campos_con_dato(_unidad().produccion)
        assert {"mineral_extraido", "ley_de_cabeza", "concentrado_producido"} <= con_dato

    def test_una_serie_vacia_y_una_de_ceros_dicen_lo_mismo(self) -> None:
        # Distinguirlas obligaria al usuario a saber cual de las dos escribio.
        vacia = campos_con_dato(_unidad(toneladas_finas=()).produccion)
        en_cero = campos_con_dato(_unidad(toneladas_finas=(0.0, 0.0)).produccion)
        assert "toneladas_finas" not in vacia
        assert "toneladas_finas" not in en_cero

    def test_una_unidad_polimetalica_si_los_muestra(self) -> None:
        con_dato = campos_con_dato(
            _unidad(concentrado_de_cu=_par(1_800.0), ley_cu=_par(0.25)).produccion
        )
        assert {"concentrado_de_cu", "ley_cu"} <= con_dato
        assert "ley_ag" not in con_dato

    def test_la_corrida_lo_dice_por_unidad(self) -> None:
        # La API y la interfaz lo toman de aqui, no lo deciden cada una.
        corrida = calcular(_caso(_unidad()), MAESTROS)
        assert "ley_cu" not in corrida.campos_con_dato_por_unidad["Proyecto X"]
        assert "mineral_extraido" in corrida.campos_con_dato_por_unidad["Proyecto X"]
