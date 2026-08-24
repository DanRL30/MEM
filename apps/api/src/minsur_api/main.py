"""Aplicación FastAPI.

Se publica detrás de Azure API Management, que valida el token del tenant
corporativo antes de reenviar. El backend vuelve a validarlo: la restricción
de red que limita el backend a la puerta es una configuración, y confiar en
que alguien más autenticó deja el servicio expuesto el día que esa
configuración cambie por error.

Todo bajo /api. La interfaz se sirve desde Static Web Apps y llega aquí
atravesando la puerta.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from .config import config
from .routers import (
    casos,
    evaluaciones,
    historial,
    identidad,
    plantillas,
    salud,
    tablero,
)
from .version import VERSION_API, version_motor

log = logging.getLogger("minsur")

DESCRIPCION = """
Servicios de la Plataforma de Evaluación Económica · Modelo MINSUR.

Reproduce la lógica del modelo económico corporativo para que el área de
Proyectos evalúe escenarios de forma autónoma, con trazabilidad completa.

**Autenticación.** Token de Microsoft Entra ID del tenant corporativo. El
perfil se deriva de la reclamación `groups`; la plataforma no consulta la
membresía a Microsoft Graph.

**Archivos.** Las plantillas se cargan y los reportes se descargan
directamente contra el almacenamiento, mediante firmas de acceso compartido
de corta vigencia. No atraviesan esta API.

**Respuestas 501.** Indican una operación cuya implementación depende de un
insumo del cliente aún no recibido. El cuerpo incluye la restricción del
cuadro de control que la bloquea.
"""


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    cfg = config()
    log.info(
        "API %s iniciada · entorno=%s · motor=%s",
        VERSION_API,
        cfg.entorno,
        version_motor() or "no disponible",
    )
    yield


def crear_app() -> FastAPI:
    app = FastAPI(
        title="Plataforma de Evaluación Económica · MINSUR",
        description=DESCRIPCION,
        version=VERSION_API,
        contact={"name": "INVA · Servicio INVA-01-2026-182"},
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=ciclo_vida,
    )

    for router in (
        salud.router,
        identidad.router,
        casos.router,
        plantillas.router,
        evaluaciones.router,
        tablero.router,
        historial.router,
    ):
        app.include_router(router, prefix="/api")

    @app.exception_handler(Exception)
    async def error_no_previsto(request: Request, exc: Exception):
        # El detalle va al registro, no a la respuesta: un mensaje de
        # excepción puede revelar rutas, consultas o nombres de recursos.
        log.exception("Error no previsto en %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detalle": (
                    "Error interno. El incidente quedó registrado con su "
                    "identificador de correlación."
                ),
                "restriccion": None,
            },
        )

    return app


app = crear_app()
