"""Almacén de casos y corridas, con su costura para la persistencia definitiva.

La plataforma guarda casos, sus insumos y las corridas que producen. El destino
de eso es Azure SQL, que no existe todavía: aprovisionarlo depende de la
aprobación del artefacto de arquitectura y de las habilitaciones de TI (`R-23`).

Mientras tanto el servicio corre contra el entorno espejo de INVA con un
almacén en memoria. **No es persistencia**: lo que guarda se pierde al
reiniciar, y por eso el adaptador lo dice en su nombre y no en un comentario.
Lo que sí es definitivo es el puerto: `RepositorioDeCasos` fija qué necesita la
API, y el adaptador de Azure SQL entrará por ahí sin tocar un router.

Una corrida guarda su terna de versiones y **nunca se sobrescribe**: recalcular
crea una corrida nueva que apunta a la anterior como origen, que es la regla del
alcance que hace que publicar una versión del motor no altere lo ya decidido.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from minsur_domain.estados import Estado
from minsur_engine.caso import Caso as CasoDelMotor
from minsur_engine.corrida import Corrida


class ErrorDeRepositorio(Exception):
    """La operación pedida no es posible sobre el estado almacenado."""


class CasoNoEncontrado(ErrorDeRepositorio):
    """No existe un caso con ese identificador."""


class CasoSinInsumos(ErrorDeRepositorio):
    """El caso existe pero no tiene inputs cargados, así que no se puede calcular."""


@dataclass(frozen=True)
class CasoAlmacenado:
    """Un caso tal como lo guarda la plataforma."""

    id_caso: str
    nombre: str
    tipo: str
    descripcion: str
    estado: Estado
    actualizado_en: datetime
    actualizado_por: str
    insumos: CasoDelMotor | None = None
    """Datos del caso ya validados por la ingesta. Sin ellos no hay cálculo."""

    revision_inputs: int = 1


@dataclass(frozen=True)
class CorridaAlmacenada:
    """Una ejecución del motor sobre un caso, con su terna y su resultado."""

    id_corrida: str
    id_caso: str
    estado: Estado
    resultado: Corrida
    version_motor: str
    version_datos_maestros: str
    revision_inputs: int
    huella_inputs: str
    ejecutada_en: datetime
    ejecutada_por: str
    duracion_ms: int
    origen: str | None = None
    """Corrida de la que esta se recalculó. Presente solo en las derivadas."""


class RepositorioDeCasos(Protocol):
    """Lo que la API necesita guardar y recuperar.

    Es el contrato que cumplirá el adaptador de Azure SQL. Mantenerlo estrecho
    es lo que permite que ese cambio no toque los routers.
    """

    def listar(self, *, tipo: str | None = None) -> list[CasoAlmacenado]: ...

    def obtener(self, id_caso: str) -> CasoAlmacenado: ...

    def guardar(self, caso: CasoAlmacenado) -> CasoAlmacenado: ...

    def registrar_corrida(self, corrida: CorridaAlmacenada) -> CorridaAlmacenada: ...

    def corridas_de(self, id_caso: str) -> list[CorridaAlmacenada]: ...

    def ultima_corrida(self, id_caso: str) -> CorridaAlmacenada | None: ...

    def historial(self, *, limite: int, desde: int = 0) -> tuple[list[CorridaAlmacenada], int]: ...


@dataclass
class RepositorioEnMemoria:
    """Adaptador para el entorno espejo. No sobrevive a un reinicio.

    Existe para que el resto de la plataforma se construya y se demuestre sin
    esperar al tenant de MINSUR, que es lo que decidió el plan de cierre del
    01/09/2026.
    """

    casos: dict[str, CasoAlmacenado] = field(default_factory=dict)
    corridas: list[CorridaAlmacenada] = field(default_factory=list)

    def listar(self, *, tipo: str | None = None) -> list[CasoAlmacenado]:
        casos = [c for c in self.casos.values() if tipo is None or c.tipo == tipo]
        return sorted(casos, key=lambda c: c.actualizado_en, reverse=True)

    def obtener(self, id_caso: str) -> CasoAlmacenado:
        caso = self.casos.get(id_caso)
        if caso is None:
            raise CasoNoEncontrado(id_caso)
        return caso

    def guardar(self, caso: CasoAlmacenado) -> CasoAlmacenado:
        self.casos[caso.id_caso] = caso
        return caso

    def registrar_corrida(self, corrida: CorridaAlmacenada) -> CorridaAlmacenada:
        self.corridas.append(corrida)
        caso = self.obtener(corrida.id_caso)
        self.guardar(
            replace(
                caso,
                estado=corrida.estado,
                actualizado_en=corrida.ejecutada_en,
                actualizado_por=corrida.ejecutada_por,
            )
        )
        return corrida

    def corridas_de(self, id_caso: str) -> list[CorridaAlmacenada]:
        return [c for c in self.corridas if c.id_caso == id_caso]

    def ultima_corrida(self, id_caso: str) -> CorridaAlmacenada | None:
        corridas = self.corridas_de(id_caso)
        return corridas[-1] if corridas else None

    def historial(self, *, limite: int, desde: int = 0) -> tuple[list[CorridaAlmacenada], int]:
        ordenadas = sorted(self.corridas, key=lambda c: c.ejecutada_en, reverse=True)
        return ordenadas[desde : desde + limite], len(ordenadas)


def nuevo_id_de_caso(tipo: str) -> str:
    """Identificador legible, con el tipo y un sufijo único.

    Un identificador que se lee en un correo o en un acta ahorra abrir la
    plataforma para saber de qué caso se habla.
    """
    # Tres letras y no dos: `CASO-CP-...` se confundiria en un correo con un
    # comite de precios, que se cita como `CP-2026-09`. El identificador existe
    # justamente para leerse fuera de la plataforma.
    prefijo = {"sin-proyecto": "SIN", "con-proyecto": "CON"}.get(tipo, "CAS")
    ano = datetime.now(UTC).year
    return f"CASO-{prefijo}-{ano}-{uuid4().hex[:6].upper()}"


def nuevo_id_de_corrida() -> str:
    return f"RUN-{uuid4().hex[:12].upper()}"
