"""Pruebas de la hoja `Otros`: bandas de egreso, bolsa y ranura reservada.

Las cifras son sintéticas y elegidas para que la aritmética se siga a mano. Lo
que se verifica no son los valores del modelo, que son confidenciales, sino las
reglas de la hoja: con qué signo se escribe cada banda, qué suma cada total, y
a cuál de los dos bloques va la regalía según el resultado del ejercicio.

El bloque tributario llega sintético a propósito. Llevar `impuestos.calcular` a
una utilidad operativa **exactamente cero** exigiría cuadrar ventas, costos y
aportes reguladores al céntimo, y lo que se prueba aquí no es esa aritmética
sino qué hace la hoja `Otros` con el número que recibe.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

import pytest

from minsur_engine.capital_trabajo import BloqueDeIgv, SaldosDeCapitalTrabajo
from minsur_engine.horizonte import Horizonte, Serie
from minsur_engine.impuestos import (
    BloqueDeImpuestoALaRenta,
    BloqueDeImpuestos,
    BloqueDePerdidaTributaria,
    BloqueDeRegalias,
    BloqueDeRenta,
)
from minsur_engine.otros import BolsaDeEgresos, ErrorHojaOtros, bolsa_de_egresos, calcular

ANOS = 3
CEROS: Serie = (0.0,) * ANOS


@pytest.fixture
def horizonte() -> Horizonte:
    return Horizonte(primer_ano=2027, anos=ANOS)


def _lleno(clase: type, **valores: Any) -> Any:
    """Un sub-bloque tributario con ceros salvo en las filas que la hoja lee.

    Se rellena por reflexión y no campo a campo: `BloqueDeRenta` tiene
    veinticuatro filas y la hoja `Otros` lee cuatro. Enumerarlas todas ataría
    esta prueba a la forma de otra hoja.
    """
    return clase(**{campo.name: valores.get(campo.name, CEROS) for campo in fields(clase)})


def tributario(
    *,
    utilidad_operativa: Serie,
    regalia_mayor: Serie = CEROS,
    impuesto_especial: Serie = CEROS,
    impuesto_a_la_renta: Serie = CEROS,
    osinergmin: Serie = CEROS,
    oefa: Serie = CEROS,
    fondo_de_jubilacion: Serie = CEROS,
) -> BloqueDeImpuestos:
    return BloqueDeImpuestos(
        regalias=_lleno(
            BloqueDeRegalias,
            utilidad_operativa=utilidad_operativa,
            regalia_mayor=regalia_mayor,
            impuesto_especial=impuesto_especial,
            osinergmin=osinergmin,
            oefa=oefa,
            fondo_de_jubilacion=fondo_de_jubilacion,
        ),
        renta=_lleno(BloqueDeRenta),
        impuesto_a_la_renta=_lleno(
            BloqueDeImpuestoALaRenta, impuesto_a_la_renta=impuesto_a_la_renta
        ),
        perdida_tributaria=_lleno(BloqueDePerdidaTributaria),
        tramos_de_regalia=(),
        tramos_de_iem=(),
        por_ano=(),
    )


def sin_movimiento(horizonte: Horizonte) -> BolsaDeEgresos:
    return bolsa_de_egresos(
        horizonte,
        opex=CEROS,
        gastos_administrativos=CEROS,
        fletes=CEROS,
        gasto_de_ventas=CEROS,
        donaciones=CEROS,
        otros_egresos=CEROS,
        servidumbre=CEROS,
        estudios=CEROS,
        planilla=CEROS,
        capex=CEROS,
        exploraciones=CEROS,
    )


def hoja(horizonte: Horizonte, **cambios: Any) -> Any:
    """La hoja `Otros` de un caso en blanco, con lo que la prueba declare."""
    vacio = SaldosDeCapitalTrabajo(saldos=CEROS, variaciones=CEROS)
    base: dict[str, Any] = {
        "cash_cost_por_unidad": {},
        "cash_cost": CEROS,
        "gasto_de_ventas_lom": CEROS,
        "gasto_de_ventas_sobre_concentrado": CEROS,
        "fletes_lom": CEROS,
        "fletes_sobre_concentrado": CEROS,
        "donaciones": CEROS,
        "servidumbre_del_flujo": CEROS,
        "otros_gastos": CEROS,
        "impuestos": tributario(utilidad_operativa=CEROS),
        "compras": sin_movimiento(horizonte),
        "igv": _lleno(BloqueDeIgv),
        "por_cobrar": vacio,
        "por_pagar": vacio,
        "dias_por_cobrar": CEROS,
        "dias_por_pagar": CEROS,
        "dias_del_ano_comercial": 360.0,
        "otras_por_cobrar": CEROS,
        "otras_por_pagar": CEROS,
        "variacion": CEROS,
        "porcentaje_de_ventas_de_exportacion": 1.0,
        "porcentaje_de_compras_locales": 1.0,
        "produce": (True,) * ANOS,
        "predios": CEROS,
    }
    base.update(cambios)
    return calcular(horizonte, **base)


class TestLaRegaliaSeParte:
    """`Otros!33` y `!37`: la misma regalía repartida por el signo del resultado.

    Es la regla `080`. El libro la escribe con dos condiciones estrictas, de modo
    que hay un ejercicio -el de utilidad operativa nula- en que la regalía no
    aparece en ninguno de los dos bloques.
    """

    @pytest.fixture
    def partida(self, horizonte: Horizonte) -> Any:
        # Un ejercicio en perdida, uno en ganancia y uno en tablas, con la misma
        # regalia en los tres: es lo unico que separa las dos filas del libro.
        return hoja(
            horizonte,
            impuestos=tributario(
                utilidad_operativa=(-500.0, 500.0, 0.0),
                regalia_mayor=(100.0, 100.0, 100.0),
            ),
        )

    def test_va_a_otros_gastos_cuando_la_utilidad_es_negativa(self, partida: Any) -> None:
        assert partida.otros_gastos.regalia == pytest.approx((-100.0, 0.0, 0.0))

    def test_va_a_los_tributos_cuando_la_utilidad_es_positiva(self, partida: Any) -> None:
        assert partida.pago_de_impuestos.regalia == pytest.approx((0.0, -100.0, 0.0))

    def test_con_utilidad_cero_no_la_recoge_ninguna(self, partida: Any) -> None:
        # No es un descuido de esta prueba: las dos condiciones del libro son
        # `<0` y `>0`, y el ejercicio en tablas se cae entre las dos. Se
        # reproduce y se reporta; si alguien lo «arregla», falla aqui.
        assert partida.otros_gastos.regalia[2] == 0.0
        assert partida.pago_de_impuestos.regalia[2] == 0.0

    def test_entre_las_dos_no_inventan_ni_pierden_regalia(self, partida: Any) -> None:
        for i, esperado in enumerate((-100.0, -100.0, 0.0)):
            suma = partida.otros_gastos.regalia[i] + partida.pago_de_impuestos.regalia[i]
            assert suma == pytest.approx(esperado)


class TestElSignoDelLibro:
    """Las bandas 6 a 41 van en signo de caja y la bolsa en positivo.

    Es lo que hace que cada total sea literalmente la suma de las filas que tiene
    encima, y es lo que se contrasta contra el libro.
    """

    def test_las_bandas_de_egreso_salen_negadas(self, horizonte: Horizonte) -> None:
        bloque = hoja(
            horizonte,
            cash_cost=(300.0,) * ANOS,
            cash_cost_por_unidad={"Mina": (300.0,) * ANOS},
            fletes_lom=(10.0,) * ANOS,
            fletes_sobre_concentrado=(20.0,) * ANOS,
            gasto_de_ventas_lom=(5.0,) * ANOS,
            gasto_de_ventas_sobre_concentrado=(15.0,) * ANOS,
            donaciones=(7.0,) * ANOS,
            servidumbre_del_flujo=(3.0,) * ANOS,
            otros_gastos=(1.0,) * ANOS,
            predios=(9.0,) * ANOS,
        )

        assert bloque.cash_cost == pytest.approx((-300.0,) * ANOS)
        assert bloque.cash_cost_por_unidad["Mina"] == pytest.approx((-300.0,) * ANOS)
        assert bloque.fletes.total == pytest.approx((-30.0,) * ANOS)
        assert bloque.gasto_de_ventas.total == pytest.approx((-20.0,) * ANOS)
        assert bloque.otros_gastos.total == pytest.approx((-11.0,) * ANOS)
        assert bloque.predios == pytest.approx((-9.0,) * ANOS)

    def test_los_reguladores_llegan_negados_y_no_se_vuelven_a_negar(
        self, horizonte: Horizonte
    ) -> None:
        # `Otros!31` es un `SUM` sin signo delante: las tres filas de `Impuestos`
        # ya vienen negadas de su bloque. Negarlas otra vez convertiria un gasto
        # en un ingreso sin que el total lo acusara.
        bloque = hoja(
            horizonte,
            impuestos=tributario(
                utilidad_operativa=CEROS,
                osinergmin=(-2.0,) * ANOS,
                oefa=(-1.0,) * ANOS,
                fondo_de_jubilacion=(-4.0,) * ANOS,
            ),
        )

        assert bloque.otros_gastos.reguladores_y_fondo == pytest.approx((-7.0,) * ANOS)

    def test_la_bolsa_sale_en_positivo(self, horizonte: Horizonte) -> None:
        compras = bolsa_de_egresos(
            horizonte,
            opex=(300.0,) * ANOS,
            gastos_administrativos=(50.0,) * ANOS,
            fletes=(30.0,) * ANOS,
            gasto_de_ventas=(20.0,) * ANOS,
            donaciones=CEROS,
            otros_egresos=CEROS,
            servidumbre=CEROS,
            estudios=CEROS,
            planilla=CEROS,
            capex=CEROS,
            exploraciones=CEROS,
        )

        assert compras.bolsa == pytest.approx((400.0,) * ANOS)


class TestLaBolsaDeEgresos:
    """`Otros!43-55`, la base de las cuentas por pagar y del IGV de compras."""

    @pytest.fixture
    def compras(self, horizonte: Horizonte) -> BolsaDeEgresos:
        return bolsa_de_egresos(
            horizonte,
            opex=(1.0,) * ANOS,
            gastos_administrativos=(2.0,) * ANOS,
            fletes=(4.0,) * ANOS,
            gasto_de_ventas=(8.0,) * ANOS,
            donaciones=(16.0,) * ANOS,
            otros_egresos=(32.0,) * ANOS,
            servidumbre=(64.0,) * ANOS,
            estudios=(128.0,) * ANOS,
            planilla=(256.0,) * ANOS,
            capex=(512.0,) * ANOS,
            exploraciones=(1_024.0,) * ANOS,
        )

    def test_lleva_los_once_conceptos_del_libro_en_su_orden(self, compras: BolsaDeEgresos) -> None:
        # Las potencias de dos hacen que la suma identifique el conjunto: si un
        # concepto entra de mas o de menos, el total dice cual.
        assert len(compras.conceptos) == 11
        assert [serie[0] for serie in compras.conceptos] == [
            1.0,
            2.0,
            4.0,
            8.0,
            16.0,
            32.0,
            64.0,
            128.0,
            256.0,
            512.0,
            1_024.0,
        ]

    def test_es_la_suma_de_sus_once_conceptos(self, compras: BolsaDeEgresos) -> None:
        assert compras.bolsa == pytest.approx((2_047.0,) * ANOS)

    def test_no_admite_una_serie_de_otro_largo(self, horizonte: Horizonte) -> None:
        with pytest.raises(ErrorHojaOtros, match="3 anos"):
            bolsa_de_egresos(
                horizonte,
                opex=(1.0, 2.0),
                gastos_administrativos=CEROS,
                fletes=CEROS,
                gasto_de_ventas=CEROS,
                donaciones=CEROS,
                otros_egresos=CEROS,
                servidumbre=CEROS,
                estudios=CEROS,
                planilla=CEROS,
                capex=CEROS,
                exploraciones=CEROS,
            )


class TestLosTotalesSonLaSumaDeSusFilas:
    """Cada banda cierra en la suma de lo que tiene encima, sin sumandos ocultos."""

    @pytest.fixture
    def bloque(self, horizonte: Horizonte) -> Any:
        return hoja(
            horizonte,
            fletes_lom=(10.0,) * ANOS,
            fletes_sobre_concentrado=(20.0,) * ANOS,
            gasto_de_ventas_lom=(5.0,) * ANOS,
            gasto_de_ventas_sobre_concentrado=(15.0,) * ANOS,
            donaciones=(7.0,) * ANOS,
            servidumbre_del_flujo=(3.0,) * ANOS,
            otros_gastos=(1.0,) * ANOS,
            impuestos=tributario(
                utilidad_operativa=(500.0,) * ANOS,
                regalia_mayor=(100.0,) * ANOS,
                impuesto_especial=(40.0,) * ANOS,
                impuesto_a_la_renta=(200.0,) * ANOS,
                osinergmin=(-2.0,) * ANOS,
                oefa=(-1.0,) * ANOS,
                fondo_de_jubilacion=(-4.0,) * ANOS,
            ),
        )

    def test_el_gasto_de_ventas(self, bloque: Any) -> None:
        gasto = bloque.gasto_de_ventas
        assert gasto.total == pytest.approx(
            tuple(a + b for a, b in zip(gasto.lom, gasto.sobre_concentrado, strict=True))
        )

    def test_los_fletes(self, bloque: Any) -> None:
        fletes = bloque.fletes
        assert fletes.total == pytest.approx(
            tuple(a + b for a, b in zip(fletes.lom, fletes.sobre_concentrado, strict=True))
        )

    def test_los_otros_gastos(self, bloque: Any) -> None:
        gastos = bloque.otros_gastos
        esperado = (
            gastos.donaciones[0]
            + gastos.servidumbre[0]
            + gastos.reguladores_y_fondo[0]
            + gastos.otros[0]
            + gastos.regalia[0]
        )
        assert gastos.total[0] == pytest.approx(esperado)

    def test_el_pago_de_impuestos_suma_tres_filas_y_no_cuatro(self, bloque: Any) -> None:
        # La cuarta es `Otros!40`, rotulada `xxx`: la tercera ranura reservada del
        # libro, que no se reproduce. Es la regla `048`, y el total sale igual
        # porque en el libro esa celda vale cero en las treinta y seis columnas.
        pago = bloque.pago_de_impuestos
        esperado = pago.regalia[0] + pago.impuesto_especial[0] + pago.impuesto_a_la_renta[0]
        assert pago.total[0] == pytest.approx(esperado)
        assert pago.total[0] == pytest.approx(-340.0)


class TestLasFilasQueElLibroTeclea:
    """Las semillas del primer año y la bandera de producción, filas 87, 88 y 90."""

    def test_las_dos_semillas_rigen_el_horizonte_entero(self, horizonte: Horizonte) -> None:
        # El libro escribe la constante en el primer ano y copia la celda a los
        # treinta y cinco restantes. Es la regla `047`.
        bloque = hoja(
            horizonte,
            porcentaje_de_ventas_de_exportacion=0.85,
            porcentaje_de_compras_locales=0.60,
        )

        assert bloque.porcentaje_de_ventas_de_exportacion == (0.85,) * ANOS
        assert bloque.porcentaje_de_compras_locales == (0.60,) * ANOS

    def test_la_bandera_sale_como_numero(self, horizonte: Horizonte) -> None:
        # El libro la escribe 1 o 0 y la multiplica por las filas 73 y 80. Sale
        # como numero y no como booleano porque es una fila de la hoja.
        bloque = hoja(horizonte, produce=(True, False, True))

        assert bloque.produce == (1.0, 0.0, 1.0)
