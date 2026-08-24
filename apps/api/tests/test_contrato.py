"""Pruebas del contrato de la API.

El grupo que más importa es `TestContratoYaComprometido`. Cuatro artefactos
del servicio —la verificación de la ventana de pase, la verificación de humo
del despliegue, la importación a API Management y la generación de tipos del
frontend— se escribieron antes que esta API y dan por supuestos ciertos
endpoints. Si alguno cambia de nombre, el fallo aparece en la ventana de
mantenimiento del domingo, que es el peor momento posible.

Estas pruebas leen los artefactos reales y comprueban la correspondencia,
en lugar de repetir la lista a mano.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from minsur_domain.estados import Perfil

from minsur_api.main import crear_app
from minsur_api.openapi import esquema
from minsur_api.seguridad import GRUPOS_POR_PERFIL, PRECEDENCIA, perfil_desde_grupos

RAIZ = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def cliente() -> TestClient:
    return TestClient(crear_app())


@pytest.fixture(scope="module")
def documento() -> dict:
    return esquema()


# --- Contrato ya comprometido con otros artefactos ---------------------------


class TestContratoYaComprometido:
    def test_los_endpoints_de_la_verificacion_del_pase_existen(self, documento: dict):
        origen = (RAIZ / "infra/pipelines/scripts/verificacion_pase.py").read_text(
            encoding="utf-8"
        )
        # Las rutas aparecen en el script como f-strings con {base} delante.
        esperados = {
            re.sub(r"\{[^}]+\}", "{id_caso}", ruta).split("?")[0]
            for ruta in re.findall(r'/api/[a-z0-9{}/_-]+', origen)
        }
        expuestos = set(documento["paths"])
        faltantes = esperados - expuestos
        assert not faltantes, (
            f"La verificación de la ventana de pase consulta {faltantes}, "
            "que esta API no expone. Fallaría el domingo del despliegue."
        )

    def test_el_endpoint_de_la_verificacion_de_humo_existe(self, documento: dict):
        plantilla = (RAIZ / "infra/pipelines/templates/desplegar.yml").read_text(
            encoding="utf-8"
        )
        assert "/api/salud" in plantilla
        assert "/api/salud" in documento["paths"]

    def test_la_ruta_del_esquema_coincide_con_la_que_importa_apim(self):
        plantilla = (RAIZ / "infra/pipelines/templates/desplegar.yml").read_text(
            encoding="utf-8"
        )
        assert "packages/contracts/openapi.json" in plantilla

    def test_el_comando_que_invoca_el_frontend_es_este_modulo(self):
        paquete = (RAIZ / "package.json").read_text(encoding="utf-8")
        assert "python -m minsur_api.openapi" in paquete


# --- Salud -------------------------------------------------------------------


class TestSalud:
    def test_responde_sin_autenticacion(self, cliente: TestClient):
        # Exigir token aquí haría que un fallo de identidad se reportara como
        # servicio caído, y llevaría a revertir por la causa equivocada.
        respuesta = cliente.get("/api/salud")
        assert respuesta.status_code == 200
        assert respuesta.json()["estado"] == "ok"

    def test_informa_que_el_motor_no_esta_disponible(self, cliente: TestClient):
        # El motor no tiene lógica todavía: PT2 espera el modelo (R-02).
        assert respuesta_motor(cliente) is None


def respuesta_motor(cliente: TestClient):
    return cliente.get("/api/salud").json()["version_motor"]


# --- Autenticación -----------------------------------------------------------


class TestAutenticacion:
    @pytest.mark.parametrize(
        "ruta", ["/api/yo", "/api/tablero", "/api/historial", "/api/auditoria"]
    )
    def test_sin_token_devuelve_401(self, cliente: TestClient, ruta: str):
        respuesta = cliente.get(ruta)
        assert respuesta.status_code == 401
        assert respuesta.headers["WWW-Authenticate"] == "Bearer"

    def test_un_esquema_distinto_de_bearer_se_rechaza(self, cliente: TestClient):
        respuesta = cliente.get("/api/yo", headers={"Authorization": "Basic abc"})
        assert respuesta.status_code == 401

    def test_con_token_devuelve_la_identidad(self, cliente: TestClient):
        respuesta = cliente.get("/api/yo", headers={"Authorization": "Bearer x"})
        assert respuesta.status_code == 200
        assert respuesta.json()["perfil"] == Perfil.ADMINISTRADOR


# --- Mapeo de grupos a perfiles ----------------------------------------------


class TestPerfiles:
    def test_hay_un_grupo_por_cada_perfil_del_alcance(self):
        assert set(GRUPOS_POR_PERFIL.values()) == set(Perfil)

    def test_la_precedencia_cubre_los_seis_perfiles(self):
        assert set(PRECEDENCIA) == set(Perfil)
        assert len(PRECEDENCIA) == len(set(PRECEDENCIA))

    def test_sin_grupo_conocido_no_hay_perfil(self):
        assert perfil_desde_grupos(["SG-OTRO-SISTEMA"]) is None
        assert perfil_desde_grupos([]) is None

    def test_con_varios_grupos_aplica_el_de_mayor_alcance(self):
        perfil = perfil_desde_grupos(
            ["SG-MINSUR-EVALECO-AUDITOR", "SG-MINSUR-EVALECO-ADMIN"]
        )
        assert perfil is Perfil.ADMINISTRADOR

    def test_el_orden_de_los_grupos_no_influye(self):
        a = perfil_desde_grupos(["SG-MINSUR-EVALECO-LIDER", "SG-MINSUR-EVALECO-AUDITOR"])
        b = perfil_desde_grupos(["SG-MINSUR-EVALECO-AUDITOR", "SG-MINSUR-EVALECO-LIDER"])
        assert a is b is Perfil.LIDER_DE_ESTUDIO


# --- Operaciones pendientes de un insumo -------------------------------------


class TestPendientes:
    @pytest.mark.parametrize(
        "ruta,restriccion",
        [
            ("/api/tablero", "R-02"),
            ("/api/estados-financieros", "R-02"),
            ("/api/casos/C1/verificar-fidelidad", "R-02"),
            ("/api/historial", "R-07"),
            ("/api/casos", "R-07"),
        ],
    )
    def test_declaran_la_restriccion_que_las_bloquea(
        self, cliente: TestClient, ruta: str, restriccion: str
    ):
        # Devolver 501 con la restricción es preferible a devolver un
        # resultado inventado que alguien pueda tomar por bueno.
        respuesta = cliente.get(ruta, headers={"Authorization": "Bearer x"})
        assert respuesta.status_code == 501
        assert respuesta.json()["detail"]["restriccion"] == restriccion


# --- Esquema -----------------------------------------------------------------


class TestEsquema:
    def test_el_servidor_es_relativo(self, documento: dict):
        # Un servidor absoluto haría que el cliente generado apuntara siempre
        # al mismo entorno.
        assert documento["servers"] == [
            {"url": "/", "description": "A través de API Management"}
        ]

    def test_toda_ruta_cuelga_de_api(self, documento: dict):
        assert all(r.startswith("/api/") for r in documento["paths"])

    def test_toda_operacion_tiene_resumen(self, documento: dict):
        sin_resumen = [
            f"{metodo.upper()} {ruta}"
            for ruta, metodos in documento["paths"].items()
            for metodo, op in metodos.items()
            if not op.get("summary")
        ]
        assert not sin_resumen, f"Operaciones sin resumen: {sin_resumen}"

    def test_es_estable_entre_generaciones(self):
        import json

        assert json.dumps(esquema(), sort_keys=True) == json.dumps(
            esquema(), sort_keys=True
        )
