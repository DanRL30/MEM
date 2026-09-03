"""Pruebas del bloque tributario y de la circularidad.

La prueba que sostiene el [ADR 0009](../../../docs/adr/0009-resolucion-de-la-circularidad-tributaria.md)
es `test_coincide_con_el_punto_fijo`: la solución cerrada y una aproximación
independiente tienen que dar el mismo número. Si divergen, la derivación del
sistema está mal, y eso es un fallo del motor aunque el resultado parezca
razonable.

Las escalas de estas pruebas son sintéticas. Las reales son dato maestro que
mantiene MINSUR (`R-32`) y no viven en el código.
"""

from __future__ import annotations

import pytest

from minsur_engine.horizonte import Horizonte
from minsur_engine.impuestos import (
    BloqueDeImpuestos,
    EntradasTributarias,
    ErrorTributos,
    EscalaProgresiva,
    Tramo,
    calcular,
    resolver,
    resolver_por_punto_fijo,
)

ESCALA_REGALIA = EscalaProgresiva(
    tramos=(
        Tramo(0.0, 0.10, 0.01),
        Tramo(0.10, 0.20, 0.02),
        Tramo(0.20, 0.40, 0.04),
        Tramo(0.40, 10.0, 0.08),
    )
)
ESCALA_IEM = EscalaProgresiva(
    tramos=(
        Tramo(0.0, 0.10, 0.02),
        Tramo(0.10, 0.30, 0.03),
        Tramo(0.30, 10.0, 0.05),
    )
)


def entradas(**cambios: float) -> EntradasTributarias:
    base: dict[str, float] = {
        "ventas_totales": 1_000_000.0,
        "base_operativa": 400_000.0,
        "base_imponible": 380_000.0,
        "saldo_perdidas": 0.0,
        "tasa_regalia_ventas": 0.01,
        "tasa_fondo_jubilacion": 0.005,
        "tasa_participacion": 0.08,
        "tasa_impuesto_renta": 0.295,
    }
    base.update(cambios)
    return EntradasTributarias(
        ventas_totales=base["ventas_totales"],
        base_operativa=base["base_operativa"],
        base_imponible=base["base_imponible"],
        saldo_perdidas=base["saldo_perdidas"],
        escala_regalia=ESCALA_REGALIA,
        escala_iem=ESCALA_IEM,
        tasa_regalia_ventas=base["tasa_regalia_ventas"],
        tasa_fondo_jubilacion=base["tasa_fondo_jubilacion"],
        tasa_participacion=base["tasa_participacion"],
        tasa_impuesto_renta=base["tasa_impuesto_renta"],
    )


class TestEscalaProgresiva:
    def test_acumula_los_tramos_completos_y_la_fraccion_del_ultimo(self) -> None:
        # Margen 0,25: 10 % al 1 %, 10 % al 2 %, y 5 % al 4 %.
        esperado = 0.10 * 0.01 + 0.10 * 0.02 + 0.05 * 0.04
        assert ESCALA_REGALIA.suma_de_tramos(0.25) == pytest.approx(esperado)

    def test_los_coeficientes_describen_la_recta_del_tramo(self) -> None:
        constante, pendiente = ESCALA_REGALIA.coeficientes(0.25)
        for margen in (0.21, 0.25, 0.39):
            assert constante + pendiente * margen == pytest.approx(
                ESCALA_REGALIA.suma_de_tramos(margen)
            )

    def test_la_regalia_es_afin_en_la_utilidad_operativa(self) -> None:
        # Es la propiedad que hace posible la solucion cerrada: la tasa
        # efectiva divide por el margen y despues se multiplica por la
        # utilidad, de modo que el margen se cancela contra si mismo.
        ventas = 1_000_000.0
        constante, pendiente = ESCALA_REGALIA.coeficientes(0.25)
        for utilidad in (210_000.0, 250_000.0, 390_000.0):
            regalia = ESCALA_REGALIA.suma_de_tramos(utilidad / ventas) * ventas
            assert regalia == pytest.approx(ventas * constante + pendiente * utilidad)

    def test_los_aportes_suman_lo_mismo_que_la_forma_afin(self) -> None:
        # Dos implementaciones de la misma cantidad, por el mismo motivo que
        # conviven la solucion cerrada y el punto fijo: la de tramos informa la
        # tabla del libro y la afin resuelve el sistema. Si divergen, una de las
        # dos esta mal.
        for margen in (-0.20, 0.0, 0.05, 0.10, 0.25, 0.40, 5.0):
            assert sum(ESCALA_REGALIA.aportes(margen)) == pytest.approx(
                ESCALA_REGALIA.suma_de_tramos(margen)
            )
            assert sum(ESCALA_IEM.aportes(margen)) == pytest.approx(
                ESCALA_IEM.suma_de_tramos(margen)
            )

    def test_un_tramo_no_aporta_nada_por_encima_del_margen(self) -> None:
        # Margen 0,25: los dos primeros tramos completos, el tercero parcial y
        # el cuarto en cero. Es la fila de la tabla que el libro deja vacia.
        aportes = ESCALA_REGALIA.aportes(0.25)
        assert aportes == pytest.approx((0.10 * 0.01, 0.10 * 0.02, 0.05 * 0.04, 0.0))

    def test_la_tasa_efectiva_es_la_suma_entre_el_margen(self) -> None:
        assert ESCALA_REGALIA.tasa_efectiva(0.25) == pytest.approx(
            sum(ESCALA_REGALIA.aportes(0.25)) / 0.25
        )

    def test_sin_margen_la_tasa_efectiva_es_cero(self) -> None:
        # Es el `IFERROR` de las filas 22 y 26: la division se indetermina y
        # cero es el resultado esperado.
        assert ESCALA_REGALIA.tasa_efectiva(0.0) == 0.0
        assert ESCALA_IEM.tasa_efectiva(0.0) == 0.0

    def test_una_escala_con_hueco_no_se_construye(self) -> None:
        with pytest.raises(ErrorTributos, match="hueco"):
            EscalaProgresiva(tramos=(Tramo(0.0, 0.1, 0.01), Tramo(0.2, 0.3, 0.02)))

    def test_un_tramo_invertido_no_se_construye(self) -> None:
        with pytest.raises(ErrorTributos, match="invertido"):
            Tramo(0.3, 0.1, 0.01)


class TestCircularidad:
    def test_coincide_con_el_punto_fijo(self) -> None:
        # El requisito del ADR 0009: exacta y aproximada dan el mismo numero.
        datos = entradas()
        exacta = resolver(datos)
        aproximada = resolver_por_punto_fijo(datos)
        assert exacta.utilidad_operativa == pytest.approx(aproximada.utilidad_operativa, rel=1e-12)
        assert exacta.regalia == pytest.approx(aproximada.regalia, rel=1e-12)
        assert exacta.impuesto_renta == pytest.approx(aproximada.impuesto_renta, rel=1e-12)

    @pytest.mark.parametrize(
        "base_operativa",
        [50_000.0, 150_000.0, 250_000.0, 400_000.0, 700_000.0],
    )
    def test_coincide_con_el_punto_fijo_en_todos_los_tramos(self, base_operativa: float) -> None:
        datos = entradas(base_operativa=base_operativa, base_imponible=base_operativa - 20_000.0)
        assert resolver(datos).utilidad_operativa == pytest.approx(
            resolver_por_punto_fijo(datos).utilidad_operativa, rel=1e-12
        )

    def test_la_solucion_cierra_el_lazo(self) -> None:
        # El fondo de jubilacion es gasto de la utilidad operativa que lo
        # determina: la solucion tiene que satisfacer esa igualdad.
        datos = entradas()
        r = resolver(datos)
        assert r.utilidad_operativa == pytest.approx(
            datos.base_operativa - r.fondo_jubilacion_minera
        )

    def test_el_margen_es_la_utilidad_sobre_las_ventas(self) -> None:
        datos = entradas()
        r = resolver(datos)
        assert r.margen_operativo == pytest.approx(r.utilidad_operativa / datos.ventas_totales)


class TestRegalia:
    def test_la_regalia_minima_sobre_ventas_manda_cuando_el_margen_es_bajo(self) -> None:
        # Con margen pequeno la escala progresiva rinde menos que el 1 % de
        # ventas, y el libro toma el mayor de los dos.
        datos = entradas(base_operativa=30_000.0, base_imponible=25_000.0)
        r = resolver(datos)
        assert r.regalia == pytest.approx(datos.tasa_regalia_ventas * datos.ventas_totales)

    def test_con_margen_alto_manda_la_escala_progresiva(self) -> None:
        datos = entradas(base_operativa=700_000.0, base_imponible=680_000.0)
        r = resolver(datos)
        assert r.regalia > datos.tasa_regalia_ventas * datos.ventas_totales

    def test_la_tea_reconstruye_la_regalia(self) -> None:
        # El libro escribe `TEA x utilidad operativa` y el motor
        # `suma de tramos x ventas`. Son la misma cantidad, y esta prueba es lo
        # que permite informar la primera mientras se calcula con la segunda.
        for base in (150_000.0, 400_000.0, 700_000.0):
            r = resolver(entradas(base_operativa=base, base_imponible=base - 20_000.0))
            assert r.tasa_efectiva_regalia * r.utilidad_operativa == pytest.approx(
                r.regalia_sobre_margen
            )
            assert r.tasa_efectiva_iem * r.utilidad_operativa == pytest.approx(
                r.impuesto_especial_mineria
            )

    def test_la_regalia_mayor_es_el_maximo_de_las_dos_filas(self) -> None:
        for base in (30_000.0, 400_000.0, 700_000.0):
            r = resolver(entradas(base_operativa=base, base_imponible=base - 20_000.0))
            assert r.regalia == max(r.regalia_sobre_margen, r.regalia_sobre_ventas)


class TestDeduccionesYSalidas:
    def test_las_perdidas_acumuladas_se_deducen_hasta_la_mitad_de_la_utilidad(self) -> None:
        sin_perdidas = resolver(entradas())
        con_perdidas = resolver(entradas(saldo_perdidas=1_000_000.0))
        assert con_perdidas.deduccion_perdidas == pytest.approx(
            -con_perdidas.utilidad_imponible * 0.5
        )
        assert con_perdidas.impuesto_renta < sin_perdidas.impuesto_renta

    def test_un_saldo_menor_que_el_limite_se_deduce_entero(self) -> None:
        r = resolver(entradas(saldo_perdidas=1_000.0))
        assert r.deduccion_perdidas == pytest.approx(-1_000.0)

    def test_sin_utilidad_no_hay_participacion_ni_renta(self) -> None:
        r = resolver(entradas(base_operativa=-50_000.0, base_imponible=-80_000.0))
        assert r.participacion_trabajadores == 0.0
        assert r.impuesto_renta == 0.0
        assert r.fondo_jubilacion_minera == 0.0

    def test_sin_ventas_no_hay_regalia_ni_margen(self) -> None:
        r = resolver(entradas(ventas_totales=0.0, base_operativa=0.0, base_imponible=0.0))
        assert r.regalia == 0.0
        assert r.margen_operativo == 0.0

    def test_la_renta_se_calcula_despues_de_participaciones(self) -> None:
        datos = entradas()
        r = resolver(datos)
        neta = r.utilidad_imponible + r.deduccion_perdidas
        esperado = (
            neta - r.fondo_jubilacion_minera - r.participacion_trabajadores
        ) * datos.tasa_impuesto_renta
        assert r.impuesto_renta == pytest.approx(esperado)


HORIZONTE = Horizonte(primer_ano=2027, anos=4)


def bloque(**cambios: object) -> BloqueDeImpuestos:
    """La hoja entera sobre un caso pequeño, con un año de pérdida en medio."""
    argumentos: dict[str, object] = {
        "ventas": (0.0, 1_000_000.0, 400_000.0, 1_200_000.0),
        "cash_cost": (0.0, 400_000.0, 380_000.0, 420_000.0),
        "fletes": (0.0, 30_000.0, 12_000.0, 36_000.0),
        "gasto_de_ventas": (0.0, 20_000.0, 8_000.0, 24_000.0),
        "administrativos": (5_000.0, 50_000.0, 50_000.0, 50_000.0),
        "estudios_deducibles": (12_000.0, 4_000.0, 4_000.0, 0.0),
        "gestion_social_deducible": (0.0, 15_000.0, 15_000.0, 15_000.0),
        "otros_gastos": (0.0, 6_000.0, 6_000.0, 6_000.0),
        "tasa_osinergmin": (0.0014, 0.0014, 0.0014, 0.0014),
        "tasa_oefa": (0.001, 0.001, 0.001, 0.001),
        "depreciacion_financiera": (0.0, 90_000.0, 90_000.0, 90_000.0),
        "depreciacion_tributaria": (0.0, 120_000.0, 120_000.0, 60_000.0),
        "exploraciones": (8_000.0, 0.0, 0.0, 0.0),
        "tasa_regalia_ventas": 0.01,
        "tasa_fondo_jubilacion": 0.005,
        "tasa_participacion": 0.08,
        "tasa_impuesto_renta": 0.295,
        "limite_arrastre_de_perdidas": 0.5,
        "saldo_inicial_de_perdidas": 0.0,
    }
    argumentos.update(cambios)
    return calcular(
        HORIZONTE,
        escala_regalia=ESCALA_REGALIA,
        escala_iem=ESCALA_IEM,
        **argumentos,  # type: ignore[arg-type]
    )


def suma_de_filas(filas: tuple[tuple[float, ...], ...], ano: int) -> float:
    return sum(fila[ano] for fila in filas)


class TestLaHojaEntera:
    """El bloque reproduce la hoja `Impuestos` fila a fila.

    Estas pruebas no verifican el resultado tributario -de eso se ocupan las de
    arriba- sino que las filas expuestas sean las de la hoja y que sus sumas
    cierren. Si una fila se cae del bloque, o entra con el signo cambiado, aqui
    se ve; en el NPV, no.
    """

    def test_la_utilidad_operativa_es_la_suma_de_sus_doce_filas(self) -> None:
        # `Impuestos!20 = SUM(8:19)`, con la 19 incluida: el fondo de jubilacion
        # descuenta la misma utilidad que lo determina.
        b = bloque()
        for ano in range(HORIZONTE.anos):
            assert b.regalias.utilidad_operativa[ano] == pytest.approx(
                suma_de_filas(b.regalias.conceptos, ano)
            )

    def test_la_utilidad_operativa_de_renta_es_la_suma_de_sus_once_filas(self) -> None:
        # `Impuestos!41 = SUM(30:40)`. Aqui no entra el fondo de jubilacion.
        b = bloque()
        for ano in range(HORIZONTE.anos):
            assert b.renta.utilidad_operativa[ano] == pytest.approx(
                suma_de_filas(b.renta.conceptos, ano)
            )

    def test_la_utilidad_imponible_es_la_suma_de_sus_seis_filas(self) -> None:
        # `Impuestos!47 = SUM(41:46)`.
        b = bloque()
        for ano in range(HORIZONTE.anos):
            assert b.renta.utilidad_imponible[ano] == pytest.approx(
                suma_de_filas(b.renta.sumandos_de_la_imponible, ano)
            )

    def test_la_utilidad_tras_participaciones_es_la_suma_de_sus_tres_filas(self) -> None:
        # `Impuestos!59 = SUM(56:58)`.
        b = bloque()
        for ano in range(HORIZONTE.anos):
            assert b.impuesto_a_la_renta.utilidad_luego_de_participaciones[ano] == pytest.approx(
                suma_de_filas(b.impuesto_a_la_renta.sumandos, ano)
            )

    def test_el_saldo_final_es_la_suma_de_sus_tres_filas(self) -> None:
        # `Impuestos!67 = SUM(64:66)`.
        b = bloque()
        p = b.perdida_tributaria
        for ano in range(HORIZONTE.anos):
            assert p.saldo_final[ano] == pytest.approx(
                p.saldo_inicial[ano] + p.perdida_de_ejercicio[ano] + p.perdida_a_amortizar[ano]
            )

    def test_el_lazo_cierra_fila_contra_fila(self) -> None:
        # `Impuestos!19 = 57`, que es el unico lazo de la hoja.
        b = bloque()
        assert b.regalias.fondo_de_jubilacion == b.impuesto_a_la_renta.fondo_de_jubilacion

    def test_el_saldo_de_perdidas_rueda_de_un_ano_al_siguiente(self) -> None:
        # `Impuestos!64` del ejercicio n es la `67` del n-1.
        p = bloque(ventas=(0.0, 200_000.0, 400_000.0, 1_500_000.0)).perdida_tributaria
        for ano in range(HORIZONTE.anos - 1):
            assert p.saldo_inicial[ano + 1] == pytest.approx(p.saldo_final[ano])
        assert p.saldo_inicial[0] == 0.0

    def test_un_ejercicio_con_perdida_alimenta_el_saldo(self) -> None:
        p = bloque().perdida_tributaria
        with_perdida = [i for i, v in enumerate(p.perdida_de_ejercicio) if v > 0.0]
        assert with_perdida, "el caso de prueba deberia tener un ano en perdida"
        for ano in with_perdida:
            assert p.saldo_final[ano] > p.saldo_inicial[ano]

    def test_las_dos_bases_difieren_en_la_via_de_la_depreciacion(self) -> None:
        # Es la diferencia que un contraste por indicadores no delata: las dos
        # bases comparten nueve conceptos y separan la depreciacion.
        b = bloque()
        assert b.regalias.depreciacion_financiera != b.renta.depreciacion_tributaria
        assert b.regalias.costo_de_produccion == b.renta.costo_de_produccion
        assert b.regalias.ventas_totales == b.renta.ventas_netas

    def test_los_gastos_entran_con_el_signo_del_libro(self) -> None:
        b = bloque()
        assert all(valor <= 0.0 for valor in b.regalias.costo_de_produccion)
        assert all(valor <= 0.0 for valor in b.regalias.osinergmin)
        assert all(valor >= 0.0 for valor in b.regalias.ventas_totales)

    def test_las_filas_financieras_estan_declaradas_y_valen_cero(self) -> None:
        # Las filas 44 y 45 del libro estan vacias, y el estandar las nombra.
        b = bloque()
        assert b.renta.ingresos_financieros == HORIZONTE.ceros()
        assert b.renta.gastos_financieros == HORIZONTE.ceros()

    def test_la_tabla_de_tramos_lleva_una_fila_por_tramo(self) -> None:
        b = bloque()
        assert len(b.tramos_de_regalia) == len(ESCALA_REGALIA.tramos)
        assert len(b.tramos_de_iem) == len(ESCALA_IEM.tramos)
        for fila in b.tramos_de_regalia:
            assert len(fila.aporte) == HORIZONTE.anos

    def test_los_aportes_de_la_tabla_reconstruyen_la_tea(self) -> None:
        # `Impuestos!22 = SUM(72:87) / 21`, que es lo que hace contrastable un
        # tramo suelto cuando la TEA no cuadra.
        b = bloque()
        for ano in range(HORIZONTE.anos):
            margen = b.regalias.margen_operativo[ano]
            if margen == 0.0:
                assert b.regalias.tasa_efectiva_regalia[ano] == 0.0
                continue
            aportado = suma_de_filas(tuple(f.aporte for f in b.tramos_de_regalia), ano)
            assert b.regalias.tasa_efectiva_regalia[ano] == pytest.approx(aportado / margen)

    def test_sin_ventas_el_ejercicio_no_paga_nada(self) -> None:
        b = bloque()
        assert b.regalias.ventas_totales[0] == 0.0
        assert b.regalias.regalia_mayor[0] == 0.0
        assert b.impuesto_a_la_renta.impuesto_a_la_renta[0] == 0.0
