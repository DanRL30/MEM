"""Dependencias con estado: credenciales y clientes de servicio.

Se construyen una sola vez y se reutilizan. La credencial de identidad
administrada mantiene una caché de tokens interna, y crearla en cada
solicitud desperdiciaria esa cache.
"""

from __future__ import annotations

from functools import lru_cache

from minsur_domain.carga_directa import CargaDirecta

from .config import config


@lru_cache
def credencial():
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
