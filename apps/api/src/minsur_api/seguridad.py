"""Autenticación y mapeo de grupos a perfiles.

API Management valida el token antes de reenviar la solicitud, pero el
backend vuelve a validarlo. No es redundancia ociosa: la restricción de red
que limita el backend a la puerta de enlace es una configuración, y una
configuración puede cambiarse por error. Un servicio que confía en que
alguien más autenticó queda expuesto el día que esa suposición deja de ser
cierta.

El perfil no se recibe del cliente ni se consulta a Microsoft Graph: se
deriva de la reclamación `groups` del token, que Entra ID emite firmada. Es
lo que permite prescindir del permiso GroupMember.Read.All.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from minsur_domain.estados import Perfil

# La correspondencia la fija MINSUR al crear los grupos (SOL-21 · R-21).
# El identificador de objeto llega por configuración; el nombre queda aquí
# como documentación de a qué grupo corresponde cada perfil.
GRUPOS_POR_PERFIL: dict[str, Perfil] = {
    "SG-MINSUR-EVALECO-ADMIN": Perfil.ADMINISTRADOR,
    "SG-MINSUR-EVALECO-FINANZAS": Perfil.FINANZAS,
    "SG-MINSUR-EVALECO-LIDER": Perfil.LIDER_DE_ESTUDIO,
    "SG-MINSUR-EVALECO-INGENIERO": Perfil.INGENIERO_DE_PROYECTO,
    "SG-MINSUR-EVALECO-EJECUTIVO": Perfil.CONSULTA_EJECUTIVA,
    "SG-MINSUR-EVALECO-AUDITOR": Perfil.AUDITOR,
}

# Cuando un usuario pertenece a varios grupos se aplica el de mayor alcance.
# El orden es deliberado: Administrador primero, Auditor último.
PRECEDENCIA: tuple[Perfil, ...] = (
    Perfil.ADMINISTRADOR,
    Perfil.FINANZAS,
    Perfil.LIDER_DE_ESTUDIO,
    Perfil.INGENIERO_DE_PROYECTO,
    Perfil.CONSULTA_EJECUTIVA,
    Perfil.AUDITOR,
)


@dataclass(frozen=True)
class Usuario:
    id_objeto: str
    nombre: str
    correo: str
    perfil: Perfil
    grupos: tuple[str, ...]


def perfil_desde_grupos(grupos: list[str]) -> Perfil | None:
    """Deriva el perfil de mayor alcance entre los grupos del usuario."""
    encontrados = {
        GRUPOS_POR_PERFIL[g] for g in grupos if g in GRUPOS_POR_PERFIL
    }
    for perfil in PRECEDENCIA:
        if perfil in encontrados:
            return perfil
    return None


async def usuario_actual(
    authorization: str = Header(default=""),
) -> Usuario:
    """Extrae y valida el usuario del token.

    NOTA DE IMPLEMENTACIÓN: la validación criptográfica de la firma contra
    las claves publicadas por Entra ID se resuelve en PT3.1, del 9 al 10 de
    septiembre, y depende del registro de aplicación (R-26). Hasta entonces
    esta función rechaza toda solicitud fuera del entorno local, para que la
    ausencia de validación no pueda confundirse con validación permisiva.
    """
    from .config import config

    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere un token de acceso del tenant corporativo.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not config().es_local:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "La validación de token contra Entra ID se implementa en PT3.1 "
                "y requiere el registro de aplicación (R-26)."
            ),
        )

    # Solo en desarrollo local: identidad de conveniencia para poder ejercitar
    # los flujos sin depender del tenant del cliente.
    return Usuario(
        id_objeto="00000000-0000-0000-0000-000000000000",
        nombre="Desarrollo local",
        correo="local@invaglobal.com",
        perfil=Perfil.ADMINISTRADOR,
        grupos=("SG-MINSUR-EVALECO-ADMIN",),
    )


def requiere(*perfiles: Perfil):
    """Dependencia que restringe un endpoint a ciertos perfiles."""

    async def verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.perfil not in perfiles:
            autorizados = ", ".join(sorted(p.value for p in perfiles))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"El perfil {usuario.perfil} no tiene acceso a esta "
                    f"operación. Autorizados: {autorizados}."
                ),
            )
        return usuario

    return verificar
