"""Enrutadores de la API, uno por módulo del alcance funcional."""

from . import casos, evaluaciones, historial, identidad, plantillas, salud, tablero

__all__ = [
    "casos",
    "evaluaciones",
    "historial",
    "identidad",
    "plantillas",
    "salud",
    "tablero",
]
