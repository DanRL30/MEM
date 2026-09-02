"""Pruebas de los endpoints que ya calculan.

Cubren el recorrido que la interfaz va a hacer: crear un caso, evaluarlo,
recalcularlo, abrir el tablero y consultar el historial. Y cubren también lo
que **no** se puede hacer todavía, porque un 501 que dejara de aparecer sin que
nadie lo note sería peor que el propio bloqueo: cada uno se comprueba con la
restricción que lo justifica.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from minsur_api.dependencias import datos_maestros, repositorio
from minsur_api.main import crear_app
from minsur_api.repositorio import CasoAlmacenado, RepositorioEnMemoria
from minsur_domain.estados import Estado
from minsur_engine.capex import CapitalDeUnidad
from minsur_engine.caso import (
    Caso,
    DatosComunes,
    DatosMaestros,
    ProduccionDeUnidad,
    TerminosComerciales,
    UnidadProductiva,
)
from minsur_engine.depreciacion import TasasDeDepreciacion
from minsur_engine.horizonte import Horizonte
from minsur_engine.impuestos import EscalaProgresiva, Tramo
from minsur_engine.parametros import ParametrosCorporativos

CABECERAS = {"Authorization": "Bearer token-de-desarrollo"}

MAESTROS = DatosMaestros(
    parametros=ParametrosCorporativos(
        version_datos_maestros="CP-2026-09",
        tasa_descuento=0.10,
        participacion_trabajadores=0.08,
        impuesto_renta=0.295,
        regalia_minima=0.01,
        osinergmin=0.0014,
        oefa=0.001,
        fondo_jubilacion_minera=0.005,
    ),
    tasas_tributarias=TasasDeDepreciacion(maquinaria=0.5, instalaciones=0.1, edificaciones=0.05),
    tasas_financieras=TasasDeDepreciacion(maquinaria=0.5, instalaciones=0.1, edificaciones=0.05),
    escala_regalia=EscalaProgresiva(tramos=(Tramo(0.0, 10.0, 0.01),)),
    escala_iem=EscalaProgresiva(tramos=(Tramo(0.0, 10.0, 0.0),)),
)


def caso_con_insumos() -> Caso:
    """Una mina que invierte el primer año y produce los dos siguientes."""
    horizonte = Horizonte(primer_ano=2027, anos=3)
    serie = horizonte.serie([1_000_000.0, 0.0, 0.0], nombre="capex")
    return Caso(
        nombre="Caso de prueba",
        horizonte=horizonte,
        unidades=(
            UnidadProductiva(
                nombre="Mina Alfa",
                tipo="mina",
                produccion=ProduccionDeUnidad(
                    mineral_tratado=horizonte.serie([0.0, 1_000.0, 1_000.0], nombre="tratado"),
                    concentrado_producido=horizonte.serie([0.0, 500.0, 500.0], nombre="conc"),
                    metal_refinado_vendido=horizonte.serie([0.0, 100.0, 100.0], nombre="fino"),
                ),
                costos={"Mina": horizonte.serie([0.0, 200_000.0, 200_000.0], nombre="mina")},
                capital=CapitalDeUnidad(
                    unidad="Mina Alfa",
                    por_etapa={"inicial": serie},
                    por_naturaleza={"maquinaria": serie},
                ),
            ),
        ),
        terminos=TerminosComerciales(
            precio_metal_refinado=horizonte.serie([10_000.0] * 3, nombre="precio"),
            premio_metal_refinado=horizonte.ceros(),
            precio_metal_en_concentrado=horizonte.ceros(),
            factor_metal_pagable=horizonte.ceros(),
        ),
        datos_comunes=DatosComunes(gastos_administrativos=horizonte.ceros()),
    )


@pytest.fixture
def repo() -> RepositorioEnMemoria:
    return RepositorioEnMemoria()


@pytest.fixture
def cliente(repo: RepositorioEnMemoria) -> Iterator[TestClient]:
    """Cliente con almacén limpio y datos maestros cargados."""
    app = crear_app()
    app.dependency_overrides[repositorio] = lambda: repo
    app.dependency_overrides[datos_maestros] = lambda: MAESTROS
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()


@pytest.fixture
def cliente_sin_maestros(repo: RepositorioEnMemoria) -> Iterator[TestClient]:
    """Cliente sin datos maestros: es el estado real mientras `R-32` siga abierta."""
    app = crear_app()
    app.dependency_overrides[repositorio] = lambda: repo
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()


def crear_caso(cliente: TestClient, nombre: str = "Nazareth 2038") -> str:
    respuesta = cliente.post(
        "/api/casos",
        json={"nombre": nombre, "tipo": "monometalico", "descripcion": "Caso de prueba"},
        headers=CABECERAS,
    )
    assert respuesta.status_code == 201, respuesta.text
    return str(respuesta.json()["id_caso"])


def con_insumos(repo: RepositorioEnMemoria, id_caso: str) -> None:
    """Carga los insumos como lo haría la ingesta tras confirmar una plantilla."""
    caso = repo.obtener(id_caso)
    repo.guardar(
        CasoAlmacenado(
            id_caso=caso.id_caso,
            nombre=caso.nombre,
            tipo=caso.tipo,
            descripcion=caso.descripcion,
            estado=caso.estado,
            actualizado_en=datetime.now(UTC),
            actualizado_por=caso.actualizado_por,
            insumos=caso_con_insumos(),
        )
    )


class TestCasos:
    def test_crear_devuelve_el_caso_en_borrador(self, cliente: TestClient) -> None:
        respuesta = cliente.post(
            "/api/casos",
            json={"nombre": "Nazareth 2038", "tipo": "monometalico"},
            headers=CABECERAS,
        )
        assert respuesta.status_code == 201
        cuerpo = respuesta.json()
        assert cuerpo["estado"] == Estado.BORRADOR
        assert cuerpo["id_caso"].startswith("CASO-MM-")
        assert cuerpo["terna"] is None

    def test_listar_devuelve_lo_creado(self, cliente: TestClient) -> None:
        crear_caso(cliente, "Uno")
        crear_caso(cliente, "Dos")
        respuesta = cliente.get("/api/casos", headers=CABECERAS)
        assert respuesta.status_code == 200
        assert {c["nombre"] for c in respuesta.json()} == {"Uno", "Dos"}

    def test_un_caso_inexistente_da_404(self, cliente: TestClient) -> None:
        respuesta = cliente.get("/api/casos/CASO-QUE-NO-EXISTE", headers=CABECERAS)
        assert respuesta.status_code == 404

    def test_duplicar_copia_los_insumos_y_nace_en_borrador(
        self, cliente: TestClient, repo: RepositorioEnMemoria
    ) -> None:
        original = crear_caso(cliente)
        con_insumos(repo, original)
        respuesta = cliente.post(
            "/api/casos",
            json={"nombre": "Copia", "tipo": "monometalico", "duplicar_de": original},
            headers=CABECERAS,
        )
        assert respuesta.status_code == 201
        copia = respuesta.json()["id_caso"]
        assert copia != original
        assert repo.obtener(copia).insumos is not None
        assert repo.obtener(copia).estado == Estado.BORRADOR

    def test_sin_token_no_se_entra(self, cliente: TestClient) -> None:
        assert cliente.get("/api/casos").status_code == 401


class TestEvaluacion:
    def test_un_caso_sin_insumos_no_se_puede_calcular(self, cliente: TestClient) -> None:
        id_caso = crear_caso(cliente)
        respuesta = cliente.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS)
        assert respuesta.status_code == 409
        assert "insumos" in respuesta.json()["detail"]["detalle"]

    def test_evaluar_devuelve_indicadores_y_terna(
        self, cliente: TestClient, repo: RepositorioEnMemoria
    ) -> None:
        id_caso = crear_caso(cliente)
        con_insumos(repo, id_caso)
        respuesta = cliente.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS)
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["estado"] == Estado.CALCULADA
        assert cuerpo["terna"]["datos_maestros"] == "CP-2026-09"
        assert len(cuerpo["terna"]["huella_inputs"]) == 64
        assert cuerpo["indicadores"]["npv_musd"] != 0.0

    def test_recalcular_crea_una_corrida_nueva_sin_tocar_la_anterior(
        self, cliente: TestClient, repo: RepositorioEnMemoria
    ) -> None:
        id_caso = crear_caso(cliente)
        con_insumos(repo, id_caso)
        primera = cliente.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS).json()
        segunda = cliente.post(f"/api/casos/{id_caso}/recalcular", headers=CABECERAS).json()

        assert segunda["id_corrida"] != primera["id_corrida"]
        corridas = repo.corridas_de(id_caso)
        assert len(corridas) == 2
        assert corridas[0].id_corrida == primera["id_corrida"]
        assert corridas[1].origen == primera["id_corrida"]

    def test_recalcular_sin_corrida_previa_es_conflicto(self, cliente: TestClient) -> None:
        id_caso = crear_caso(cliente)
        respuesta = cliente.post(f"/api/casos/{id_caso}/recalcular", headers=CABECERAS)
        assert respuesta.status_code == 409

    def test_sin_datos_maestros_no_se_calcula(
        self, cliente_sin_maestros: TestClient, repo: RepositorioEnMemoria
    ) -> None:
        # Es el estado real: los parametros los mantiene MINSUR y `R-32` sigue
        # abierta. Calcular con unos valores por defecto seria inventarlos.
        id_caso = crear_caso(cliente_sin_maestros)
        con_insumos(repo, id_caso)
        respuesta = cliente_sin_maestros.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS)
        assert respuesta.status_code == 501
        assert respuesta.json()["detail"]["restriccion"] == "R-32"


class TestTableroEHistorial:
    def test_el_tablero_trae_indicadores_y_curvas(
        self, cliente: TestClient, repo: RepositorioEnMemoria
    ) -> None:
        id_caso = crear_caso(cliente)
        con_insumos(repo, id_caso)
        cliente.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS)

        respuesta = cliente.get("/api/tablero", params={"caso": id_caso}, headers=CABECERAS)
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["id_caso"] == id_caso
        assert len(cuerpo["curva_produccion"]) == 3
        assert cuerpo["cascada"][0]["concepto"] == "Ventas"

    def test_el_tablero_de_un_caso_sin_corrida_es_conflicto(self, cliente: TestClient) -> None:
        id_caso = crear_caso(cliente)
        respuesta = cliente.get("/api/tablero", params={"caso": id_caso}, headers=CABECERAS)
        assert respuesta.status_code == 409

    def test_los_estados_financieros_traen_una_linea_por_bloque(
        self, cliente: TestClient, repo: RepositorioEnMemoria
    ) -> None:
        id_caso = crear_caso(cliente)
        con_insumos(repo, id_caso)
        cliente.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS)

        cuerpo = cliente.get(
            "/api/estados-financieros", params={"caso": id_caso}, headers=CABECERAS
        ).json()
        assert cuerpo["anios"] == [2027, 2028, 2029]
        assert "Flujo economico" in cuerpo["lineas"]
        for nombre, linea in cuerpo["lineas"].items():
            assert len(linea) == 3, f"la linea {nombre} no cubre el horizonte"

    def test_el_historial_ordena_de_la_mas_reciente_a_la_mas_antigua(
        self, cliente: TestClient, repo: RepositorioEnMemoria
    ) -> None:
        id_caso = crear_caso(cliente, "Nazareth")
        con_insumos(repo, id_caso)
        cliente.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS)
        cliente.post(f"/api/casos/{id_caso}/recalcular", headers=CABECERAS)

        cuerpo = cliente.get("/api/historial", headers=CABECERAS).json()
        assert cuerpo["total"] == 2
        assert cuerpo["corridas"][0]["nombre_caso"] == "Nazareth"
        assert cuerpo["corridas"][0]["version_motor"]

    def test_comparar_exige_que_ambos_tengan_corrida(
        self, cliente: TestClient, repo: RepositorioEnMemoria
    ) -> None:
        uno = crear_caso(cliente, "Base")
        otro = crear_caso(cliente, "Con proyecto")
        con_insumos(repo, uno)
        cliente.post(f"/api/casos/{uno}/evaluar", headers=CABECERAS)

        assert (
            cliente.get(f"/api/casos/{uno}/comparar/{otro}", headers=CABECERAS).status_code == 409
        )

        con_insumos(repo, otro)
        cliente.post(f"/api/casos/{otro}/evaluar", headers=CABECERAS)
        cuerpo = cliente.get(f"/api/casos/{uno}/comparar/{otro}", headers=CABECERAS).json()
        assert cuerpo["comparables"] is True
        assert cuerpo["advertencia"] is None


class TestLoQueSigueBloqueado:
    """Cada 501 con la restricción que lo justifica, para que no se pierda."""

    def test_congelar_espera_el_contenedor_inmutable(
        self, cliente: TestClient, repo: RepositorioEnMemoria
    ) -> None:
        id_caso = crear_caso(cliente)
        con_insumos(repo, id_caso)
        cliente.post(f"/api/casos/{id_caso}/evaluar", headers=CABECERAS)
        respuesta = cliente.post(
            f"/api/casos/{id_caso}/congelar",
            json={"motivo": "Sustento del comite de inversiones de octubre"},
            headers=CABECERAS,
        )
        assert respuesta.status_code == 501
        assert respuesta.json()["detail"]["restriccion"] == "R-23"

    def test_el_contraste_espera_los_casos_certificados(self, cliente: TestClient) -> None:
        id_caso = crear_caso(cliente)
        respuesta = cliente.get(f"/api/casos/{id_caso}/verificar-fidelidad", headers=CABECERAS)
        assert respuesta.status_code == 501
        assert respuesta.json()["detail"]["restriccion"] == "R-30"

    def test_exportar_espera_el_almacenamiento(self, cliente: TestClient) -> None:
        id_caso = crear_caso(cliente)
        respuesta = cliente.get(f"/api/casos/{id_caso}/exportar", headers=CABECERAS)
        assert respuesta.status_code == 501
        assert respuesta.json()["detail"]["restriccion"] == "R-23"

    def test_la_bitacora_espera_el_almacen_de_solo_escritura(self, cliente: TestClient) -> None:
        respuesta = cliente.get("/api/auditoria", headers=CABECERAS)
        assert respuesta.status_code == 501
        assert respuesta.json()["detail"]["restriccion"] == "R-23"
