"""Imagen sellada de una evaluación congelada.

El alcance exige que una evaluación usada como sustento de decisión se
preserve de forma permanente e inmutable, y que pueda **reproducirse**: que
recalcularla dentro de cinco años dé el mismo resultado.

Reproducir exige dos cosas. Que la imagen contenga todo lo necesario —no una
referencia a algo que puede cambiar— y que el resumen criptográfico sea
estable. Lo segundo es donde este módulo pone el cuidado.

## Por qué la serialización canónica es el punto delicado

Un SHA-256 sobre `json.dumps(datos)` parece suficiente y no lo es. El mismo
contenido produce hashes distintos si cambia el orden de las claves, si el
separador lleva espacio, si un float se escribe `0.1` en una versión de Python
y `0.10000000000000001` en otra, o si una fecha se serializa con zona horaria
local en un servidor y en UTC en otro.

Nada de eso es hipotético a cinco años vista. La verificación programada de
reproducibilidad reportaría incidentes que no son incidentes, y el mecanismo
perdería credibilidad justo cuando hace falta.

`canonicalizar` fija esas cuatro decisiones de forma explícita.

## Dos resúmenes, no uno

    huella_contenido   cubre lo que hace falta para reproducir el cálculo
    huella_sello       cubre la imagen completa, metadatos incluidos

El primero responde «¿el recálculo da lo mismo?». El segundo, «¿alguien tocó
la imagen?». Confundirlos haría que un cambio de metadato pareciera una
divergencia de cálculo.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from .versionado import TernaVersion

VERSION_FORMATO = "1.0"

# Decimales a los que se normaliza cualquier float antes de serializar.
# Doce dígitos exceden con holgura la precisión significativa de una
# evaluación económica y quedan muy por debajo del límite donde el doble
# precisión pierde exactitud, de modo que la normalización nunca altera un
# resultado que importe.
DECIMALES = 12


class ErrorSellado(Exception):
    """La imagen no puede sellarse o su verificación falló."""


# --- Serialización canónica --------------------------------------------------


def _normalizar(valor: Any) -> Any:
    """Reduce el valor a un tipo con representación textual única."""
    if valor is None or isinstance(valor, (bool, str, int)):
        return valor

    if isinstance(valor, float):
        if math.isnan(valor):
            raise ErrorSellado(
                "Un resultado contiene NaN. Una evaluación con valores "
                "indefinidos no puede congelarse como sustento de decisión."
            )
        if math.isinf(valor):
            raise ErrorSellado("Un resultado contiene infinito.")
        redondeado = round(valor, DECIMALES)
        # -0.0 y 0.0 son iguales para el cálculo pero distintos al imprimirse.
        return 0.0 if redondeado == 0 else redondeado

    if isinstance(valor, datetime):
        # Toda marca de tiempo se guarda en UTC. Una ingenua se rechaza en
        # lugar de suponerle una zona: suponer es lo que produce divergencias
        # entre el servidor que selló y el que verifica.
        if valor.tzinfo is None:
            raise ErrorSellado(
                "Marca de tiempo sin zona horaria. Use UTC explícito."
            )
        return valor.astimezone(UTC).isoformat(timespec="microseconds")

    if isinstance(valor, date):
        return valor.isoformat()

    if isinstance(valor, dict):
        return {str(k): _normalizar(v) for k, v in valor.items()}

    if isinstance(valor, (list, tuple)):
        return [_normalizar(v) for v in valor]

    # numpy y pandas exponen tolist() y devuelven tipos nativos de Python.
    if hasattr(valor, "tolist"):
        return _normalizar(valor.tolist())

    raise ErrorSellado(
        f"Tipo no serializable en la imagen: {type(valor).__name__}. "
        "Conviértalo a un tipo nativo antes de sellar."
    )


def canonicalizar(datos: Any) -> bytes:
    """Representación byte a byte única de una estructura de datos.

    Cuatro decisiones fijadas de forma explícita:

    - claves ordenadas, para que el orden de inserción no influya
    - sin espacios en los separadores
    - sin escapar caracteres no ASCII, con codificación UTF-8
    - floats normalizados y fechas en UTC, resueltos en `_normalizar`
    """
    return json.dumps(
        _normalizar(datos),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256(datos: Any) -> str:
    return hashlib.sha256(canonicalizar(datos)).hexdigest()


# --- La imagen ---------------------------------------------------------------


@dataclass(frozen=True)
class Contenido:
    """Lo que hace falta para reproducir el cálculo, y nada más.

    Si algo no está aquí, el recálculo dependería de leerlo de otro sitio, y
    ese otro sitio puede haber cambiado. Es la razón de que los parámetros se
    guarden por valor y no por referencia al Comité de Precios: el comité es
    un registro maestro que se consulta, la imagen es evidencia que se
    conserva.
    """

    id_caso: str
    terna: TernaVersion
    inputs: dict[str, Any]
    parametros: dict[str, Any]
    resultados: dict[str, Any]

    def a_dict(self) -> dict[str, Any]:
        return {
            "id_caso": self.id_caso,
            "version_motor": str(self.terna.motor),
            "version_datos_maestros": str(self.terna.datos_maestros),
            "vigencia_datos_maestros": self.terna.datos_maestros.fecha_vigencia,
            "revision_inputs": self.terna.inputs.revision,
            "huella_inputs": self.terna.inputs.huella,
            "inputs": self.inputs,
            "parametros": self.parametros,
            "resultados": self.resultados,
        }


@dataclass(frozen=True)
class Respaldo:
    """Documento asociado a la evaluación.

    Cubre el requisito de gobierno de asociar documentación de respaldo y
    correos de aprobación. Se referencia por ruta y huella: el documento vive
    en el almacenamiento, la imagen guarda la prueba de cuál era.
    """

    tipo: str
    nombre: str
    ruta_blob: str
    sha256: str


@dataclass(frozen=True)
class ImagenSellada:
    """Paquete autocontenido de una evaluación congelada."""

    contenido: Contenido
    congelada_por: str
    congelada_en: datetime
    motivo: str
    respaldos: tuple[Respaldo, ...] = field(default_factory=tuple)
    version_formato: str = VERSION_FORMATO

    # Se calculan al sellar; no se reciben desde fuera.
    huella_contenido: str = ""
    huella_sello: str = ""

    def _cuerpo_sello(self) -> dict[str, Any]:
        return {
            "version_formato": self.version_formato,
            "contenido": self.contenido.a_dict(),
            "huella_contenido": self.huella_contenido,
            "congelada_por": self.congelada_por,
            "congelada_en": self.congelada_en,
            "motivo": self.motivo,
            "respaldos": [
                {
                    "tipo": r.tipo,
                    "nombre": r.nombre,
                    "ruta_blob": r.ruta_blob,
                    "sha256": r.sha256,
                }
                for r in sorted(self.respaldos, key=lambda r: r.ruta_blob)
            ],
        }

    def a_dict(self) -> dict[str, Any]:
        return {**self._cuerpo_sello(), "huella_sello": self.huella_sello}

    def serializar(self) -> bytes:
        """Bytes que se depositan en el contenedor inmutable."""
        return canonicalizar(self.a_dict())


def sellar(
    contenido: Contenido,
    congelada_por: str,
    motivo: str,
    respaldos: tuple[Respaldo, ...] = (),
    momento: datetime | None = None,
) -> ImagenSellada:
    """Construye la imagen y calcula sus dos resúmenes.

    `momento` se acepta como parámetro para que las pruebas sean
    deterministas. En operación no se pasa y se toma el reloj en UTC.
    """
    if not congelada_por.strip():
        raise ErrorSellado("El congelamiento debe registrar a su responsable.")
    if not motivo.strip():
        raise ErrorSellado(
            "El congelamiento debe registrar su motivo: es lo que explica, "
            "años después, qué decisión sustentó esta evaluación."
        )

    huella_contenido = sha256(contenido.a_dict())

    parcial = ImagenSellada(
        contenido=contenido,
        congelada_por=congelada_por.strip(),
        congelada_en=(momento or datetime.now(UTC)),
        motivo=motivo.strip(),
        respaldos=respaldos,
        huella_contenido=huella_contenido,
    )
    huella_sello = sha256(parcial._cuerpo_sello())

    return ImagenSellada(
        contenido=parcial.contenido,
        congelada_por=parcial.congelada_por,
        congelada_en=parcial.congelada_en,
        motivo=parcial.motivo,
        respaldos=parcial.respaldos,
        huella_contenido=huella_contenido,
        huella_sello=huella_sello,
    )


# --- Verificación ------------------------------------------------------------


@dataclass(frozen=True)
class Veredicto:
    integra: bool
    reproducible: bool | None
    detalle: str

    @property
    def es_incidente(self) -> bool:
        return not self.integra or self.reproducible is False


def verificar_integridad(imagen: ImagenSellada) -> Veredicto:
    """Comprueba que la imagen no fue alterada desde que se selló."""
    esperado_contenido = sha256(imagen.contenido.a_dict())
    if esperado_contenido != imagen.huella_contenido:
        return Veredicto(
            integra=False,
            reproducible=None,
            detalle=(
                "El contenido no corresponde a su huella. La imagen fue "
                f"alterada. Esperado {imagen.huella_contenido[:16]}…, "
                f"obtenido {esperado_contenido[:16]}…"
            ),
        )

    esperado_sello = sha256(imagen._cuerpo_sello())
    if esperado_sello != imagen.huella_sello:
        return Veredicto(
            integra=False,
            reproducible=None,
            detalle=(
                "Los metadatos del sello no corresponden a su huella. El "
                "contenido está intacto, pero alguien modificó la autoría, la "
                "marca de tiempo, el motivo o los respaldos."
            ),
        )

    return Veredicto(integra=True, reproducible=None, detalle="Imagen íntegra.")


def verificar_reproducibilidad(
    imagen: ImagenSellada, resultados_recalculados: dict[str, Any]
) -> Veredicto:
    """Compara el resultado de recalcular contra lo sellado.

    El alcance pide que la reproducibilidad **se verifique de forma activa y
    no se presuma**. Esta función es la que ejecuta la verificación programada
    sobre una muestra de las evaluaciones congeladas.

    La comparación es de igualdad exacta sobre la forma canónica, no por
    tolerancia. La tolerancia tiene sentido al contrastar contra el modelo de
    referencia, donde hay dos implementaciones distintas; aquí es la misma
    implementación con las mismas entradas, y cualquier diferencia es un
    hallazgo.
    """
    integridad = verificar_integridad(imagen)
    if not integridad.integra:
        return integridad

    sellados = canonicalizar(imagen.contenido.resultados)
    recalculados = canonicalizar(resultados_recalculados)

    if sellados == recalculados:
        return Veredicto(
            integra=True,
            reproducible=True,
            detalle=(
                f"Recalculada con el motor {imagen.contenido.terna.motor}, "
                "reproduce el resultado sellado."
            ),
        )

    divergentes = _lineas_divergentes(
        imagen.contenido.resultados, resultados_recalculados
    )
    return Veredicto(
        integra=True,
        reproducible=False,
        detalle=(
            f"El recálculo diverge del sello en {len(divergentes)} línea(s): "
            f"{', '.join(divergentes[:8])}"
            + ("…" if len(divergentes) > 8 else "")
        ),
    )


def _lineas_divergentes(sellados: dict, recalculados: dict, prefijo: str = "") -> list[str]:
    """Localiza las líneas que difieren, para que el incidente sea accionable."""
    rutas: list[str] = []
    for clave in sorted(set(sellados) | set(recalculados)):
        ruta = f"{prefijo}{clave}"
        a, b = sellados.get(clave), recalculados.get(clave)
        if isinstance(a, dict) and isinstance(b, dict):
            rutas.extend(_lineas_divergentes(a, b, f"{ruta}."))
        elif canonicalizar(a) != canonicalizar(b):
            rutas.append(ruta)
    return rutas
