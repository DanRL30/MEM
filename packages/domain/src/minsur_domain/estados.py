"""Máquina de estados de una evaluación económica.

El alcance exige que el congelamiento sea una **transición irreversible con
respaldo tecnológico, no un atributo editable**. Este módulo hace cumplir la
primera mitad de esa frase: qué transiciones existen, quién puede ejecutarlas
y cuáles no tienen retorno. La segunda mitad —que ni un administrador de la
suscripción pueda alterar lo congelado— la sostiene la política de
inmutabilidad del almacenamiento, no el código.

    +-----------+  ejecutar   +------------+  congelar   +-----------+
    | BORRADOR  |------------>| CALCULADA  |------------>| CONGELADA |
    +-----------+             +------------+             +-----------+
          ^   editar insumos        |                          |
          +-------------------------+                     (terminal)

Recalcular una corrida congelada **no la modifica**: crea una corrida nueva
en estado CALCULADA que apunta a la anterior como origen. Es la única forma de
que el usuario pueda ver el efecto de un cambio del modelo sin que la
evidencia que sustentó una decisión deje de existir.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Estado(StrEnum):
    BORRADOR = "borrador"
    CALCULADA = "calculada"
    CONGELADA = "congelada"


class Perfil(StrEnum):
    """Los seis perfiles del alcance."""

    ADMINISTRADOR = "administrador"
    FINANZAS = "finanzas"
    LIDER_DE_ESTUDIO = "lider-de-estudio"
    INGENIERO_DE_PROYECTO = "ingeniero-de-proyecto"
    CONSULTA_EJECUTIVA = "consulta-ejecutiva"
    AUDITOR = "auditor"


class Accion(StrEnum):
    EJECUTAR = "ejecutar"
    EDITAR_INSUMOS = "editar-insumos"
    CONGELAR = "congelar"
    RECALCULAR = "recalcular"


class TransicionInvalida(Exception):
    """La transición no existe desde el estado actual."""


class PerfilNoAutorizado(Exception):
    """El perfil no puede ejecutar esa acción."""


@dataclass(frozen=True)
class Transicion:
    desde: Estado
    accion: Accion
    hasta: Estado
    perfiles: frozenset[Perfil]
    irreversible: bool = False


# Congelar corresponde a quien sustenta la decisión de inversión, no a quien
# opera la plataforma: el Ingeniero de Proyecto carga y ejecuta, el Líder de
# Estudio es quien declara que una evaluación respalda una decisión.
#
# Finanzas no aparece aquí a propósito. Gobierna los parámetros maestros y la
# versión del motor —eso vive en otra máquina de estados— pero no congela
# evaluaciones del área de Proyectos.
TRANSICIONES: tuple[Transicion, ...] = (
    Transicion(
        desde=Estado.BORRADOR,
        accion=Accion.EJECUTAR,
        hasta=Estado.CALCULADA,
        perfiles=frozenset(
            {Perfil.ADMINISTRADOR, Perfil.LIDER_DE_ESTUDIO, Perfil.INGENIERO_DE_PROYECTO}
        ),
    ),
    Transicion(
        desde=Estado.CALCULADA,
        accion=Accion.EDITAR_INSUMOS,
        hasta=Estado.BORRADOR,
        perfiles=frozenset(
            {Perfil.ADMINISTRADOR, Perfil.LIDER_DE_ESTUDIO, Perfil.INGENIERO_DE_PROYECTO}
        ),
    ),
    Transicion(
        desde=Estado.CALCULADA,
        accion=Accion.CONGELAR,
        hasta=Estado.CONGELADA,
        perfiles=frozenset({Perfil.ADMINISTRADOR, Perfil.LIDER_DE_ESTUDIO}),
        irreversible=True,
    ),
)

# Perfiles sin capacidad de modificación en ningún estado.
SOLO_LECTURA: frozenset[Perfil] = frozenset({Perfil.CONSULTA_EJECUTIVA, Perfil.AUDITOR})


def transiciones_desde(estado: Estado) -> tuple[Transicion, ...]:
    return tuple(t for t in TRANSICIONES if t.desde == estado)


def acciones_disponibles(estado: Estado, perfil: Perfil) -> tuple[Accion, ...]:
    """Acciones que el perfil puede ejecutar sobre una corrida en ese estado.

    La interfaz consume esta función para decidir qué controles muestra. Que
    un botón no aparezca no sustituye a la verificación del servidor, que
    ocurre en `verificar`.
    """
    if perfil in SOLO_LECTURA:
        return ()
    disponibles = tuple(t.accion for t in transiciones_desde(estado) if perfil in t.perfiles)
    if estado is Estado.CONGELADA:
        # Recalcular no es una transición: crea una corrida nueva. Se ofrece
        # desde el estado congelado porque es donde el usuario la necesita.
        return (Accion.RECALCULAR,)
    return disponibles


def verificar(estado: Estado, accion: Accion, perfil: Perfil) -> Estado:
    """Valida la transición y devuelve el estado resultante.

    Lanza en lugar de devolver un booleano: una transición no autorizada es un
    error de programa o un intento de elusión, nunca un caso esperado que el
    llamador deba manejar con un `if`.
    """
    if accion is Accion.RECALCULAR:
        if estado is not Estado.CONGELADA:
            raise TransicionInvalida(
                "Recalcular solo aplica a una corrida congelada. "
                f"Esta se encuentra en estado {estado}."
            )
        if perfil in SOLO_LECTURA:
            raise PerfilNoAutorizado(
                f"El perfil {perfil} es de consulta y no puede generar corridas."
            )
        # No transiciona: la corrida congelada permanece intacta.
        return Estado.CONGELADA

    candidatas = [t for t in TRANSICIONES if t.desde == estado and t.accion == accion]
    if not candidatas:
        if estado is Estado.CONGELADA:
            raise TransicionInvalida(
                "Una evaluación congelada no admite modificaciones. "
                "Para ver el efecto de un cambio, recalcúlela: se generará una "
                "corrida nueva y esta permanecerá como sustento."
            )
        raise TransicionInvalida(f"No existe la acción {accion} desde el estado {estado}.")

    transicion = candidatas[0]
    if perfil not in transicion.perfiles:
        autorizados = ", ".join(sorted(p.value for p in transicion.perfiles))
        raise PerfilNoAutorizado(
            f"El perfil {perfil} no puede {accion}. Autorizados: {autorizados}."
        )
    return transicion.hasta


def es_irreversible(estado: Estado, accion: Accion) -> bool:
    return any(t.irreversible for t in TRANSICIONES if t.desde == estado and t.accion == accion)
