"""Pruebas del bloque del complejo.

La que más importa es la de la regla de oro: **nada se agrupa**. Cada unidad
entra con su propia recuperación y su aporte al refinado se calcula por separado.
El libro corporativo agrupa —una `Recuperación Sn SR + B2` y otra `NZ + SRP`— y
las dos pruebas de `TestReglaDeOro` fijan por qué eso no se reproduce: un total
agregado no se puede atribuir a una unidad, y un proyecto nuevo no cabe en un
grupo sin decidir a cuál se parece.
"""

from __future__ import annotations

import pytest

from minsur_engine.complejo import Componente, calcular
from minsur_engine.horizonte import Horizonte

HORIZONTE = Horizonte(primer_ano=2027, anos=2)


def _componente(nombre: str, concentrado: float, ley: float, recuperacion: float) -> Componente:
    return Componente(
        unidad=nombre,
        concentrado=(concentrado, concentrado),
        ley=(ley, ley),
        recuperacion=(recuperacion, recuperacion),
    )


class TestReglaDeOro:
    def test_cada_unidad_aporta_con_su_propia_recuperacion(self) -> None:
        # 600 t al 40 % con 90 % de recuperacion dan 216 tmf; 400 t al 30 % con
        # 70 % dan 84. El total son 300, y cada aporte queda a la vista.
        bloque = calcular(
            HORIZONTE,
            [_componente("Alfa", 600.0, 0.40, 0.90), _componente("Beta", 400.0, 0.30, 0.70)],
        )
        por_unidad = {a.unidad: a.refinado[0] for a in bloque.aportes}
        assert por_unidad == {"Alfa": pytest.approx(216.0), "Beta": pytest.approx(84.0)}
        assert bloque.refinado_sin_restriccion[0] == pytest.approx(300.0)

    def test_agrupar_daria_otro_numero(self) -> None:
        # Es la prueba de que la regla importa. Con una sola recuperacion para
        # las dos —el promedio simple, 80 %— el refinado saldria 288 en vez de
        # 300: una diferencia del 4 % que ningun total permite atribuir.
        bloque = calcular(
            HORIZONTE,
            [_componente("Alfa", 600.0, 0.40, 0.90), _componente("Beta", 400.0, 0.30, 0.70)],
        )
        agrupado = (600.0 * 0.40 + 400.0 * 0.30) * 0.80
        assert agrupado == pytest.approx(288.0)
        assert bloque.refinado_sin_restriccion[0] != pytest.approx(agrupado)

    def test_una_unidad_sin_recuperacion_no_contamina_a_las_demas(self) -> None:
        # Si el complejo no declara la recuperacion de una unidad, esa aporta
        # cero y las otras conservan la suya. Repartir una recuperacion media
        # entre todas ocultaria el dato que falta.
        bloque = calcular(
            HORIZONTE,
            [
                _componente("Alfa", 600.0, 0.40, 0.90),
                Componente(unidad="Beta", concentrado=(400.0, 400.0), ley=(0.30, 0.30)),
            ],
        )
        por_unidad = {a.unidad: a.refinado[0] for a in bloque.aportes}
        assert por_unidad["Alfa"] == pytest.approx(216.0)
        assert por_unidad["Beta"] == 0.0


class TestLoQueEntra:
    def test_el_alimentado_es_la_suma_acotada_por_la_capacidad(self) -> None:
        bloque = calcular(
            HORIZONTE,
            [_componente("Alfa", 600.0, 0.40, 0.90), _componente("Beta", 400.0, 0.30, 0.70)],
            capacidad=(900.0, 900.0),
        )
        assert bloque.concentrado_entregado[0] == pytest.approx(1_000.0)
        assert bloque.concentrado_alimentado[0] == pytest.approx(900.0)
        assert bloque.concentrado_excedente[0] == pytest.approx(100.0)

    def test_sin_capacidad_declarada_no_hay_cuello_de_botella(self) -> None:
        bloque = calcular(HORIZONTE, [_componente("Alfa", 600.0, 0.40, 0.90)])
        assert bloque.concentrado_alimentado[0] == pytest.approx(600.0)
        assert bloque.concentrado_excedente[0] == 0.0

    def test_la_ley_de_alimentacion_se_pondera_por_tonelaje(self) -> None:
        # 600 t al 40 % y 400 al 30 % dan 36 %, no el 35 % del promedio simple.
        bloque = calcular(
            HORIZONTE,
            [_componente("Alfa", 600.0, 0.40, 0.90), _componente("Beta", 400.0, 0.30, 0.70)],
        )
        assert bloque.ley_de_alimentacion[0] == pytest.approx(0.36)

    def test_el_check_del_libro_cierra_en_cero(self) -> None:
        bloque = calcular(
            HORIZONTE,
            [_componente("Alfa", 600.0, 0.40, 0.90), _componente("Beta", 400.0, 0.30, 0.70)],
            capacidad=(900.0, 900.0),
        )
        assert bloque.check == (0.0, 0.0)


class TestRepartoPorMerito:
    """Cuando el complejo se satura, quien se queda fuera cambia el resultado."""

    def test_va_a_spot_primero_el_concentrado_de_menor_ley(self) -> None:
        # Se refina el mejor concentrado y se vende el peor. Beta esta al 30 %
        # y Alfa al 40 %, asi que las 100 t que sobran salen de Beta.
        bloque = calcular(
            HORIZONTE,
            [_componente("Alfa", 600.0, 0.40, 0.90), _componente("Beta", 400.0, 0.30, 0.70)],
            capacidad=(900.0, 900.0),
        )
        a_spot = {a.unidad: a.a_spot[0] for a in bloque.aportes}
        assert a_spot == {"Alfa": 0.0, "Beta": pytest.approx(100.0)}

    def test_el_recorte_pasa_a_la_siguiente_cuando_una_no_alcanza(self) -> None:
        # Si el excedente supera lo que entrega la de menor ley, la que sigue
        # cede el resto. Beta entrega 400 y sobran 500: cede todo y Alfa 100.
        bloque = calcular(
            HORIZONTE,
            [_componente("Alfa", 600.0, 0.40, 0.90), _componente("Beta", 400.0, 0.30, 0.70)],
            capacidad=(500.0, 500.0),
        )
        a_spot = {a.unidad: a.a_spot[0] for a in bloque.aportes}
        assert a_spot == {"Alfa": pytest.approx(100.0), "Beta": pytest.approx(400.0)}

    def test_el_refinado_descuenta_lo_que_fue_a_spot(self) -> None:
        # Alfa refina sus 600 t enteras; Beta solo 300 de sus 400.
        bloque = calcular(
            HORIZONTE,
            [_componente("Alfa", 600.0, 0.40, 0.90), _componente("Beta", 400.0, 0.30, 0.70)],
            capacidad=(900.0, 900.0),
        )
        por_unidad = {a.unidad: a.refinado[0] for a in bloque.aportes}
        assert por_unidad == {"Alfa": pytest.approx(216.0), "Beta": pytest.approx(63.0)}
        assert bloque.refinado[0] == pytest.approx(279.0)
        assert bloque.refinado_sin_restriccion[0] == pytest.approx(300.0)

    def test_el_empate_de_leyes_se_resuelve_igual_en_cada_corrida(self) -> None:
        # Sin desempate, dos corridas del mismo caso podrian repartir distinto.
        minas = [_componente("Beta", 400.0, 0.35, 0.70), _componente("Alfa", 400.0, 0.35, 0.90)]
        primera = calcular(HORIZONTE, minas, capacidad=(700.0, 700.0))
        segunda = calcular(HORIZONTE, list(reversed(minas)), capacidad=(700.0, 700.0))
        assert {a.unidad: a.a_spot[0] for a in primera.aportes} == {
            a.unidad: a.a_spot[0] for a in segunda.aportes
        }

    def test_sin_saturacion_nadie_cede_nada(self) -> None:
        bloque = calcular(
            HORIZONTE,
            [_componente("Alfa", 600.0, 0.40, 0.90), _componente("Beta", 400.0, 0.30, 0.70)],
            capacidad=(5_000.0, 5_000.0),
        )
        assert all(a.a_spot == (0.0, 0.0) for a in bloque.aportes)
        assert bloque.refinado == bloque.refinado_sin_restriccion


class TestVentaSpot:
    def test_el_excedente_se_valoriza_a_la_ley_de_lo_que_fue_a_spot(self) -> None:
        # Y no a la del conjunto. Con reparto por merito lo que sale es el
        # concentrado de menor ley, de modo que usar el promedio -0,36 aqui-
        # sobrestimaria el metal contenido en lo que se vende.
        bloque = calcular(
            HORIZONTE,
            [_componente("Alfa", 600.0, 0.40, 0.90), _componente("Beta", 400.0, 0.30, 0.70)],
            capacidad=(900.0, 900.0),
        )
        assert bloque.ley_de_alimentacion[0] == pytest.approx(0.36)
        assert bloque.ley_del_excedente[0] == pytest.approx(0.30)
        assert bloque.refinado_del_excedente[0] == pytest.approx(30.0)

    def test_no_lleva_factor_de_recuperacion(self) -> None:
        # Es metal contenido en concentrado, pese a que la fila del libro se
        # llame `Produccion Sn Refinado`. Regla 019: se reproduce y se reporta.
        bloque = calcular(
            HORIZONTE,
            [_componente("Beta", 400.0, 0.30, 0.70)],
            capacidad=(300.0, 300.0),
        )
        assert bloque.refinado_del_excedente[0] == pytest.approx(100.0 * 0.30)


class TestSinComponentes:
    def test_un_caso_sin_minas_no_revienta(self) -> None:
        bloque = calcular(HORIZONTE, [])
        assert bloque.concentrado_alimentado == HORIZONTE.ceros()
        assert bloque.ley_de_alimentacion == (0.0, 0.0)
        assert bloque.refinado_sin_restriccion == (0.0, 0.0)
