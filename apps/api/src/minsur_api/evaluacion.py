"""Ejecución de una evaluación: del caso almacenado a la corrida registrada.

Es la costura entre la API y el motor. Aquí se mide el tiempo, se calcula la
huella de los insumos y se arma la terna de versiones; el cálculo en sí lo hace
`minsur_engine` y esta capa no reproduce ni una línea suya.

**La terna se registra, no se referencia.** Una corrida guarda la versión exacta
del motor, la de datos maestros y la revisión de inputs con las que se calculó.
Guardar «la vigente» haría que publicar una versión nueva reescribiera
evaluaciones pasadas, que es justo lo que el alcance prohíbe.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from time import perf_counter

from minsur_domain.estados import Estado
from minsur_domain.sellado import sha256
from minsur_engine import __version__ as version_del_motor
from minsur_engine.caso import Caso as CasoDelMotor, DatosMaestros
from minsur_engine.corrida import calcular

from .esquemas import EntradaHistorial, Indicadores, ResultadoEvaluacion, Terna
from .repositorio import CasoAlmacenado, CasoSinInsumos, CorridaAlmacenada, nuevo_id_de_corrida

MILLONES = 1_000_000.0


def huella_de_insumos(caso: CasoDelMotor) -> str:
    """SHA-256 de los insumos, sobre una serialización canónica.

    Dos casos con los mismos datos dan la misma huella aunque se hayan cargado
    en distinto orden, y cualquier cambio de un dato la cambia. Es lo que
    permite afirmar, años después, que una corrida se hizo con estos inputs.
    """
    return sha256(asdict(caso))


def ejecutar(
    caso: CasoAlmacenado,
    maestros: DatosMaestros,
    *,
    usuario: str,
    origen: str | None = None,
) -> CorridaAlmacenada:
    """Calcula el caso y devuelve la corrida, sin guardarla."""
    if caso.insumos is None:
        raise CasoSinInsumos(caso.id_caso)

    inicio = perf_counter()
    resultado = calcular(caso.insumos, maestros)
    duracion_ms = int((perf_counter() - inicio) * 1000)

    return CorridaAlmacenada(
        id_corrida=nuevo_id_de_corrida(),
        id_caso=caso.id_caso,
        estado=Estado.CALCULADA,
        resultado=resultado,
        version_motor=version_del_motor,
        version_datos_maestros=maestros.version,
        revision_inputs=caso.revision_inputs,
        huella_inputs=huella_de_insumos(caso.insumos),
        ejecutada_en=datetime.now(UTC),
        ejecutada_por=usuario,
        duracion_ms=duracion_ms,
        origen=origen,
    )


def indicadores_de(corrida: CorridaAlmacenada) -> Indicadores:
    """Traduce los indicadores del motor al contrato de la interfaz.

    El motor trabaja en dólares y el contrato expone millones, porque es la
    unidad en la que el negocio lee un NPV. La conversión vive aquí y no en el
    motor: cambiar cómo se presenta un número no debe tocar cómo se calcula.
    """
    indicadores = corrida.resultado.indicadores
    return Indicadores(
        npv_musd=indicadores.npv / MILLONES,
        tir=indicadores.tir if indicadores.tir is not None else 0.0,
        payback_anios=indicadores.payback.anos,
        capital_intensity=indicadores.capital_intensity or 0.0,
    )


def terna_de(corrida: CorridaAlmacenada) -> Terna:
    return Terna(
        motor=corrida.version_motor,
        datos_maestros=corrida.version_datos_maestros,
        vigencia_datos_maestros=corrida.ejecutada_en.date(),
        revision_inputs=corrida.revision_inputs,
        huella_inputs=corrida.huella_inputs,
    )


def resultado_de(corrida: CorridaAlmacenada) -> ResultadoEvaluacion:
    return ResultadoEvaluacion(
        id_corrida=corrida.id_corrida,
        id_caso=corrida.id_caso,
        estado=corrida.estado,
        terna=terna_de(corrida),
        indicadores=indicadores_de(corrida),
        ejecutada_en=corrida.ejecutada_en,
        ejecutada_por=corrida.ejecutada_por,
        duracion_ms=corrida.duracion_ms,
    )


def entrada_de_historial(corrida: CorridaAlmacenada, nombre_caso: str) -> EntradaHistorial:
    return EntradaHistorial(
        id_corrida=corrida.id_corrida,
        id_caso=corrida.id_caso,
        nombre_caso=nombre_caso,
        estado=corrida.estado,
        usuario=corrida.ejecutada_por,
        marca_tiempo=corrida.ejecutada_en,
        version_motor=corrida.version_motor,
        npv_musd=corrida.resultado.indicadores.npv / MILLONES,
    )
