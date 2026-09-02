"""Pruebas de la lectura de plantillas.

La prueba que sostiene todo el paquete es la de ida y vuelta: se genera una
plantilla con el script que la emite, se llena, se lee y se comprueba que el
caso que sale es el que se escribió. Generador y lector son las dos mitades del
mismo contrato, y esta prueba falla en cuanto una se mueve sin la otra.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

from minsur_engine.caso import DatosMaestros
from minsur_engine.corrida import calcular
from minsur_engine.depreciacion import TasasDeDepreciacion
from minsur_engine.parametros import ParametrosCorporativos
from minsur_engine.tributos import EscalaProgresiva, Tramo
from minsur_ingest.incidencias import ErrorDePlantilla
from minsur_ingest.plantilla import Lectura, leer_o_fallar, leer_plantilla
from minsur_ingest.sinonimos import canonizar

RAIZ = Path(__file__).resolve().parents[3]

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


def _generador() -> object:
    """Importa el script que emite la plantilla, que no es un paquete."""
    ruta = RAIZ / "scripts" / "generar_plantilla_inputs.py"
    especificacion = importlib.util.spec_from_file_location("generador", ruta)
    assert especificacion is not None and especificacion.loader is not None
    modulo = importlib.util.module_from_spec(especificacion)
    sys.modules["generador"] = modulo
    especificacion.loader.exec_module(modulo)
    return modulo


def _escribir(hoja: object, etiqueta: str, valores: list[float]) -> int:
    """Llena la fila de un concepto y devuelve su número."""
    for fila in hoja.iter_rows(min_row=5, max_col=1):  # type: ignore[attr-defined]
        celda = fila[0]
        if celda.value and str(celda.value).strip() == etiqueta.strip():
            for i, valor in enumerate(valores):
                hoja.cell(row=celda.row, column=3 + i, value=valor)  # type: ignore[attr-defined]
            return int(celda.row)
    raise AssertionError(f"la plantilla no tiene la fila {etiqueta!r}")


@pytest.fixture
def plantilla_llena(tmp_path: Path) -> Path:
    """Una plantilla de dos unidades y tres años, con la cadena completa llena.

    Las cifras se eligen para seguirlas a mano y para que la cadena cuadre: 1 000
    toneladas al 25 % son 250 tmf; con 80 % de recuperación y un concentrado al
    40 % salen 500 toneladas de concentrado. El primer ejercicio invierte y no
    produce.

    Llenar la cadena entera y no solo las cuatro filas que el motor consumía
    antes es lo que hace que la prueba cubra el vocabulario real de la plantilla.
    """
    generador = _generador()
    ruta = tmp_path / "caso.xlsx"
    unidades = generador._encadenar(  # type: ignore[attr-defined]
        [
            generador.Unidad.desde_texto("Mina Alfa:mina:Sn"),  # type: ignore[attr-defined]
            generador.Unidad.desde_texto("Fundicion:fundicion:Sn"),  # type: ignore[attr-defined]
        ]
    )
    libro = generador.Workbook()  # type: ignore[attr-defined]
    generador.hoja_caso(libro, unidades, 2027, 3)  # type: ignore[attr-defined]
    for unidad in unidades:
        generador.hoja_produccion_de_unidad(  # type: ignore[attr-defined]
            libro, unidad, unidades, 2027, 3
        )
    generador.hoja_opex(libro, unidades, 2027, 3)  # type: ignore[attr-defined]
    generador.hoja_capex(libro, unidades, 2027, 3)  # type: ignore[attr-defined]
    generador.hoja_precios(libro, unidades, 2027, 3)  # type: ignore[attr-defined]
    generador.hoja_instrucciones(libro, unidades)  # type: ignore[attr-defined]
    libro.save(ruta)

    libro = load_workbook(ruta)
    caso = libro["Caso"]
    caso["B3"] = "Caso de prueba"
    caso["B9"] = "CP-2026-09"

    mina = libro["Mina Alfa"]
    _escribir(mina, "Mineral extraido", [0.0, 1_200.0, 1_200.0])
    _escribir(mina, "Ley de Sn del mineral extraido", [0.0, 25.0, 25.0])
    _escribir(mina, "Mineral directo a planta concentradora", [0.0, 1_000.0, 1_000.0])
    _escribir(mina, "Ley de Sn del mineral directo", [0.0, 25.0, 25.0])
    _escribir(mina, "Mineral tratado total en concentradora", [0.0, 1_000.0, 1_000.0])
    _escribir(mina, "Ley de Sn del tratado total", [0.0, 25.0, 25.0])
    _escribir(mina, "Mineral tratado total para cash cost", [0.0, 1_000.0, 1_000.0])
    _escribir(mina, "Ley de Sn del tratado para cash cost", [0.0, 25.0, 25.0])
    _escribir(mina, "Toneladas finas de Sn", [0.0, 250.0, 250.0])
    _escribir(mina, "Ley de Sn en el concentrado", [0.0, 40.0, 40.0])
    _escribir(mina, "Recuperacion de Sn", [0.0, 80.0, 80.0])
    _escribir(mina, "Produccion de concentrado de Sn", [0.0, 500.0, 500.0])
    _escribir(mina, "Concentrado entregado al complejo", [0.0, 500.0, 500.0])

    complejo = libro["Fundicion"]
    _escribir(complejo, "Concentrado alimentado desde Mina Alfa", [0.0, 500.0, 500.0])
    _escribir(complejo, "Ley de Sn del concentrado de Mina Alfa", [0.0, 40.0, 40.0])
    _escribir(complejo, "Toneladas alimentadas mas escoria", [0.0, 520.0, 520.0])
    _escribir(complejo, "Capacidad maxima de tratamiento", [900.0, 900.0, 900.0])
    _escribir(complejo, "Concentrado excedente", [0.0, 0.0, 0.0])
    _escribir(complejo, "Ley promedio de alimentacion de Sn", [0.0, 40.0, 40.0])
    _escribir(complejo, "Produccion de metal refinado de Sn", [0.0, 100.0, 100.0])
    _escribir(complejo, "Recuperacion de Sn de Mina Alfa", [0.0, 90.0, 90.0])

    _escribir(libro["Opex"], "Mina", [0.0, 200_000.0, 200_000.0])
    _escribir(libro["Capex"], "    Maquinaria, equipos y vehiculos", [1_000_000.0, 0.0, 0.0])

    precios = libro["Precios"]
    _escribir(precios, "Precio, escenario Base", [10_000.0] * 3)
    _escribir(precios, "Factor de metal pagable", [0.9] * 3)
    libro.save(ruta)
    return ruta


class TestIdaYVuelta:
    def test_la_plantilla_llena_produce_un_caso(self, plantilla_llena: Path) -> None:
        lectura = leer_plantilla(plantilla_llena)
        assert lectura.valida, [str(i) for i in lectura.incidencias]
        caso = lectura.caso
        assert caso is not None
        assert caso.nombre == "Caso de prueba"
        assert caso.horizonte.primer_ano == 2027
        assert caso.horizonte.anos == 3
        assert [u.nombre for u in caso.unidades] == ["Mina Alfa", "Fundicion"]

    def test_las_series_llegan_como_se_escribieron(self, plantilla_llena: Path) -> None:
        caso = leer_o_fallar(plantilla_llena)
        alfa = caso.unidades[0]
        assert alfa.produccion.mineral_tratado == (0.0, 1_000.0, 1_000.0)
        assert alfa.produccion.concentrado_producido == (0.0, 500.0, 500.0)
        assert alfa.costos["mina"] == (0.0, 200_000.0, 200_000.0)

    def test_la_cadena_completa_llega_al_motor(self, plantilla_llena: Path) -> None:
        # Hasta el 01/09/2026 el lector consumia cinco series por unidad y
        # descartaba las dieciseis restantes. Esta prueba fija que la cadena
        # entera —tonelajes, leyes y concentrado por metal— llega entera.
        alfa = leer_o_fallar(plantilla_llena).unidades[0]
        produccion = alfa.produccion
        assert produccion.extraido is not None
        assert produccion.extraido.toneladas == (0.0, 1_200.0, 1_200.0)
        assert produccion.extraido.leyes["Sn"] == (0.0, 0.25, 0.25)
        assert produccion.tratado_total is not None
        assert produccion.tratado_total.toneladas == (0.0, 1_000.0, 1_000.0)
        assert produccion.leyes_del_tratado["Sn"] == (0.0, 0.25, 0.25)

        concentrado = produccion.concentrados["Sn"]
        assert concentrado.toneladas_finas == (0.0, 250.0, 250.0)
        assert concentrado.recuperacion == (0.0, 0.80, 0.80)
        assert concentrado.ley == (0.0, 0.40, 0.40)
        assert concentrado.toneladas == (0.0, 500.0, 500.0)

    def test_el_origen_y_las_etapas_sobreviven_la_ida_y_vuelta(self, plantilla_llena: Path) -> None:
        # Vivian en la hoja de instrucciones, que el lector no abre, de modo que
        # de una plantilla llena no se podia regenerar la misma plantilla.
        caso = leer_o_fallar(plantilla_llena)
        alfa = caso.unidades[0]
        assert alfa.origen == "yacimiento"
        assert alfa.etapas == ("concentradora",)
        assert alfa.entrega_a == "Fundicion"

    def test_el_complejo_sabe_de_donde_viene_lo_que_recibe(self, plantilla_llena: Path) -> None:
        fundicion = leer_o_fallar(plantilla_llena).fundicion
        assert fundicion is not None
        recibido = fundicion.produccion.alimentacion_recibida
        assert set(recibido) == {"Mina Alfa"}
        assert recibido["Mina Alfa"].toneladas == (0.0, 500.0, 500.0)
        assert fundicion.produccion.recuperacion_por_grupo["Mina Alfa"] == (0.0, 0.90, 0.90)

    def test_la_capacidad_llega_a_la_fundicion(self, plantilla_llena: Path) -> None:
        caso = leer_o_fallar(plantilla_llena)
        fundicion = caso.fundicion
        assert fundicion is not None
        assert fundicion.produccion.capacidad_de_tratamiento == (900.0, 900.0, 900.0)

    def test_el_capital_cuadra_en_sus_dos_clasificaciones(self, plantilla_llena: Path) -> None:
        # La hoja anida naturaleza dentro de etapa, asi que el mismo importe
        # alimenta ambas. Si no cuadraran, CapitalDeUnidad lo rechazaria.
        caso = leer_o_fallar(plantilla_llena)
        capital = caso.unidades[0].capital
        assert capital is not None
        assert capital.total_por_etapa() == pytest.approx(1_000_000.0)
        assert capital.por_naturaleza["maquinaria"][0] == pytest.approx(1_000_000.0)

    def test_el_caso_leido_se_puede_calcular(self, plantilla_llena: Path) -> None:
        # La prueba de que la frontera funciona: lo que sale de la ingesta
        # entra en el motor sin retoques.
        corrida = calcular(leer_o_fallar(plantilla_llena), MAESTROS)
        assert corrida.ventas[1] == pytest.approx(1_000_000.0)
        assert corrida.concentrado_tratado[1] == pytest.approx(500.0)


class TestConversionDeEscalas:
    def test_los_miles_de_dolares_se_convierten(self, plantilla_llena: Path) -> None:
        # Regla 003: el libro alterna dolares y miles de dolares. La conversion
        # ocurre aqui y no se propaga al motor.
        libro = load_workbook(plantilla_llena)
        hoja = libro["Opex"]
        for fila in hoja.iter_rows(min_row=5, max_col=2):
            if fila[0].value and str(fila[0].value).strip() == "Mina":
                fila[1].value = "miles de US$"
                for i, valor in enumerate([0.0, 200.0, 200.0]):
                    hoja.cell(row=fila[0].row, column=3 + i, value=valor)
                break
        libro.save(plantilla_llena)

        caso = leer_o_fallar(plantilla_llena)
        assert caso.unidades[0].costos["mina"] == (0.0, 200_000.0, 200_000.0)


class TestIncidencias:
    def test_una_celda_con_texto_se_reporta_con_su_ubicacion(self, plantilla_llena: Path) -> None:
        libro = load_workbook(plantilla_llena)
        fila = _escribir(libro["Mina Alfa"], "Mineral tratado total para cash cost", [0.0] * 3)
        libro["Mina Alfa"].cell(row=fila, column=4, value="mil toneladas")
        libro.save(plantilla_llena)

        lectura = leer_plantilla(plantilla_llena)
        assert not lectura.valida
        incidencia = lectura.incidencias[0]
        assert incidencia.hoja == "Mina Alfa"
        assert incidencia.celda == f"D{fila}"
        assert "se esperaba un numero" in incidencia.mensaje

    def test_se_devuelven_todas_las_incidencias_juntas(self, plantilla_llena: Path) -> None:
        # Devolverlas de una en una obliga a corregir y reenviar tantas veces
        # como errores tenga la plantilla.
        libro = load_workbook(plantilla_llena)
        hoja = libro["Mina Alfa"]
        fila = _escribir(hoja, "Mineral tratado total para cash cost", [0.0] * 3)
        hoja.cell(row=fila, column=3, value="a")
        hoja.cell(row=fila, column=4, value="b")
        libro.save(plantilla_llena)

        lectura = leer_plantilla(plantilla_llena)
        assert len(lectura.incidencias) >= 2

    def test_un_concepto_que_no_se_reconoce_se_reporta(self, plantilla_llena: Path) -> None:
        # La regla invertida: antes una fila con concepto desconocido se
        # descartaba con un `continue`. El usuario la llenaba, el caso se leia
        # sin errores y su dato no se usaba, que es el peor fallo posible aqui.
        libro = load_workbook(plantilla_llena)
        hoja = libro["Mina Alfa"]
        fila = hoja.max_row + 1
        hoja.cell(row=fila, column=1, value="Mineral flotado en columna")
        hoja.cell(row=fila, column=2, value="t")
        hoja.cell(row=fila, column=3, value=10.0)
        libro.save(plantilla_llena)

        lectura = leer_plantilla(plantilla_llena)
        assert not lectura.valida
        assert any("no reconocido" in i.mensaje for i in lectura.incidencias)

    def test_una_unidad_declarada_sin_pestana_se_reporta(self, plantilla_llena: Path) -> None:
        libro = load_workbook(plantilla_llena)
        del libro["Mina Alfa"]
        libro.save(plantilla_llena)

        lectura = leer_plantilla(plantilla_llena)
        assert not lectura.valida
        assert any("no tiene pestana" in i.mensaje for i in lectura.incidencias)

    def test_un_libro_que_no_es_la_plantilla_se_rechaza(self, tmp_path: Path) -> None:
        from openpyxl import Workbook

        ruta = tmp_path / "otra_cosa.xlsx"
        Workbook().save(ruta)
        lectura = leer_plantilla(ruta)
        assert not lectura.valida
        assert "no es la canonica" in lectura.incidencias[0].mensaje

    def test_un_archivo_que_no_existe_no_revienta(self, tmp_path: Path) -> None:
        lectura = leer_plantilla(tmp_path / "fantasma.xlsx")
        assert not lectura.valida
        assert lectura.incidencias[0].mensaje == "no existe"

    def test_leer_o_fallar_levanta_con_todas(self, plantilla_llena: Path) -> None:
        libro = load_workbook(plantilla_llena)
        fila = _escribir(libro["Mina Alfa"], "Mineral tratado total para cash cost", [0.0] * 3)
        libro["Mina Alfa"].cell(row=fila, column=3, value="x")
        libro.save(plantilla_llena)

        with pytest.raises(ErrorDePlantilla, match="incidencia"):
            leer_o_fallar(plantilla_llena)


class TestSinonimos:
    def test_entiende_las_abreviaturas_del_libro(self) -> None:
        assert canonizar("LT")[0] == "linea de transmision"
        assert canonizar("Pta Subproductos")[0] == "planta de subproductos"

    def test_quita_el_nombre_de_la_unidad_pegado(self) -> None:
        # El libro pega el nombre de la unidad a la etiqueta. Y `Tratamiento de
        # Relaves B2` es una linea de costo operativo, no de produccion: hasta
        # el 01/09/2026 el sinonimo la mandaba a un concepto de tonelaje.
        concepto, _ = canonizar("Tratamiento de Relaves B2", unidades=["B2"])
        assert concepto == "relavera"

    def test_tolera_los_parentesis_del_libro(self) -> None:
        assert canonizar("Mineral Tratado Total (Cash Cost)")[0] == (
            "mineral tratado total para cash cost"
        )

    def test_separa_el_metal_del_concepto(self) -> None:
        assert canonizar("Ley de cabeza de Sn") == ("ley de cabeza", "Sn")
        assert canonizar("Recuperacion Cu") == ("recuperacion", "Cu")

    def test_un_concepto_sin_metal_no_inventa_uno(self) -> None:
        assert canonizar("Mineral extraido") == ("mineral extraido", None)


def test_la_lectura_declara_si_es_valida(plantilla_llena: Path) -> None:
    assert Lectura(None, ()).valida is False
    assert leer_plantilla(plantilla_llena).valida is True
