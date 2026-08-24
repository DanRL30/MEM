"""Versión de la API y del motor.

Se exponen por separado porque cambian por razones distintas: la API cuando
cambia el contrato con la interfaz, el motor cuando Finanzas modifica el
modelo económico. Confundirlas haría que una corrección de la interfaz
pareciera un cambio de la lógica de cálculo.
"""

from __future__ import annotations

VERSION_API = "0.1.0"


def version_motor() -> str | None:
    """Versión del motor instalado, si ya existe.

    Devuelve None mientras el motor no tenga lógica: PT2 no ha iniciado por
    estar pendiente la entrega del modelo de referencia (R-02).
    """
    try:
        from minsur_engine import __version__

        return __version__
    except ImportError:
        return None
