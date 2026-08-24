"""Configuración de la aplicación.

Todo valor que cambie entre entornos llega por variable de entorno, que es lo
que la plantilla Bicep inyecta en la configuración de la aplicación. No hay
constantes de entorno en el código: es la condición para que el mismo
artefacto que pasó calidad sea el que llega a producción.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    entorno: str = Field(default="local", alias="ENTORNO")

    # --- Identidad -----------------------------------------------------------
    tenant_id: str = Field(default="", alias="AZURE_TENANT_ID")
    id_aplicacion: str = Field(default="", alias="AZURE_CLIENT_ID")

    # --- Datos ---------------------------------------------------------------
    cuenta_almacenamiento: str = Field(default="", alias="ALMACENAMIENTO_CUENTA")
    servidor_sql: str = Field(default="", alias="SQL_SERVIDOR")
    base_datos: str = Field(default="", alias="SQL_BASE_DATOS")
    uri_boveda: str = Field(default="", alias="KEY_VAULT_URI")

    # --- Publicación documental ----------------------------------------------
    sitio_sharepoint: str = Field(default="", alias="SHAREPOINT_SITIO")
    biblioteca_sharepoint: str = Field(default="", alias="SHAREPOINT_BIBLIOTECA")

    # --- Nivel de servicio ---------------------------------------------------
    # El alcance compromete apertura del tablero por debajo de 5 s. La cifra
    # de la evaluación estándar la fija MINSUR (R-51).
    slo_tablero_ms: int = Field(default=5000, alias="SLO_TABLERO_MS")

    @property
    def es_local(self) -> bool:
        return self.entorno == "local"


@lru_cache
def config() -> Config:
    return Config()
