"""Configuración del contraste de fidelidad.

Los casos sintéticos viven en `casos/`, fuera del alcance de importación por
defecto de pytest. Añadir este directorio al camino de búsqueda es lo que
permite que `casos/` sea un catálogo y no un archivo suelto: cuando lleguen los
casos certificados, se sumarán ahí al lado.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
