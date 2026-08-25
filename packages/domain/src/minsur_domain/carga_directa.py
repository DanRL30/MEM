"""Carga y descarga de archivos sin atravesar la puerta de enlace.

Las plantillas de Producción, CAPEX y OPEX pesan entre 1 y 10 MB. Hacerlas
pasar por API Management y por los servicios de aplicación tiene tres costos:
ocupa memoria de cómputo con megabytes de Excel, tensiona el límite de tamaño
del cuerpo de la solicitud en la puerta, y duplica la latencia de carga sin
aportar nada — el archivo termina en el almacenamiento de todos modos.

El patrón correcto es que la interfaz pida una autorización de corta vigencia y
suba el archivo **directamente al almacenamiento**. La aplicación nunca ve los
bytes: solo emite el permiso y, después, valida el resultado.

Esto vale con cualquier SKU. Que además permita operar API Management en el
nivel Consumption, que factura por llamada y escala a cero, es una consecuencia
favorable y no el motivo del diseño.

Seguridad del mecanismo:

  - Firma de **delegación de usuario**, no clave de cuenta. La cuenta tiene
    `allowSharedKeyAccess` en false: no existe clave que firmar.
  - Vigencia de quince minutos. Suficiente para 10 MB en una red corporativa,
    corto para reutilizarse.
  - Permiso acotado a **un blob concreto**, no al contenedor.
  - Escritura sin lectura al cargar; lectura sin escritura al descargar.
  - El nombre del blob lo determina el servidor, nunca el cliente: un nombre
    provisto por el usuario permitiría escribir sobre otra evaluación.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from azure.core.credentials import TokenCredential
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    UserDelegationKey,
    generate_blob_sas,
)

VIGENCIA_CARGA = timedelta(minutes=15)
VIGENCIA_DESCARGA = timedelta(minutes=5)

# Margen hacia atrás por desfase de reloj entre el cliente y el servicio.
MARGEN_RELOJ = timedelta(minutes=5)

TipoPlantilla = Literal["produccion", "capex", "opex"]

EXTENSIONES_ADMITIDAS = {".xlsx", ".xlsm"}
TAMANIO_MAXIMO_MB = 25


@dataclass(frozen=True)
class Autorizacion:
    """Permiso temporal para operar sobre un blob concreto."""

    url: str
    ruta_blob: str
    expira: datetime
    metodo: str


class CargaDirecta:
    """Emite autorizaciones de carga y descarga contra el almacenamiento."""

    def __init__(
        self,
        cuenta: str,
        credencial: TokenCredential,
        contenedor: str = "plantillas",
    ) -> None:
        self._cuenta = cuenta
        self._contenedor = contenedor
        self._url_cuenta = f"https://{cuenta}.blob.core.windows.net"
        self._cliente = BlobServiceClient(self._url_cuenta, credential=credencial)

    # --- Clave de delegación -------------------------------------------------

    def _clave_delegacion(self, desde: datetime, hasta: datetime) -> UserDelegationKey:
        """Clave firmada por Entra ID, no por una clave de cuenta.

        Requiere el rol `Storage Blob Delegator` sobre la cuenta, que la
        plantilla asigna a la identidad administrada.
        """
        return self._cliente.get_user_delegation_key(
            key_start_time=desde,
            key_expiry_time=hasta,
        )

    # --- Carga ---------------------------------------------------------------

    def autorizar_carga(
        self,
        id_caso: str,
        tipo: TipoPlantilla,
        nombre_original: str,
    ) -> Autorizacion:
        """Autoriza la subida de una plantilla a un blob que fija el servidor.

        `nombre_original` solo se usa para validar la extensión y conservarla
        como metadato. **No forma parte de la ruta**: aceptar una ruta del
        cliente permitiría sobrescribir la plantilla de otra evaluación.
        """
        extension = _extension(nombre_original)
        if extension not in EXTENSIONES_ADMITIDAS:
            raise ValueError(
                f"Extensión no admitida: {extension or '(sin extensión)'}. "
                f"Se aceptan {', '.join(sorted(EXTENSIONES_ADMITIDAS))}."
            )

        ruta = f"{id_caso}/{tipo}/{uuid4().hex}{extension}"
        ahora = datetime.now(UTC)
        desde, hasta = ahora - MARGEN_RELOJ, ahora + VIGENCIA_CARGA

        firma = generate_blob_sas(
            account_name=self._cuenta,
            container_name=self._contenedor,
            blob_name=ruta,
            user_delegation_key=self._clave_delegacion(desde, hasta),
            # Escritura y creación, sin lectura: quien carga no puede leer
            # lo que ya existe en el contenedor.
            permission=BlobSasPermissions(write=True, create=True),
            start=desde,
            expiry=hasta,
            protocol="https",
        )

        return Autorizacion(
            url=f"{self._url_cuenta}/{self._contenedor}/{ruta}?{firma}",
            ruta_blob=ruta,
            expira=hasta,
            metodo="PUT",
        )

    # --- Descarga ------------------------------------------------------------

    def autorizar_descarga(self, ruta_blob: str) -> Autorizacion:
        """Autoriza la lectura de un blob ya existente.

        Se usa para las exportaciones a Excel y PDF, que también evitan
        atravesar la puerta de enlace.
        """
        ahora = datetime.now(UTC)
        desde, hasta = ahora - MARGEN_RELOJ, ahora + VIGENCIA_DESCARGA

        firma = generate_blob_sas(
            account_name=self._cuenta,
            container_name=self._contenedor,
            blob_name=ruta_blob,
            user_delegation_key=self._clave_delegacion(desde, hasta),
            permission=BlobSasPermissions(read=True),
            start=desde,
            expiry=hasta,
            protocol="https",
        )

        return Autorizacion(
            url=f"{self._url_cuenta}/{self._contenedor}/{ruta_blob}?{firma}",
            ruta_blob=ruta_blob,
            expira=hasta,
            metodo="GET",
        )

    # --- Confirmación --------------------------------------------------------

    def confirmar_carga(self, ruta_blob: str) -> int:
        """Verifica que el archivo llegó y devuelve su tamaño en bytes.

        La autorización no garantiza que la carga haya ocurrido: el cliente
        pudo abandonarla. Nada se procesa antes de esta comprobación.
        """
        blob = self._cliente.get_blob_client(self._contenedor, ruta_blob)
        if not blob.exists():
            raise FileNotFoundError(
                f"No se encontró {ruta_blob}. La carga no se completó "
                "o la autorización expiró antes de terminar."
            )

        propiedades = blob.get_blob_properties()
        tamanio = propiedades.size

        limite = TAMANIO_MAXIMO_MB * 1024 * 1024
        if tamanio > limite:
            blob.delete_blob()
            raise ValueError(
                f"El archivo pesa {tamanio / 1024 / 1024:.1f} MB y el máximo es "
                f"{TAMANIO_MAXIMO_MB} MB. Se eliminó del almacenamiento."
            )
        if tamanio == 0:
            blob.delete_blob()
            raise ValueError("El archivo llegó vacío. Se eliminó del almacenamiento.")

        return tamanio


def _extension(nombre: str) -> str:
    punto = nombre.rfind(".")
    return nombre[punto:].lower() if punto >= 0 else ""
