"""Dependencias con estado: credenciales y clientes de servicio.

Se construyen una sola vez y se reutilizan. La credencial de identidad
administrada mantiene una caché de tokens interna, y crearla en cada
solicitud desperdiciaria esa cache.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from minsur_domain.carga_directa import CargaDirecta
from minsur_engine.caso import DatosMaestros

from .config import config
from .repositorio import RepositorioDeCasos, RepositorioEnMemoria

if TYPE_CHECKING:
    from azure.core.credentials import TokenCredential


@lru_cache
def credencial() -> TokenCredential:
    """Credencial de la identidad administrada asignada por el usuario.

    En un entorno de Azure resuelve a la identidad que la plantilla asignó a
    la aplicación. En local recurre a la sesión de Azure CLI del
    desarrollador. En ningun caso hay un secreto en el codigo.
    """
    from azure.identity import DefaultAzureCredential

    cfg = config()
    if cfg.id_aplicacion:
        return DefaultAzureCredential(managed_identity_client_id=cfg.id_aplicacion)
    return DefaultAzureCredential()


@lru_cache
def carga_directa() -> CargaDirecta:
    cfg = config()
    if not cfg.cuenta_almacenamiento:
        raise RuntimeError(
            "Falta ALMACENAMIENTO_CUENTA. La plantilla Bicep la inyecta en la "
            "configuracion de la aplicacion."
        )
    return CargaDirecta(cuenta=cfg.cuenta_almacenamiento, credencial=credencial())


@lru_cache
def repositorio() -> RepositorioDeCasos:
    """Almacén de casos y corridas.

    Devuelve el adaptador en memoria mientras Azure SQL no exista (`R-23`).
    Sustituirlo por el definitivo es cambiar esta función, porque los routers
    dependen del puerto y no del adaptador.
    """
    return RepositorioEnMemoria()


def datos_maestros() -> DatosMaestros | None:
    """Versión de datos maestros vigente: parámetros, tasas y escalas.

    Los mantiene MINSUR (`R-32`) y todavía no han llegado, así que hoy devuelve
    `None` y los endpoints que calculan responden 501 con esa restricción.
    Inventar unos valores por defecto seria peor: alguien los tomaria por
    oficiales y ningun contraste lo detectaria, porque el motor calcularia bien
    sobre parametros equivocados.

    Es una dependencia y no una lectura directa para que el entorno espejo
    pueda inyectar un juego de prueba sin tocar los routers.
    """
    return None
