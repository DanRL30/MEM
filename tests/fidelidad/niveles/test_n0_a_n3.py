"""Contraste de fidelidad en cuatro niveles sobre los casos sintéticos.

Es el arnés que `mapa-n1.md` describe y que CI anunciaba sin ejecutar. Su
estructura reproduce la del contraste acordado:

    N0  paridad de inputs leidos          exacta, sin tolerancia
    N1  bloques intermedios, ano a ano    0,1 % relativo o US$ 10 000
    N2  flujos operativo e inversiones    0,1 % relativo o US$ 10 000
    N3  indicadores finales               NPV 0,1 % o US$ 50 000, TIR 5 pb

**Las tolerancias son provisionales.** Son la propuesta de INVA hasta que
Finanzas cierre `R-31`, y por eso viven en constantes con nombre y no repartidas
por los `assert`: el día que se acuerden, cambian en un sitio.

**Pero aquí no se aplican.** La tolerancia contractual existe para comparar el
motor contra un libro de Excel, donde hay redondeos y aritmética ajena. Entre
dos cálculos propios no hay error de medición que tolerar, y aplicarla sobre un
caso sintético la vuelve ciega: una línea cuyo valor esperado son 10 000 pasaría
aunque el motor devolviera cero, porque la diferencia cabe entera dentro de la
tolerancia absoluta. El contraste sintético se hace **exacto**, y la regla
contractual queda implementada, verificada y reservada para el contraste contra
el modelo de referencia.

Contra qué se contrasta. Aquí, contra valores calculados a mano sobre casos de
cifras redondas, porque el modelo de referencia entregado tiene los datos
modificados por confidencialidad y **sirve para contrastar lógica, no cifras**.
El contraste numérico contra los tres casos certificados corre dentro del tenant
de MINSUR y se marca `tenant_minsur`.
"""

from __future__ import annotations

import pytest
from casos import sinteticos

from minsur_engine.corrida import Corrida, calcular, unidades_activas

pytestmark = pytest.mark.fidelidad

TOLERANCIA_RELATIVA = 0.001
TOLERANCIA_ABSOLUTA = 10_000.0
TOLERANCIA_ABSOLUTA_NPV = 50_000.0
TOLERANCIA_TIR = 0.0005
"""Cinco puntos basicos."""

TOLERANCIA_PAYBACK = 0.1


RUIDO_DE_COMA_FLOTANTE = 1e-6


def coincide_con_el_modelo(
    obtenido: float, esperado: float, absoluta: float = TOLERANCIA_ABSOLUTA
) -> bool:
    """Criterio contractual: pasa por relativa **o** por absoluta.

    Es el que se aplicará al contrastar contra el modelo de referencia. La
    absoluta evita que una línea de valor pequeño falle por una diferencia
    irrelevante frente a un flujo de millones; la relativa impide que una línea
    grande pase por serlo.

    No se usa en las pruebas sintéticas: ver el encabezado del módulo.
    """
    diferencia = abs(obtenido - esperado)
    if diferencia <= absoluta:
        return True
    if esperado == 0.0:
        return False
    return diferencia / abs(esperado) <= TOLERANCIA_RELATIVA


def coincide(obtenido: float, esperado: float) -> bool:
    """Igualdad exacta salvo el ruido de la coma flotante."""
    return abs(obtenido - esperado) <= max(RUIDO_DE_COMA_FLOTANTE, abs(esperado) * 1e-12)


def contrastar(serie: tuple[float, ...], esperada: tuple[float, ...], linea: str) -> None:
    """Compara una línea año a año y falla nombrando el año que discrepa."""
    assert len(serie) == len(esperada), f"{linea}: {len(serie)} anos contra {len(esperada)}"
    for i, (obtenido, esperado) in enumerate(zip(serie, esperada, strict=True)):
        assert coincide(obtenido, esperado), (
            f"{linea}, ano {i}: se obtuvo {obtenido:,.2f} y se esperaba {esperado:,.2f}"
        )


@pytest.fixture(scope="module")
def simple() -> Corrida:
    return calcular(sinteticos.unidad_simple(), sinteticos.MAESTROS)


@pytest.fixture(scope="module")
def con_refineria() -> Corrida:
    return calcular(sinteticos.caso_con_refineria(), sinteticos.MAESTROS)


@pytest.fixture(scope="module")
def combinado() -> Corrida:
    return calcular(sinteticos.dos_proyectos(), sinteticos.MAESTROS)


class TestLaReglaDeTolerancia:
    """La regla contractual se verifica aquí, ya que no gobierna lo demás."""

    def test_pasa_por_relativa_en_lineas_grandes(self) -> None:
        assert coincide_con_el_modelo(100_000_000.0, 100_050_000.0)
        assert not coincide_con_el_modelo(100_000_000.0, 101_000_000.0)

    def test_pasa_por_absoluta_en_lineas_pequenas(self) -> None:
        assert coincide_con_el_modelo(1_000.0, 9_000.0)

    def test_es_ciega_por_debajo_de_la_tolerancia_absoluta(self) -> None:
        # Esta es la razon por la que el contraste sintetico no la usa: una
        # linea cuyo valor esperado son 10 000 pasaria valiendo cero.
        assert coincide_con_el_modelo(0.0, TOLERANCIA_ABSOLUTA)
        assert not coincide(0.0, TOLERANCIA_ABSOLUTA)

    def test_el_npv_tiene_su_propia_absoluta(self) -> None:
        assert coincide_con_el_modelo(1_000_000.0, 1_040_000.0, absoluta=TOLERANCIA_ABSOLUTA_NPV)
        assert not coincide_con_el_modelo(1_000_000.0, 1_040_000.0)


# --- N0 · paridad de inputs ---------------------------------------------------


class TestN0:
    """Lo que entra es lo que se declaró. Sin tolerancia."""

    def test_las_series_del_caso_llegan_intactas(self, simple: Corrida) -> None:
        unidad = simple.caso.unidades[0]
        assert unidad.produccion.mineral_tratado == (0.0, 1_000.0, 1_000.0)
        assert unidad.costos["Mina"] == (0.0, 200_000.0, 200_000.0)

    def test_la_corrida_registra_la_version_de_datos_maestros(self, simple: Corrida) -> None:
        # Sin la version, la corrida no se puede reproducir a cinco anos.
        assert simple.version_datos_maestros == "CP-SINTETICO-01"

    def test_el_horizonte_gobierna_todas_las_series(self, con_refineria: Corrida) -> None:
        anos = con_refineria.caso.horizonte.anos
        for nombre, serie in (
            ("ventas", con_refineria.ventas),
            ("cash cost", con_refineria.cash_cost),
            ("capex", con_refineria.capex),
            ("flujo economico", con_refineria.flujo.flujo_economico),
        ):
            assert len(serie) == anos, f"{nombre} no esta alineada al horizonte"

    def test_las_unidades_sin_datos_no_participan(self, combinado: Corrida) -> None:
        # Criterio de Finanzas del 01/09/2026: la participacion se deriva de
        # los datos, no de un interruptor.
        activas = unidades_activas(combinado.caso)
        assert activas["Operacion"] == (0, 1, 2, 3, 4)
        assert activas["Proyecto X"] == (2, 3, 4)
        assert combinado.depreciacion_tributaria_por_mina["Proyecto X"][:2] == (0.0, 0.0)


# --- N1 · bloques intermedios --------------------------------------------------


class TestN1:
    """Cada bloque, año a año, contra su valor calculado a mano."""

    def test_ventas(self, simple: Corrida) -> None:
        # 100 tmf al precio de 10 000, sin premio.
        contrastar(simple.ventas, (0.0, 1_000_000.0, 1_000_000.0), "ventas")

    def test_cash_cost(self, simple: Corrida) -> None:
        contrastar(simple.cash_cost, (0.0, 200_000.0, 200_000.0), "cash cost")

    def test_depreciacion_no_corre_antes_de_producir(self, simple: Corrida) -> None:
        # La inversion es del primer ano y la produccion empieza en el segundo:
        # la cuota del primer ejercicio se anula (regla 013) y solo queda una.
        por_mina = simple.depreciacion_tributaria_por_mina["Mina Unica"]
        contrastar(por_mina, (0.0, 500_000.0, 0.0), "depreciacion tributaria")

    def test_regalia_manda_la_minima_sobre_ventas(self, simple: Corrida) -> None:
        # Con escala plana al 1 % del margen, la regalia por margen queda por
        # debajo del 1 % de ventas y el libro toma la mayor.
        contrastar(simple.regalias, (0.0, 10_000.0, 10_000.0), "regalia")

    def test_participacion_de_trabajadores(self, simple: Corrida) -> None:
        contrastar(simple.participacion_trabajadores, (0.0, 23_200.0, 63_200.0), "participacion")

    def test_impuesto_a_la_renta(self, simple: Corrida) -> None:
        contrastar(simple.impuesto_renta, (0.0, 78_278.25, 213_240.75), "impuesto a la renta")

    def test_la_utilidad_operativa_cierra_el_lazo_del_fondo(self, simple: Corrida) -> None:
        # El fondo de jubilacion es gasto de la utilidad operativa que lo
        # determina. Si el lazo no cierra, la solucion cerrada esta mal.
        for ano, resultado in enumerate(simple.tributos_por_ano):
            esperada = 1_000_000.0 - 200_000.0 if ano else 0.0
            base = esperada - (500_000.0 if ano == 1 else 0.0)
            assert coincide(
                resultado.utilidad_operativa, base - resultado.fondo_jubilacion_minera
            ), f"el lazo del fondo no cierra en el ano {ano}"

    def test_el_tope_de_la_refineria_acota_el_tratamiento(self, con_refineria: Corrida) -> None:
        # Alimentado 1 200, 1 400, 1 600 y 1 700 contra una capacidad de 1 500.
        contrastar(
            con_refineria.refineria.concentrado_entregado,
            (1_200.0, 1_400.0, 1_600.0, 1_700.0),
            "alimentado",
        )
        contrastar(
            con_refineria.refineria.concentrado_alimentado,
            (1_200.0, 1_400.0, 1_500.0, 1_500.0),
            "tratado",
        )
        contrastar(
            con_refineria.refineria.concentrado_excedente, (0.0, 0.0, 100.0, 200.0), "excedente"
        )

    def test_lo_tratado_mas_lo_excedente_es_lo_alimentado(self, con_refineria: Corrida) -> None:
        for i, alimentado in enumerate(con_refineria.refineria.concentrado_entregado):
            suma = (
                con_refineria.refineria.concentrado_alimentado[i]
                + con_refineria.refineria.concentrado_excedente[i]
            )
            assert coincide(suma, alimentado), f"descuadre en el ano {i}"

    def test_la_depreciacion_se_desglosa_por_mina(self, combinado: Corrida) -> None:
        # D-04: MINSUR pidio el calculo separado por mina en todos los casos.
        por_mina = combinado.depreciacion_tributaria_por_mina
        assert set(por_mina) == {"Proyecto X"}, "solo la unidad con capital deprecia"
        # 600 000 al 50 %, con la produccion arrancando en el tercer ano.
        contrastar(
            por_mina["Proyecto X"], (0.0, 0.0, 300_000.0, 0.0, 0.0), "depreciacion Proyecto X"
        )


# --- N2 · flujos ---------------------------------------------------------------


class TestN2:
    """Los tres escalones del flujo, contrastados y consistentes entre sí."""

    def test_ebitda_ajustado(self, simple: Corrida) -> None:
        contrastar(simple.flujo.ebitda_ajustado, (0.0, 775_350.0, 732_850.0), "EBITDA ajustado")

    def test_flujo_operativo(self, simple: Corrida) -> None:
        contrastar(simple.flujo.flujo_operativo, (0.0, 687_071.75, 509_609.25), "flujo operativo")

    def test_flujo_de_inversiones(self, simple: Corrida) -> None:
        contrastar(
            simple.flujo.flujo_de_inversiones, (-1_000_000.0, 0.0, 0.0), "flujo de inversiones"
        )

    def test_flujo_economico(self, simple: Corrida) -> None:
        contrastar(
            simple.flujo.flujo_economico,
            (-1_000_000.0, 687_071.75, 509_609.25),
            "flujo economico",
        )

    def test_el_economico_es_la_suma_de_los_otros_dos(self, con_refineria: Corrida) -> None:
        for i, economico in enumerate(con_refineria.flujo.flujo_economico):
            suma = (
                con_refineria.flujo.flujo_operativo[i] + con_refineria.flujo.flujo_de_inversiones[i]
            )
            assert coincide(economico, suma), f"descuadre en el ano {i}"

    def test_una_inversion_nunca_entra_a_caja(self, combinado: Corrida) -> None:
        assert all(v <= 0.0 for v in combinado.flujo.flujo_de_inversiones)


# --- N3 · indicadores ----------------------------------------------------------


class TestN3:
    """Las cuatro cifras que el cliente mira, con sus propias tolerancias."""

    def test_npv(self, simple: Corrida) -> None:
        esperado = -1_000_000.0 + 687_071.75 / 1.1 + 509_609.25 / 1.21
        assert coincide(simple.indicadores.npv, esperado), (
            f"NPV: se obtuvo {simple.indicadores.npv:,.2f} y se esperaba {esperado:,.2f}"
        )

    def test_la_tir_anula_el_valor_presente(self, simple: Corrida) -> None:
        from minsur_engine.indicadores import npv

        tasa = simple.indicadores.tir
        assert tasa is not None
        assert abs(npv(simple.flujo.flujo_economico, tasa)) < 1.0

    def test_la_tir_es_reproducible(self) -> None:
        # Condicion del sellado: dos corridas del mismo caso, el mismo numero.
        primera = calcular(sinteticos.unidad_simple(), sinteticos.MAESTROS)
        segunda = calcular(sinteticos.unidad_simple(), sinteticos.MAESTROS)
        assert primera.indicadores.tir == segunda.indicadores.tir
        assert primera.indicadores.npv == segunda.indicadores.npv

    def test_payback(self, simple: Corrida) -> None:
        # Se invierte 1 000 000 y el segundo ano devuelve 687 071,75: falta
        # recuperar 312 928,25 de los 509 609,25 del tercero.
        esperado = 2.0 + 312_928.25 / 509_609.25
        assert simple.indicadores.payback.alcanzado
        assert abs(simple.indicadores.payback.anos - esperado) <= TOLERANCIA_PAYBACK

    def test_el_payback_descontado_no_es_anterior_al_simple(self, simple: Corrida) -> None:
        assert simple.indicadores.payback_descontado.anos >= simple.indicadores.payback.anos

    def test_capital_intensity_solo_si_hay_capacidad(
        self, simple: Corrida, combinado: Corrida
    ) -> None:
        assert simple.indicadores.capital_intensity is None
        assert combinado.indicadores.capital_intensity == pytest.approx(600_000.0 / 800.0)

    def test_un_caso_sin_desembolso_no_define_tir(self, con_refineria: Corrida) -> None:
        # La refinería no declara capital: su flujo no cambia de signo y la TIR
        # no existe. Informarlo es mejor que devolver un numero.
        assert con_refineria.indicadores.tir is None
