"""Versión de la API y del motor.

Se exponen por separado porque cambian por razones distintas: la API cuando
cambia el contrato con la interfaz, el motor cuando Finanzas modifica el
modelo económico. Confundirlas haría que una corrección de la interfaz
pareciera un cambio de la lógica de cálculo.
"""

from __future__ import annotations

from importlib.util import find_spec

VERSION_API = "0.1.0"

# Ultimo eslabon de la cadena de calculo: produce NPV, TIR, Payback y Capital
# Intensity. Sirve de senal de capacidad porque sin el no hay indicador que
# reportar, por muchos bloques intermedios que existan.
MODULO_INDICADORES = "minsur_engine.indicadores"


def version_motor() -> str | None:
    """Versión del motor desplegado, o None si todavía no calcula.

    La presencia del paquete no distingue nada: `minsur_engine` es miembro
    del espacio de trabajo y se instala siempre, incluso vacío. Lo que
    interesa al operador es si hay lógica de cálculo desplegada, y eso lo
    marca la existencia del módulo de indicadores, que PT2 incorpora cuando
    Finanzas entregue el modelo de referencia (R-02).
    """
    try:
        if find_spec(MODULO_INDICADORES) is None:
            return None
    except ModuleNotFoundError:
        return None

    from minsur_engine import __version__

    return __version__
