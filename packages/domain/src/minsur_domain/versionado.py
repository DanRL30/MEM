"""Versionado en tres ejes.

Una evaluación económica queda definida por tres versiones que cambian a
ritmos distintos y por decisión de actores distintos:

    motor           cambia cuando Finanzas modifica el modelo corporativo
    datos maestros  cambia con cada Comité de Precios
    inputs          cambia con cada iteración del Líder de Estudio

Registrarlas por separado no es un lujo de trazabilidad: es lo que permite
cumplir el requisito del alcance de que **los cambios que Finanzas introduzca
en el modelo no alteren evaluaciones previas**. Si la corrida guardara solo
"la versión vigente", publicar una versión nueva reescribiría la historia.

De ahí se derivan tres reglas que el resto del módulo hace cumplir:

1. Una corrida guarda la terna exacta con la que se calculó, no una
   referencia a "lo vigente".
2. Las versiones del motor **coexisten en producción**. Una corrida antigua
   se recalcula con su propio motor, no con el último.
3. Recalcular **nunca sobrescribe**: produce una corrida nueva que apunta a
   la anterior como origen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from typing import Self

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
ID_COMITE = re.compile(r"^CP-(\d{4})-(\d{2})$")


class ErrorVersionado(ValueError):
    """La terna de versiones es inválida o su uso viola una regla del alcance."""


# --- Eje 1 · versión del motor -----------------------------------------------


@dataclass(frozen=True, order=True)
class VersionMotor:
    """Versión de la lógica de cálculo, en correspondencia con el modelo.

    El significado de cada componente está atado a lo que cambió en el modelo
    corporativo, no a conveniencias de desarrollo:

        mayor   cambia una regla de cálculo y los resultados difieren
        menor   se añade una línea o un indicador, sin alterar los existentes
        parche  corrección de un defecto de implementación de INVA

    La distinción importa: un incremento de `mayor` significa que los casos
    certificados deben recontrastarse antes de desplegar.
    """

    mayor: int
    menor: int
    parche: int

    @classmethod
    def desde_cadena(cls, texto: str) -> Self:
        m = SEMVER.match(texto.strip())
        if not m:
            raise ErrorVersionado(
                f"Versión de motor inválida: {texto!r}. Se espera mayor.menor.parche."
            )
        return cls(int(m[1]), int(m[2]), int(m[3]))

    def __str__(self) -> str:
        return f"{self.mayor}.{self.menor}.{self.parche}"

    @property
    def altera_resultados(self) -> bool:
        """Una versión mayor 0 es preliminar: aún no certificada por Finanzas."""
        return self.mayor > 0

    def es_compatible_con(self, otra: VersionMotor) -> bool:
        """Dos versiones son compatibles si no difieren en el componente mayor.

        Solo entre versiones compatibles tiene sentido comparar resultados sin
        explicar la diferencia: un cambio de mayor implica, por definición, que
        los resultados difieren.
        """
        return self.mayor == otra.mayor


# --- Eje 2 · versión de los datos maestros -----------------------------------


@dataclass(frozen=True)
class VersionDatosMaestros:
    """Comité de Precios efectivamente utilizado en la corrida.

    El alcance exige registrar **el comité usado**, no el vigente al momento
    de consultar. Un caso evaluado en marzo con el comité de marzo debe seguir
    mostrando el comité de marzo cuando se consulte en diciembre.
    """

    id_comite: str
    fecha_vigencia: date

    def __post_init__(self) -> None:
        if not ID_COMITE.match(self.id_comite):
            raise ErrorVersionado(
                f"Identificador de comité inválido: {self.id_comite!r}. "
                "Se espera el formato CP-AAAA-NN."
            )

    def __str__(self) -> str:
        return self.id_comite


# --- Eje 3 · versión de los inputs del caso ----------------------------------


@dataclass(frozen=True)
class VersionInputs:
    """Revisión de los insumos del caso.

    El número crece con cada edición del Líder de Estudio. El resumen
    criptográfico permite detectar que dos revisiones distintas tienen, de
    hecho, el mismo contenido — algo que ocurre cuando alguien edita y
    deshace.
    """

    revision: int
    huella: str

    def __post_init__(self) -> None:
        if self.revision < 1:
            raise ErrorVersionado("La revisión de inputs empieza en 1.")
        if len(self.huella) != 64:
            raise ErrorVersionado("La huella de inputs debe ser un SHA-256 de 64 caracteres.")

    def __str__(self) -> str:
        return f"r{self.revision}"

    def siguiente(self, huella: str) -> VersionInputs:
        return replace(self, revision=self.revision + 1, huella=huella)


# --- La terna ----------------------------------------------------------------


@dataclass(frozen=True)
class TernaVersion:
    """La combinación exacta que define una corrida.

    Dos corridas con la misma terna deben producir el mismo resultado. Esa
    afirmación es la que verifica el contraste de reproducibilidad, y es la
    razón por la que el motor no puede leer nada que no esté aquí dentro.
    """

    motor: VersionMotor
    datos_maestros: VersionDatosMaestros
    inputs: VersionInputs

    def __str__(self) -> str:
        return f"{self.motor} · {self.datos_maestros} · {self.inputs}"

    @property
    def clave(self) -> str:
        """Clave estable para índices y comparaciones."""
        return f"{self.motor}|{self.datos_maestros}|{self.inputs.huella}"

    def difiere_en(self, otra: TernaVersion) -> list[str]:
        """Ejes en los que dos ternas difieren.

        Es lo que responde la pregunta que hace el usuario al comparar dos
        corridas del mismo caso: por qué dan distinto. Si la lista sale vacía
        y los resultados difieren, hay un incidente de reproducibilidad.
        """
        ejes = []
        if self.motor != otra.motor:
            ejes.append("motor")
        if self.datos_maestros != otra.datos_maestros:
            ejes.append("datos_maestros")
        if self.inputs.huella != otra.inputs.huella:
            ejes.append("inputs")
        return ejes

    def comparable_con(self, otra: TernaVersion) -> bool:
        """Si dos corridas pueden compararse sin advertencia.

        Comparar un caso base calculado con el motor 1.x contra un caso con
        proyecto calculado con el motor 2.x produce una diferencia que no es
        atribuible al proyecto. La plataforma lo advierte antes de mostrar el
        comparador.
        """
        return self.motor.es_compatible_con(otra.motor) and (
            self.datos_maestros == otra.datos_maestros
        )
