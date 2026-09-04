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

**Las escalas son las de la norma publicada, no una reconstrucción.** Hasta el
04/09/2026 fueron planas -un tramo al 1 % y un impuesto especial en cero-, con
el argumento de que reproducirlas de memoria daría cifras plausibles y
equivocadas. El argumento sigue siendo bueno y por eso no se reproducen de
memoria: se transcriben de la Ley 29788 y de la Ley 29789, que son públicas, y
coinciden con las que el modelo de referencia lleva en sus dos tablas de
tramos. Lo que las escalas planas hacían imposible era ver la hoja: con la
regalía al 1 % empatada con la mínima sobre ventas, la rama progresiva no gana
nunca, y con el impuesto especial en cero sus diecisiete tramos y sus dos
filas salen vacíos en toda pantalla y en toda prueba.

**Siguen siendo provisionales.** Los límites y las tasas son dato maestro que
MINSUR confirma bajo `R-32`, y la versión `DEV-0` marca cada corrida que los usó.

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

# El limite superior es el margen operativo en tanto por uno; diez cubre
# cualquier margen concebible y evita que la escala se quede corta. Es como se
# escribe el tramo abierto por arriba del libro, que alli es el texto `>80%` y
# `>85%`: la regla `058`.
_TOPE_DE_MARGEN = 10.0

# Los tramos de las dos escalas, como pares de -limite superior del margen, tasa
# marginal-. Se escriben uno a uno y no se derivan de una progresion aritmetica:
# el ultimo tramo de las dos rompe el paso, y una tabla explicita se coteja
# contra la norma de un vistazo, que es lo que hay que poder hacer con ella.
TRAMOS_DE_REGALIA = (
    (0.10, 0.0100),
    (0.15, 0.0175),
    (0.20, 0.0250),
    (0.25, 0.0325),
    (0.30, 0.0400),
    (0.35, 0.0475),
    (0.40, 0.0550),
    (0.45, 0.0625),
    (0.50, 0.0700),
    (0.55, 0.0775),
    (0.60, 0.0850),
    (0.65, 0.0925),
    (0.70, 0.1000),
    (0.75, 0.1075),
    (0.80, 0.1150),
    (_TOPE_DE_MARGEN, 0.1200),
)
"""Regalia minera, Ley 29788: dieciseis tramos sobre el margen operativo."""

TRAMOS_DE_IEM = (
    (0.10, 0.0200),
    (0.15, 0.0240),
    (0.20, 0.0280),
    (0.25, 0.0320),
    (0.30, 0.0360),
    (0.35, 0.0400),
    (0.40, 0.0440),
    (0.45, 0.0480),
    (0.50, 0.0520),
    (0.55, 0.0560),
    (0.60, 0.0600),
    (0.65, 0.0640),
    (0.70, 0.0680),
    (0.75, 0.0720),
    (0.80, 0.0760),
    (0.85, 0.0800),
    (_TOPE_DE_MARGEN, 0.0840),
)
"""Impuesto especial a la mineria, Ley 29789: diecisiete tramos."""


def _escala(tramos: tuple[tuple[float, float], ...]) -> EscalaProgresiva:
    """Encadena los tramos: el limite superior de uno abre el siguiente."""
    desde = 0.0
    construidos = []
    for hasta, tasa in tramos:
        construidos.append(Tramo(desde, hasta, tasa))
        desde = hasta
    return EscalaProgresiva(tramos=tuple(construidos))


ESCALA_REGALIA = _escala(TRAMOS_DE_REGALIA)
ESCALA_IEM = _escala(TRAMOS_DE_IEM)

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
    escala_regalia=ESCALA_REGALIA,
    escala_iem=ESCALA_IEM,
)
