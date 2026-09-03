"""Parámetros corporativos, como dato versionado y no como constantes.

Los siete parámetros que gobiernan el cálculo — tasa de descuento,
participación de trabajadores, impuesto a la renta, regalía, Osinergmin, OEFA y
fondo de jubilación minera — los fija y mantiene MINSUR (`R-32`). En el libro
corporativo viven en la hoja `Control`; aquí entran como un valor que la
corrida recibe, nunca como un número escrito en el código.

La razón no es de estilo. Una corrida guarda la versión de datos maestros con
la que se calculó, y recalcularla dentro de cinco años tiene que usar **esa**
versión y no la vigente. Si un parámetro estuviera incrustado en el motor, esa
promesa se rompería en silencio la primera vez que MINSUR cambiara una tasa.

Los valores de referencia del alcance —10 %, 8 %, 29,5 %, 1 %, 0,14 %, 0,10 %
y 0,5 %— se citan en la documentación como lectura, y no aparecen aquí como
valores por defecto a propósito: un valor por defecto se acaba usando.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


class ErrorParametros(ValueError):
    """Un parámetro corporativo falta o está fuera de rango."""


@dataclass(frozen=True)
class ParametrosCorporativos:
    """Juego completo de parámetros de una versión de datos maestros.

    Todas las tasas se expresan en tanto por uno: 0,295 y no 29,5.
    """

    version_datos_maestros: str
    tasa_descuento: float
    participacion_trabajadores: float
    impuesto_renta: float
    regalia_minima: float
    osinergmin: float
    oefa: float
    fondo_jubilacion_minera: float

    limite_arrastre_de_perdidas: float = 0.5
    """Fraccion de la utilidad imponible que puede absorber el arrastre.

    El libro la lleva incrustada en las formulas de `Impuestos!48` y `!66`, y el
    estandar corporativo no la menciona. Aqui es dato maestro como las demas
    tasas: si la norma la cambia, la corrida nueva usa la version nueva y las
    anteriores conservan la suya. Es la regla `013` del catalogo de parametros y
    la consulta abierta de `brechas-hoja-impuestos.md`.
    """

    def __post_init__(self) -> None:
        if not self.version_datos_maestros.strip():
            raise ErrorParametros(
                "Falta la version de datos maestros. Una corrida sin ella no se puede "
                "reproducir, porque no queda registro de que parametros uso."
            )
        for campo in fields(self):
            if campo.name == "version_datos_maestros":
                continue
            valor = getattr(self, campo.name)
            if not 0.0 <= valor <= 1.0:
                raise ErrorParametros(
                    f"{campo.name} vale {valor} y se espera un tanto por uno entre 0 y 1. "
                    "Una tasa del 29,5 % se escribe 0.295."
                )
