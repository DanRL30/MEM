"""Pruebas de la carga local y de los bloques intermedios.

Cubren el recorrido que hace la interfaz de modelamiento de escenario: crear el
caso, subir la plantilla, calcular y recorrer la cadena hoja por hoja.

Y cubren sobre todo el limite: la carga por la API existe solo en local, y los
datos maestros de desarrollo tambien. Si esa frontera se borrara sin que nadie
lo notara, un entorno del cliente acabaria calculando con parametros que MINSUR
no ha confirmado, que es exactamente lo que `R-32` impide.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from minsur_api import maestros_desarrollo
from minsur_api.dependencias import datos_maestros, repositorio
from minsur_api.main import crear_app
from minsur_api.repositorio import RepositorioEnMemoria

CABECERAS = {"Authorization": "Bearer token-de-desarrollo"}
RAIZ = Path(__file__).resolve().parents[3]
RUTA_DE_CARGA = "/api/desarrollo/casos/CASO-XX-2026-000000/insumos"

# La cadena de una mina, en el orden en que la plantilla pide las filas. El
# primer ejercicio invierte y no produce.
CADENA = [
    1_000.0,  # Mineral extraido
    0.02,  # Ley Sn de cabeza
    1_000.0,  # Mineral tratado en preconcentracion
    0.02,  # Ley de Sn de entrada
    500.0,  # Mineral preconcentrado
    0.03,  # Ley Sn del preconcentrado
    0.0,  # Mineral directo
    0.0,  # Ley de Sn del directo
    500.0,  # Mineral tratado total
    0.03,  # Ley Sn del tratado total
    500.0,  # Mineral tratado total para cash cost
    0.03,  # Ley Sn del cash cost
    13.5,  # Toneladas finas
    0.30,  # Ley Sn del concentrado
    90.0,  # Recuperacion Sn
    45.0,  # Produccion Concentrado
    0.0,  # Concentrado producido Cu
    0.0,  # Ley Cu
    0.0,  # Ley Ag
]


def _generador() -> object:
    """Importa el script que emite la plantilla, que no es un paquete."""
    ruta = RAIZ / "scripts" / "generar_plantilla_inputs.py"
    especificacion = importlib.util.spec_from_file_location("generador", ruta)
    assert especificacion is not None and especificacion.loader is not None
    modulo = importlib.util.module_from_spec(especificacion)
    sys.modules["generador"] = modulo
    especificacion.loader.exec_module(modulo)
    return modulo


def _escribir(hoja: object, etiqueta: str, valores: list[float]) -> None:
    for fila in hoja.iter_rows(min_row=5, max_col=1):  # type: ignore[attr-defined]
        celda = fila[0]
        if celda.value and str(celda.value).strip() == etiqueta.strip():
            for i, valor in enumerate(valores):
                hoja.cell(row=celda.row, column=3 + i, value=valor)  # type: ignore[attr-defined]
            return
    raise AssertionError(f"la plantilla no tiene la fila {etiqueta!r}")


def _llenar_cadena(hoja: object, anos: int = 3) -> None:
    """Llena la pestaña por posición, que es como se lee."""
    fila = 5
    for valor in CADENA:
        while not hoja.cell(row=fila, column=2).value:  # type: ignore[attr-defined]
            fila += 1
        for i in range(anos):
            hoja.cell(row=fila, column=3 + i, value=0.0 if i == 0 else valor)  # type: ignore[attr-defined]
        fila += 1


@pytest.fixture
def plantilla(tmp_path: Path) -> Path:
    """Un libro de una mina y una refinería, con la cadena llena."""
    generador = _generador()
    ruta = tmp_path / "caso.xlsx"
    unidades = generador._encadenar(  # type: ignore[attr-defined]
        [
            generador.Unidad.desde_texto("Mina Alfa:mina:Sn"),  # type: ignore[attr-defined]
            generador.Unidad.desde_texto("Refineria:refineria:Sn"),  # type: ignore[attr-defined]
        ]
    )
    libro = generador.Workbook()  # type: ignore[attr-defined]
    generador.hoja_caso(libro, unidades, 2027, 3)  # type: ignore[attr-defined]
    generador.hoja_produccion_de_unidad(libro, "Mina Alfa", 2027, 3)  # type: ignore[attr-defined]
    generador.hoja_precios(libro, unidades, 2027, 3)  # type: ignore[attr-defined]
    libro.save(ruta)

    libro = load_workbook(ruta)
    libro["Caso"]["B3"] = "Escenario de prueba"
    libro["Caso"]["B9"] = "CP-2026-09"
    _llenar_cadena(libro["Mina Alfa"])
    _escribir(libro["Precios"], "Precio, escenario Base", [10_000.0] * 3)
    _escribir(libro["Precios"], "Factor de metal pagable", [0.9] * 3)
    libro.save(ruta)
    return ruta


@pytest.fixture
def repo() -> RepositorioEnMemoria:
    return RepositorioEnMemoria()


@pytest.fixture
def cliente(repo: RepositorioEnMemoria) -> Iterator[TestClient]:
    app = crear_app()
    app.dependency_overrides[repositorio] = lambda: repo
    with TestClient(app) as instancia:
        yield instancia
    app.dependency_overrides.clear()


def _crear_caso(cliente: TestClient) -> str:
    respuesta = cliente.post(
        "/api/casos",
        json={"nombre": "Escenario de prueba", "tipo": "monometalico", "descripcion": "Prueba"},
        headers=CABECERAS,
    )
    assert respuesta.status_code == 201, respuesta.text
    return str(respuesta.json()["id_caso"])


def _subir(cliente: TestClient, id_caso: str, ruta: Path) -> dict[str, object]:
    with ruta.open("rb") as archivo:
        respuesta = cliente.post(
            f"/api/desarrollo/casos/{id_caso}/insumos",
            files={"caso": (ruta.name, archivo, "application/vnd.ms-excel")},
            headers=CABECERAS,
        )
    assert respuesta.status_code == 200, respuesta.text
    resultado: dict[str, object] = respuesta.json()
    return resultado


class TestLaFronteraDeLoLocal:
    def test_en_local_los_datos_maestros_son_los_de_desarrollo(self) -> None:
        maestros = datos_maestros()
        assert maestros is not None
        assert maestros.version == maestros_desarrollo.VERSION == "DEV-0"

    def test_fuera_de_local_no_hay_datos_maestros(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Es la garantia que sostiene `R-32`: los parametros los confirma MINSUR
        # y ningun entorno del cliente puede calcular sin ellos.
        monkeypatch.setattr("minsur_api.dependencias.config", lambda: _ConfigRemota())
        assert datos_maestros() is None

    def test_fuera_de_local_la_carga_por_la_api_no_existe(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Se comprueba por comportamiento y no por introspeccion: la ruta esta
        # fuera del esquema a proposito, y `app.routes` conserva los routers sin
        # desplegar en esta version de FastAPI. Un 404 es la ausencia; un 422
        # seria la ruta existiendo y rechazando el cuerpo.
        monkeypatch.setattr("minsur_api.main.config", lambda: _ConfigRemota())
        with TestClient(crear_app()) as remoto:
            respuesta = remoto.post(RUTA_DE_CARGA, headers=CABECERAS)
        assert respuesta.status_code == 404

    def test_en_local_la_carga_esta_montada_y_fuera_del_contrato(self, cliente: TestClient) -> None:
        assert cliente.post(RUTA_DE_CARGA, headers=CABECERAS).status_code == 422

        # De este esquema salen los tipos del frontend y la definicion que se
        # importa a API Management. Una ruta que solo existe en la maquina del
        # desarrollador no pertenece a ese contrato.
        rutas = crear_app().openapi()["paths"]
        assert not [ruta for ruta in rutas if "desarrollo" in ruta]
        assert "/api/casos" in rutas, "el resto de la API sigue publicada"


class _ConfigRemota:
    """Lo mínimo que las dependencias consultan de la configuración."""

    entorno = "qa"
    es_local = False


class TestCargaDeInsumos:
    def test_la_plantilla_llena_deja_el_caso_calculable(
        self, cliente: TestClient, plantilla: Path
    ) -> None:
        id_caso = _crear_caso(cliente)
        resultado = _subir(cliente, id_caso, plantilla)

        assert resultado["valida"] is True, resultado["hallazgos"]
        assert resultado["incidencias"] == []
        assert int(str(resultado["filas_leidas"])) > 0
        assert len(str(resultado["huella"])) == 64

        respuesta = cliente.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS)
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["terna"]["datos_maestros"] == "DEV-0"

    def test_la_revision_de_inputs_sube_con_cada_carga(
        self, cliente: TestClient, repo: RepositorioEnMemoria, plantilla: Path
    ) -> None:
        id_caso = _crear_caso(cliente)
        _subir(cliente, id_caso, plantilla)
        primera = repo.obtener(id_caso).revision_inputs
        _subir(cliente, id_caso, plantilla)
        assert repo.obtener(id_caso).revision_inputs == primera + 1

    def test_un_archivo_ilegible_devuelve_la_incidencia_con_su_hoja(
        self, cliente: TestClient, tmp_path: Path
    ) -> None:
        id_caso = _crear_caso(cliente)
        roto = tmp_path / "roto.xlsx"
        roto.write_bytes(b"esto no es un libro de Excel")
        with roto.open("rb") as archivo:
            respuesta = cliente.post(
                f"/api/desarrollo/casos/{id_caso}/insumos",
                files={"caso": (roto.name, archivo, "application/vnd.ms-excel")},
                headers=CABECERAS,
            )
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["valida"] is False
        assert cuerpo["incidencias"], "una lectura fallida tiene que decir por que"
        assert set(cuerpo["incidencias"][0]) >= {"hoja", "celda", "mensaje"}

    def test_un_caso_inexistente_no_admite_carga(
        self, cliente: TestClient, plantilla: Path
    ) -> None:
        with plantilla.open("rb") as archivo:
            respuesta = cliente.post(
                "/api/desarrollo/casos/CASO-XX-2026-000000/insumos",
                files={"caso": (plantilla.name, archivo, "application/vnd.ms-excel")},
                headers=CABECERAS,
            )
        assert respuesta.status_code == 404


class TestBloquesIntermedios:
    def test_los_bloques_van_en_el_orden_del_libro(
        self, cliente: TestClient, plantilla: Path
    ) -> None:
        id_caso = _crear_caso(cliente)
        _subir(cliente, id_caso, plantilla)
        cliente.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS)

        respuesta = cliente.get(f"/api/casos/{id_caso}/corrida/bloques", headers=CABECERAS)
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()

        # `Depreciacion` va antes que `Ventas` porque asi esta en el libro,
        # aunque la cadena de calculo no lo exija. Es el orden aprendido.
        assert [b["clave"] for b in cuerpo["bloques"]] == [
            "produccion",
            "refineria",
            "opex",
            "capex",
            "depreciacion",
            "ventas",
            "otros",
            "impuestos",
            "flujo",
        ]
        assert [b["hoja"] for b in cuerpo["bloques"]][:5] == [
            "InputsProd",
            "InputsProd",
            "InputsOpex",
            "InputsCapex",
            "Depreciacion",
        ]

    def test_cada_serie_tiene_un_valor_por_ano(self, cliente: TestClient, plantilla: Path) -> None:
        id_caso = _crear_caso(cliente)
        _subir(cliente, id_caso, plantilla)
        cliente.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS)
        cuerpo = cliente.get(f"/api/casos/{id_caso}/corrida/bloques", headers=CABECERAS).json()

        anios = len(cuerpo["anios"])
        assert anios == 3
        for bloque in cuerpo["bloques"]:
            for serie in bloque["series"]:
                assert len(serie["valores"]) == anios, (bloque["clave"], serie["concepto"])

    def test_la_produccion_trae_su_recalculo_para_contrastar(
        self, cliente: TestClient, plantilla: Path
    ) -> None:
        # Es la alerta de control de calidad: sin el valor recalculado al lado,
        # una diferencia no dice que esperaba el sistema.
        id_caso = _crear_caso(cliente)
        _subir(cliente, id_caso, plantilla)
        cliente.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS)
        cuerpo = cliente.get(f"/api/casos/{id_caso}/corrida/bloques", headers=CABECERAS).json()

        produccion = next(b for b in cuerpo["bloques"] if b["clave"] == "produccion")
        con_recalculo = [s for s in produccion["series"] if s["recalculada"] is not None]
        assert con_recalculo, "ninguna fila de produccion trae su recalculo"
        assert all(s["origen"] == "dato" for s in produccion["series"])

    def test_los_campos_con_dato_los_decide_el_motor(
        self, cliente: TestClient, plantilla: Path
    ) -> None:
        id_caso = _crear_caso(cliente)
        _subir(cliente, id_caso, plantilla)
        cliente.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS)
        cuerpo = cliente.get(f"/api/casos/{id_caso}/corrida/bloques", headers=CABECERAS).json()

        assert "Mina Alfa" in cuerpo["campos_con_dato"]
        assert "mineral_extraido" in cuerpo["campos_con_dato"]["Mina Alfa"]

    def test_un_caso_sin_corrida_no_tiene_bloques(self, cliente: TestClient) -> None:
        id_caso = _crear_caso(cliente)
        respuesta = cliente.get(f"/api/casos/{id_caso}/corrida/bloques", headers=CABECERAS)
        assert respuesta.status_code == 409


class TestLaTirNoFingeUnCero:
    def test_un_caso_sin_desembolso_declara_que_no_tiene_tir(
        self, cliente: TestClient, plantilla: Path
    ) -> None:
        # La plantilla no declara capital, asi que el flujo no abre con
        # desembolso y no hay tasa que describa una rentabilidad. El libro
        # escribe un guion; el contrato escribe nulo. Lo decide el ADR 0011.
        id_caso = _crear_caso(cliente)
        _subir(cliente, id_caso, plantilla)
        respuesta = cliente.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS)
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["indicadores"]["tir"] is None
