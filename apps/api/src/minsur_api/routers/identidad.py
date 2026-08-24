"""Identidad del usuario autenticado."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from minsur_domain.estados import Estado, acciones_disponibles

from ..esquemas import UsuarioActual
from ..seguridad import Usuario, usuario_actual

router = APIRouter(tags=["Identidad"])


@router.get("/yo", response_model=UsuarioActual, summary="Usuario autenticado")
async def yo(usuario: Usuario = Depends(usuario_actual)) -> UsuarioActual:
    """Identidad y alcance del usuario.

    La interfaz la consulta al iniciar sesión para decidir qué controles
    muestra. Que un control no aparezca no sustituye a la verificación del
    servidor, que ocurre en cada operación.
    """
    permitidas = sorted(
        {
            str(accion)
            for estado in Estado
            for accion in acciones_disponibles(estado, usuario.perfil)
        }
    )
    return UsuarioActual(
        id_objeto=usuario.id_objeto,
        nombre=usuario.nombre,
        correo=usuario.correo,
        perfil=usuario.perfil,
        acciones_permitidas=permitidas,
    )
