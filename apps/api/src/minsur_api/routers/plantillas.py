"""Carga de plantillas mediante firma de acceso compartido.

La interfaz no envía el archivo a la API. Pide una autorización temporal y
sube el archivo **directamente al almacenamiento**, sin que atraviese la
puerta de enlace ni los servicios de aplicación.

El flujo tiene tres pasos y los tres importan:

    1. autorizacion  la API emite una firma de quince minutos para un blob
                     cuyo nombre fija el servidor
    2. el navegador  sube el archivo a esa URL con PUT
    3. confirmar     la API comprueba que llegó, lo valida y lo admite

El paso 3 no es una formalidad. La autorización no garantiza que la carga
haya ocurrido: el cliente pudo abandonarla. Nada se procesa antes de
comprobarlo.

Este patrón es correcto con cualquier configuración de la puerta de enlace.
Evita ocupar memoria de cómputo con megabytes de Excel, elimina un límite de
tamaño en la puerta y reduce la latencia de carga.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status

from minsur_domain.estados import Perfil

from ..esquemas import (
    AutorizacionCarga,
    ConfirmacionCarga,
    Problema,
    ResultadoValidacion,
    SolicitudCarga,
)
from ..seguridad import Usuario, requiere

router = APIRouter(prefix="/casos/{id_caso}/plantillas", tags=["Plantillas"])

ID_CASO = Path(examples=["CASO-SR-2026-014"])

PUEDE_CARGAR = requiere(
    Perfil.ADMINISTRADOR,
    Perfil.FINANZAS,
    Perfil.LIDER_DE_ESTUDIO,
    Perfil.INGENIERO_DE_PROYECTO,
)


@router.post(
    "/autorizacion",
    response_model=AutorizacionCarga,
    summary="Autorizar la carga directa de una plantilla",
    responses={400: {"model": Problema}, 403: {"model": Problema}},
)
async def autorizar_carga(
    solicitud: SolicitudCarga,
    id_caso: str = ID_CASO,
    usuario: Usuario = Depends(PUEDE_CARGAR),
) -> AutorizacionCarga:
    """Emite una firma de acceso compartido acotada a un solo archivo.

    Cinco restricciones sostienen la seguridad del mecanismo:

    - Firma de **delegación de usuario**, no clave de cuenta. El
      almacenamiento tiene deshabilitado el acceso por clave compartida: no
      existe clave que firmar.
    - Vigencia de quince minutos.
    - Permiso acotado a **un blob concreto**, no al contenedor.
    - Escritura y creación, sin lectura: quien carga no puede leer lo que ya
      existe.
    - **El nombre del blob lo determina el servidor.** Aceptar una ruta del
      cliente permitiría escribir sobre la plantilla de otra evaluación.
    """
    from ..dependencias import carga_directa

    try:
        autorizacion = carga_directa().autorizar_carga(
            id_caso=id_caso,
            tipo=solicitud.tipo,
            nombre_original=solicitud.nombre_archivo,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detalle": str(e), "restriccion": None},
        ) from e

    return AutorizacionCarga(
        url=autorizacion.url,
        ruta_blob=autorizacion.ruta_blob,
        expira=autorizacion.expira,
    )


@router.post(
    "/confirmar",
    response_model=ResultadoValidacion,
    summary="Confirmar y validar una plantilla cargada",
    responses={
        400: {"model": Problema},
        404: {"model": Problema},
        501: {"model": Problema},
    },
)
async def confirmar_carga(
    confirmacion: ConfirmacionCarga,
    id_caso: str = ID_CASO,
    usuario: Usuario = Depends(PUEDE_CARGAR),
) -> ResultadoValidacion:
    """Comprueba que el archivo llegó y lo valida antes de admitirlo.

    La validación de estructura, unidades, clasificaciones y horizonte
    temporal depende de las plantillas definitivas que elabora MINSUR
    (`R-07`). INVA implementa su lectura y validación, no su diseño.
    """
    from ..dependencias import carga_directa

    try:
        tamanio = carga_directa().confirmar_carga(confirmacion.ruta_blob)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detalle": str(e), "restriccion": None},
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detalle": str(e), "restriccion": None},
        ) from e

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "detalle": (
                f"El archivo llegó correctamente ({tamanio} bytes). El "
                "validador depende de las plantillas definitivas de "
                "Producción, CAPEX y OPEX que elabora MINSUR."
            ),
            "restriccion": "R-07",
        },
    )
