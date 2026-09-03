"""Juego de datos maestros para desarrollo local. **Nunca sale de local.**

MINSUR mantiene los datos maestros reales (`R-32`) y todavía no han llegado.
Sin ellos la API responde 501 y no hay forma de ejecutar una corrida por HTTP,
lo que deja la interfaz sin nada que mostrar mientras se construye.

Este módulo resuelve eso **solo dentro del entorno local**, con el mismo
criterio que la identidad de conveniencia de `seguridad.py`: la carencia se
suple donde no puede confundirse con lo oficial, y en cualquier otro entorno
se mantiene el 501 con su restricción.

Tres decisiones deliberadas para que estos valores no puedan pasar por buenos:

**La versión se llama `DEV-0`.** Una corrida guarda la versión de datos
maestros con la que se calculó, así que cualquier resultado obtenido con este
juego queda marcado como tal en su terna, en el historial y en la pantalla. No
hay forma de mirar un número calculado aquí y creerlo oficial.

**Las escalas son planas y evidentemente falsas.** La regalía minera real tiene
dieciséis tramos y el impuesto especial diecisiete. Reproducirlas de memoria
daría cifras plausibles y equivocadas, que es el peor resultado posible: nadie
las revisaría. Un tramo único al 1 % y un impuesto especial en cero se delatan
a la primera lectura.

**Los ocho parámetros son los de referencia del alcance**, los mismos que la
documentación del servicio publica como lectura. No son un hallazgo ni una
suposición sobre lo que MINSUR va a confirmar: son el punto de partida que el
propio alcance declara, y su confirmación sigue siendo `R-32`.
"""

from __future__ import annotations

from minsur_engine.caso import DatosMaestros
from minsur_engine.depreciacion import TasasDeDepreciacion
from minsur_engine.impuestos import EscalaProgresiva, Tramo
from minsur_engine.parametros import ParametrosCorporativos

VERSION = "DEV-0"
"""Identificador que viaja en la terna de toda corrida calculada en local."""

# El límite superior es el margen operativo en tanto por uno; diez cubre
# cualquier margen concebible y evita que la escala se quede corta.
_TOPE_DE_MARGEN = 10.0

ESCALA_REGALIA_PLANA = EscalaProgresiva(tramos=(Tramo(0.0, _TOPE_DE_MARGEN, 0.01),))
"""Regalía al mínimo legal en un solo tramo. La escala real tiene dieciséis."""

ESCALA_IEM_NULA = EscalaProgresiva(tramos=(Tramo(0.0, _TOPE_DE_MARGEN, 0.0),))
"""Impuesto especial a la minería en cero. La escala real tiene diecisiete."""

PARAMETROS = ParametrosCorporativos(
    version_datos_maestros=VERSION,
    tasa_descuento=0.10,
    participacion_trabajadores=0.08,
    impuesto_renta=0.295,
    regalia_minima=0.01,
    osinergmin=0.0014,
    oefa=0.0010,
    fondo_jubilacion_minera=0.005,
)

# Las tasas de depreciación son dato maestro como las demás, y el caso puede
# sobrescribirlas componente a componente. Las dos vías arrancan iguales: lo
# que las separa no son las tasas sino el método, y eso lo decide el motor.
TASAS = TasasDeDepreciacion(
    maquinaria=0.20,
    instalaciones=0.10,
    edificaciones=0.05,
    estudios=0.05,
)

MAESTROS = DatosMaestros(
    parametros=PARAMETROS,
    tasas_tributarias=TASAS,
    tasas_financieras=TASAS,
    escala_regalia=ESCALA_REGALIA_PLANA,
    escala_iem=ESCALA_IEM_NULA,
)
