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

from dataclasses import replace

import pytest
from casos import sinteticos

from minsur_engine.caso import Caso
from minsur_engine.corrida import Corrida, calcular, unidades_activas
from minsur_engine.ventas import GRAMOS_POR_ONZA_TROY, LIBRAS_POR_TONELADA

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


@pytest.fixture(scope="module")
def con_agotamiento() -> Corrida:
    return calcular(sinteticos.caso_con_agotamiento(), sinteticos.MAESTROS)


@pytest.fixture(scope="module")
def polimetalico() -> Corrida:
    return calcular(sinteticos.caso_polimetalico(), sinteticos.MAESTROS)


@pytest.fixture(scope="module")
def con_capital_de_trabajo() -> Corrida:
    return calcular(sinteticos.caso_de_capital_de_trabajo(), sinteticos.MAESTROS)


# Cifras del concentrado, calculadas a mano desde las constantes del caso. El
# cobre paga la menor de sus dos deducciones -0,30 x 0,90 frente a 0,30 - 0,01-
# y la plata pasa de gramos por tonelada a onzas troy.
LEY_PAGABLE_CU_ALFA = sinteticos.LEY_CU_ALFA * sinteticos.FACTOR_PAGABLE_CU
LEY_PAGABLE_CU_BETA = sinteticos.LEY_CU_BETA * sinteticos.FACTOR_PAGABLE_CU
RC_CU = sinteticos.TARIFA_RC_CU * LIBRAS_POR_TONELADA
CONTENIDO_AG_ALFA = sinteticos.LEY_PAGABLE_AG_ALFA / GRAMOS_POR_ONZA_TROY
CONTENIDO_AG_BETA = sinteticos.LEY_PAGABLE_AG_BETA / GRAMOS_POR_ONZA_TROY


def _liquidacion(embarcado: float, ley_pagable_cu: float, contenido_ag: float) -> float:
    """Valor neto de un embarque: contenido sobre vendidas, cargos sobre netas."""
    netas = embarcado * (1.0 - sinteticos.MERMA)
    pagable = (
        ley_pagable_cu * sinteticos.PRECIO_CU * embarcado
        + contenido_ag * sinteticos.PRECIO_AG * embarcado
    )
    cargos = netas * (sinteticos.MAQUILA + RC_CU + contenido_ag * sinteticos.TARIFA_RC_AG)
    return pagable - cargos


def _sin_merma(caso: Caso) -> Caso:
    """El mismo caso con la merma en cero, para aislar su efecto."""
    concentrado = caso.terminos.concentrado
    assert concentrado is not None
    return replace(
        caso,
        terminos=replace(
            caso.terminos,
            concentrado=replace(concentrado, merma=caso.horizonte.ceros()),
        ),
    )


def _sin_concentrado(caso: Caso) -> Caso:
    """El mismo caso sin condiciones de concentrado: la liquidacion desaparece."""
    return replace(caso, terminos=replace(caso.terminos, concentrado=None))


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

    def test_declarar_las_reservas_las_convierte_en_dato(self, con_agotamiento: Corrida) -> None:
        # Una unidad en marcha las trae de su plan de vida de mina; un proyecto
        # todavia no las tiene y salen de lo que su propio plan extrae.
        larga, proyecto = con_agotamiento.caso.unidades
        assert larga.reservas == 4_000.0
        assert proyecto.reservas is None
        assert sum(proyecto.produccion.mineral_extraido) == 1_000.0

    def test_la_ley_pagable_declarada_llega_intacta_a_la_liquidacion(
        self, polimetalico: Corrida
    ) -> None:
        # La de plata se carga porque su formula esta consultada (regla 045): lo
        # que se declara es lo que liquida, sin recalculo por el camino.
        volumen = polimetalico.volumen_pagable_por_unidad["Mina Alfa"]["Ag"]
        embarcado = polimetalico.caso.unidades[0].produccion.concentrado_de_cu
        contrastar(
            volumen, tuple(CONTENIDO_AG_ALFA * t for t in embarcado), "volumen pagable de Ag"
        )


# --- N1 · bloques intermedios --------------------------------------------------


class TestN1:
    """Cada bloque, año a año, contra su valor calculado a mano."""

    def test_ventas(self, simple: Corrida) -> None:
        # 100 tmf al precio de 10 000, sin premio.
        contrastar(simple.ventas, (0.0, 1_000_000.0, 1_000_000.0), "ventas")

    def test_metal_pagable(self, polimetalico: Corrida) -> None:
        """Volumen pagable por unidad y por metal, en la unidad de cada uno."""
        alfa = polimetalico.volumen_pagable_por_unidad["Mina Alfa"]
        beta = polimetalico.volumen_pagable_por_unidad["Mina Beta"]
        # Toneladas de cobre pagable: 1 000 t al 27 % y 500 t al 18 %.
        contrastar(alfa["Cu"], (0.0, 270.0, 270.0), "volumen pagable de Cu en Alfa")
        contrastar(beta["Cu"], (0.0, 90.0, 90.0), "volumen pagable de Cu en Beta")
        # Onzas troy de plata.
        contrastar(
            beta["Ag"],
            (0.0, CONTENIDO_AG_BETA * 500.0, CONTENIDO_AG_BETA * 500.0),
            "volumen pagable de Ag en Beta",
        )

    def test_ventas_del_concentrado(self, polimetalico: Corrida) -> None:
        """Las cuatro lineas de venta del libro, cada una por separado."""
        alfa = _liquidacion(1_000.0, LEY_PAGABLE_CU_ALFA, CONTENIDO_AG_ALFA)
        beta = _liquidacion(500.0, LEY_PAGABLE_CU_BETA, CONTENIDO_AG_BETA)
        contrastar(polimetalico.ventas_por_unidad["Mina Alfa"], (0.0, alfa, alfa), "venta de Alfa")
        contrastar(polimetalico.ventas_por_unidad["Mina Beta"], (0.0, beta, beta), "venta de Beta")

        caminos = polimetalico.ventas_por_camino
        contrastar(caminos["Venta Sn Refinado"], (0.0, 0.0, 0.0), "venta de Sn refinado")
        contrastar(
            caminos["Venta Cu + Ag"], (0.0, alfa + beta, alfa + beta), "venta del concentrado"
        )
        contrastar(caminos["Ajustes finales"], (0.0, 50_000.0, 0.0), "ajustes")
        # El total es la suma de las cuatro lineas, y nada mas.
        contrastar(
            polimetalico.ventas,
            (0.0, alfa + beta + 50_000.0, alfa + beta),
            "venta total",
        )

    def test_una_unidad_no_hereda_la_ley_de_la_otra(self, polimetalico: Corrida) -> None:
        # Regla de oro: cada mina liquida con su propia ley. Agrupar las dos en
        # una ley media daria un solo numero que no se puede atribuir a nadie.
        agrupado = _liquidacion(
            1_500.0, (LEY_PAGABLE_CU_ALFA + LEY_PAGABLE_CU_BETA) / 2.0, CONTENIDO_AG_ALFA
        )
        por_unidad = polimetalico.ventas_por_unidad
        suma = por_unidad["Mina Alfa"][1] + por_unidad["Mina Beta"][1]
        assert not coincide(suma, agrupado)

    def test_las_penalidades_no_llegan_a_la_venta(self, polimetalico: Corrida) -> None:
        # Regla 010, esta vez sobre la corrida entera y no sobre la funcion: el
        # caso declara penalidades de cobre y de plata y la venta no las acusa.
        alfa = _liquidacion(1_000.0, LEY_PAGABLE_CU_ALFA, CONTENIDO_AG_ALFA)
        contrastar(
            polimetalico.concentrado_liquidado_por_unidad["Mina Alfa"],
            (0.0, alfa, alfa),
            "liquidacion de Alfa",
        )

    def test_el_pagable_va_sobre_vendidas_y_los_cargos_sobre_netas(self) -> None:
        """Regla 011: subir la merma no toca el contenido, solo los cargos."""
        con_merma = calcular(sinteticos.caso_polimetalico(), sinteticos.MAESTROS)
        sin_merma = calcular(_sin_merma(sinteticos.caso_polimetalico()), sinteticos.MAESTROS)
        # El volumen pagable es identico: la merma no descuenta contenido.
        contrastar(
            sin_merma.volumen_pagable_por_unidad["Mina Alfa"]["Cu"],
            con_merma.volumen_pagable_por_unidad["Mina Alfa"]["Cu"],
            "volumen pagable con y sin merma",
        )
        # Y la diferencia de venta es exactamente la de los cargos: la merma
        # rebaja las toneladas que pagan maquila y refinacion, de modo que el
        # caso con merma vende mas, no menos.
        cargos = 1_500.0 * sinteticos.MERMA * (sinteticos.MAQUILA + RC_CU)
        cargos += 1_000.0 * sinteticos.MERMA * CONTENIDO_AG_ALFA * sinteticos.TARIFA_RC_AG
        cargos += 500.0 * sinteticos.MERMA * CONTENIDO_AG_BETA * sinteticos.TARIFA_RC_AG
        assert coincide(con_merma.ventas[1] - sin_merma.ventas[1], cargos)

    def test_capital_de_trabajo(self, con_capital_de_trabajo: Corrida) -> None:
        """Los saldos rotan sobre la venta y sobre la bolsa de egresos."""
        corrida = con_capital_de_trabajo
        # 1 000 000 de venta con 36 dias sobre 360: la decima parte.
        contrastar(
            corrida.cuentas_por_cobrar.saldos,
            (0.0, 100_000.0, 100_000.0, 0.0, 100_000.0),
            "saldo de cuentas por cobrar",
        )
        # La deuda rota sobre la bolsa, que en el primer ano es el capital
        # entero: es la diferencia con la base de solo costo operativo.
        contrastar(
            corrida.cuentas_por_pagar.saldos,
            tuple(bolsa * sinteticos.DIAS_POR_PAGAR / 360.0 for bolsa in corrida.bolsa_de_egresos),
            "saldo de cuentas por pagar",
        )
        assert corrida.bolsa_de_egresos[0] == pytest.approx(1_000_000.0)

    def test_la_bolsa_de_egresos_no_vuelve_al_flujo(self, con_capital_de_trabajo: Corrida) -> None:
        # Sus componentes ya llegan cada uno por su linea: si volviera, el
        # capital se contaria dos veces.
        corrida = con_capital_de_trabajo
        contrastar(
            corrida.flujo.flujo_de_inversiones,
            tuple(-c for c in corrida.capex),
            "flujo de inversiones",
        )

    def test_las_cuentas_se_liquidan_en_el_ultimo_ano_con_produccion(
        self, con_capital_de_trabajo: Corrida
    ) -> None:
        # Regla 053: la bandera es el ano con produccion, no la venta. Con la
        # bandera de venta, la parada del tercer ejercicio pasaria por fin de
        # vida util y liquidaria las cuentas un ano antes.
        cobrar = con_capital_de_trabajo.cuentas_por_cobrar.variaciones
        # La cartera se abre en el segundo ejercicio, se cobra al cerrar la
        # racha y **la parada no mueve nada**: el libro multiplica la fila por
        # la bandera del ano, y sin eso el saldo se recuperaria dos veces.
        assert cobrar[1] == pytest.approx(-100_000.0)
        assert cobrar[2] == pytest.approx(100_000.0)
        assert cobrar[3] == pytest.approx(0.0)

    def test_el_ciclo_cierra_salvo_lo_que_abre_antes_de_producir(
        self, con_capital_de_trabajo: Corrida
    ) -> None:
        """Un ciclo que se abre y se cierra no crea ni destruye caja.

        Es la comprobacion que delata una bandera equivocada sin tener el libro
        delante: con la bandera de venta, la cartera no cierra.
        """
        corrida = con_capital_de_trabajo
        assert coincide(sum(corrida.cuentas_por_cobrar.variaciones), 0.0)

        # La deuda deja un residuo, y es exactamente el saldo que abrio el
        # capital del primer ejercicio, cuando la unidad todavia no producia:
        # el libro multiplica la fila por la bandera del ano, de modo que esa
        # apertura no entra al flujo y su reduccion posterior si. Es la regla
        # 056, reproducida y reportada.
        pagar = corrida.cuentas_por_pagar
        assert coincide(sum(pagar.variaciones), -pagar.saldos[0])
        assert pagar.saldos[0] > 0.0

    def test_el_igv_se_calcula_y_no_mueve_el_flujo(self, con_capital_de_trabajo: Corrida) -> None:
        # Regla 014, sobre la corrida entera: el bloque tiene cifras y su
        # variacion llega al flujo multiplicada por cero.
        corrida = con_capital_de_trabajo
        assert any(x != 0.0 for x in corrida.igv.igv_de_compras)
        assert any(x != 0.0 for x in corrida.igv.credito_acumulado)
        contrastar(
            corrida.igv.variacion_para_el_flujo,
            corrida.caso.horizonte.ceros(),
            "variacion de IGV en el flujo",
        )

    def test_las_otras_cuentas_entran_al_capital_de_trabajo(
        self, con_capital_de_trabajo: Corrida
    ) -> None:
        # Son saldos y el libro los suma junto a las variaciones (regla 050).
        corrida = con_capital_de_trabajo
        otras = sinteticos.OTRAS_POR_COBRAR + sinteticos.OTRAS_POR_PAGAR
        esperada = tuple(
            corrida.cuentas_por_cobrar.variaciones[i]
            + corrida.cuentas_por_pagar.variaciones[i]
            + otras
            for i in range(corrida.caso.horizonte.anos)
        )
        contrastar(corrida.variacion_capital_trabajo, esperada, "variacion de capital de trabajo")

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

    def test_la_via_financiera_agota_el_capital_contra_las_reservas(
        self, con_agotamiento: Corrida
    ) -> None:
        # Edificaciones de 1 000 000 contra un saldo de 4 000, 3 000 y 2 000 t:
        # se agota un cuarto del saldo en el segundo ejercicio -250 000- y un
        # tercio de los 750 000 que quedan en el tercero, otros 250 000. La
        # maquinaria no se agota: sigue lineal al 50 %, igual que en la otra via.
        componentes = con_agotamiento.depreciacion_financiera_por_componente["Mina Larga"]
        contrastar(componentes["edificaciones"], (0.0, 250_000.0, 250_000.0, 0.0), "agotamiento")
        contrastar(componentes["maquinaria"], (0.0, 200_000.0, 0.0, 0.0), "maquinaria financiera")

    def test_la_via_tributaria_reparte_el_mismo_capital_lineal(
        self, con_agotamiento: Corrida
    ) -> None:
        # Las mismas edificaciones, al 5 % anual desde el primer ano con
        # produccion. El metodo, no la tasa, es lo que separa a las dos vias.
        componentes = con_agotamiento.depreciacion_tributaria_por_componente["Mina Larga"]
        contrastar(
            componentes["edificaciones"],
            (0.0, 50_000.0, 50_000.0, 50_000.0),
            "edificaciones tributaria",
        )
        contrastar(componentes["maquinaria"], (0.0, 200_000.0, 0.0, 0.0), "maquinaria tributaria")

    def test_un_ano_sin_produccion_pierde_la_cuota_financiera(
        self, con_agotamiento: Corrida
    ) -> None:
        # Regla 041: la tributaria acumula y desde el primer ano con produccion
        # deprecia siempre; la financiera cierra ano a ano con la bandera del
        # libro. El cuarto ejercicio no produce, y ahi las dos se separan.
        contrastar(
            con_agotamiento.depreciacion_tributaria_por_mina["Mina Larga"],
            (0.0, 250_000.0, 50_000.0, 50_000.0),
            "depreciacion tributaria",
        )
        contrastar(
            con_agotamiento.depreciacion_financiera_por_mina["Mina Larga"],
            (0.0, 450_000.0, 250_000.0, 0.0),
            "depreciacion financiera",
        )

    def test_el_agotamiento_se_detiene_al_acabarse_las_reservas(
        self, con_agotamiento: Corrida
    ) -> None:
        # Sin reservas declaradas son las 1 000 t que extrae el plan: se agota
        # la mitad del saldo en el tercer ejercicio y el 100 % en el cuarto, de
        # modo que el activo queda en cero justo cuando se acaba el yacimiento.
        financiera = con_agotamiento.depreciacion_financiera_por_mina["Proyecto Y"]
        contrastar(financiera, (0.0, 0.0, 300_000.0, 300_000.0), "agotamiento Proyecto Y")
        assert coincide(sum(financiera), 600_000.0), "el agotamiento no reparte todo el capital"
        contrastar(
            con_agotamiento.depreciacion_tributaria_por_mina["Proyecto Y"],
            (0.0, 0.0, 60_000.0, 60_000.0),
            "depreciacion tributaria Proyecto Y",
        )


# --- N2 · flujos ---------------------------------------------------------------


class TestN2:
    """Los tres escalones del flujo, contrastados y consistentes entre sí."""

    def test_la_liquidacion_del_concentrado_llega_al_flujo(self, polimetalico: Corrida) -> None:
        # Sin este escalon, un error en la liquidacion se compensa aguas abajo y
        # no se ve: el EBITDA arranca de la venta, y la venta del caso es toda
        # concentrado.
        cash_cost = 1_400_000.0
        ventas = polimetalico.ventas[1]
        participacion = polimetalico.participacion_trabajadores[1]
        fondo = polimetalico.tributos_por_ano[1].fondo_jubilacion_minera
        esperado = ventas - cash_cost - participacion - fondo
        contrastar(polimetalico.flujo.ebitda_ajustado[1:2], (esperado,), "EBITDA del polimetalico")

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

    def test_el_agotamiento_llega_al_flujo(self, con_agotamiento: Corrida) -> None:
        # La depreciacion financiera no es una linea de caja, pero manda en la
        # base operativa que determina la regalia y el fondo de jubilacion: si
        # el agotamiento no llegara hasta aqui, el flujo no lo delataria.
        contrastar(
            con_agotamiento.flujo.flujo_de_inversiones,
            (-1_400_000.0, -600_000.0, 0.0, 0.0),
            "flujo de inversiones",
        )
        contrastar(
            con_agotamiento.flujo.flujo_economico,
            (-1_400_000.0, 507_949.75, 1_313_064.875, 293_846.375),
            "flujo economico",
        )


# --- N3 · indicadores ----------------------------------------------------------


class TestN3:
    """Las cuatro cifras que el cliente mira, con sus propias tolerancias."""

    def test_el_concentrado_mueve_el_npv(self, polimetalico: Corrida) -> None:
        # Quitar las condiciones del concentrado deja el caso sin venta: si el
        # NPV no se moviera, la liquidacion no estaria llegando al flujo.
        sin_venta = calcular(_sin_concentrado(sinteticos.caso_polimetalico()), sinteticos.MAESTROS)
        assert polimetalico.indicadores.npv > sin_venta.indicadores.npv
        assert not coincide(polimetalico.indicadores.npv, sin_venta.indicadores.npv)

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

    def test_npv_del_caso_con_agotamiento(self, con_agotamiento: Corrida) -> None:
        esperado = -1_400_000.0 + 507_949.75 / 1.1 + 1_313_064.875 / 1.21 + 293_846.375 / 1.331
        assert coincide(con_agotamiento.indicadores.npv, esperado), (
            f"NPV: se obtuvo {con_agotamiento.indicadores.npv:,.2f} y se esperaba {esperado:,.2f}"
        )

    def test_un_caso_sin_desembolso_no_define_tir(self, con_refineria: Corrida) -> None:
        # La refinería no declara capital: su flujo no cambia de signo y la TIR
        # no existe. Informarlo es mejor que devolver un numero.
        assert con_refineria.indicadores.tir is None
