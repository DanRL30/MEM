"""Incidencias de lectura: qué falló, en qué celda y por qué.

Una plantilla se llena a mano y llega con varios errores a la vez. Devolverlos
de uno en uno obliga al usuario a corregir, reenviar y esperar tantas veces
como errores tenga, que es la forma más rápida de que deje de usar la
plataforma y vuelva al Excel.

Por eso la lectura **acumula** y devuelve todas las incidencias juntas, cada
una con su hoja y su celda: el usuario abre la plantilla, va a la celda y
corrige. Sin la celda, un mensaje de error sobre una hoja de mil filas no sirve
de nada.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Incidencia:
    """Un problema concreto, localizado en la plantilla."""

    hoja: str
    celda: str
    mensaje: str

    def __str__(self) -> str:
        return f"{self.hoja}!{self.celda}: {self.mensaje}"


class ErrorDePlantilla(ValueError):
    """La plantilla no se puede convertir en un caso.

    Lleva la lista completa de incidencias, no solo la primera.
    """

    def __init__(self, incidencias: tuple[Incidencia, ...]) -> None:
        self.incidencias = incidencias
        detalle = "\n".join(f"  - {i}" for i in incidencias)
        super().__init__(f"La plantilla tiene {len(incidencias)} incidencia(s):\n{detalle}")
