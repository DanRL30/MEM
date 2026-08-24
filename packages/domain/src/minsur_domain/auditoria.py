"""Bitácora de auditoría de solo escritura.

El alcance enumera ocho requisitos de gobierno y calidad de datos. Este
módulo existe para que se cumplan de forma verificable y no por convención,
así que cada uno está mapeado a un campo concreto en `COBERTURA`:

    1. versionado de insumos
    2. registro de los parámetros efectivamente empleados
    3. identificación del responsable de la carga
    4. fecha y hora de creación y ejecución
    5. asociación de documentación de respaldo y correos de aprobación
    6. historial de cambios
    7. registro del origen de la información
    8. capacidad de reproducir los resultados con los mismos datos registrados

Dos propiedades sostienen la bitácora:

**Solo escritura.** No hay operación de modificación ni de borrado. La clase
`Bitacora` no expone ninguna, y en el almacenamiento la tabla se protege con
la misma política de anexado que el contenedor de imágenes selladas. Una
bitácora que admite correcciones no sirve como evidencia.

**Encadenada.** Cada entrada incluye el resumen de la anterior. Suprimir una
entrada intermedia rompe la cadena y la verificación lo detecta. Sin esto, un
actor con acceso al almacenamiento podría eliminar el rastro de una acción en
lugar de alterarlo, que es más difícil de notar.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Iterator

from .estados import Perfil
from .sellado import canonicalizar

GENESIS = "0" * 64


class Accion(StrEnum):
    """Acciones que dejan rastro. La consulta no se registra: con diecisiete
    usuarios consultando un tablero, registrarla ahogaría lo que importa."""

    CASO_CREADO = "caso-creado"
    CASO_DUPLICADO = "caso-duplicado"
    INSUMOS_CARGADOS = "insumos-cargados"
    INSUMOS_EDITADOS = "insumos-editados"
    PARAMETROS_CAMBIADOS = "parametros-cambiados"
    COMITE_SELECCIONADO = "comite-seleccionado"
    EVALUACION_EJECUTADA = "evaluacion-ejecutada"
    EVALUACION_CONGELADA = "evaluacion-congelada"
    EVALUACION_RECALCULADA = "evaluacion-recalculada"
    RESPALDO_ASOCIADO = "respaldo-asociado"
    REPORTE_EXPORTADO = "reporte-exportado"
    VERIFICACION_EJECUTADA = "verificacion-ejecutada"
    INCIDENTE_REPRODUCIBILIDAD = "incidente-reproducibilidad"


class Origen(StrEnum):
    """De dónde vino el dato. Requisito 7 del gobierno de datos."""

    PLANTILLA_EXCEL = "plantilla-excel"
    CAPTURA_WEB = "captura-web"
    DATO_MAESTRO = "dato-maestro"
    DUPLICADO_DE_CASO = "duplicado-de-caso"
    CALCULO = "calculo"
    SISTEMA = "sistema"


class BitacoraCorrupta(Exception):
    """La cadena de resúmenes no verifica."""


@dataclass(frozen=True)
class Entrada:
    """Un asiento de la bitácora. Inmutable por construcción."""

    id_corrida: str
    id_caso: str
    usuario: str
    perfil: Perfil
    marca_tiempo: datetime
    accion: Accion
    origen: Origen
    # Valores anterior y posterior, exigidos ante modificación de insumos o
    # parámetros. En acciones que no modifican nada quedan en None.
    valor_anterior: Any = None
    valor_posterior: Any = None
    detalle: str = ""
    # Encadenamiento
    huella_anterior: str = GENESIS
    huella: str = ""

    def _cuerpo(self) -> dict[str, Any]:
        return {
            "id_corrida": self.id_corrida,
            "id_caso": self.id_caso,
            "usuario": self.usuario,
            "perfil": str(self.perfil),
            "marca_tiempo": self.marca_tiempo,
            "accion": str(self.accion),
            "origen": str(self.origen),
            "valor_anterior": self.valor_anterior,
            "valor_posterior": self.valor_posterior,
            "detalle": self.detalle,
            "huella_anterior": self.huella_anterior,
        }

    def calcular_huella(self) -> str:
        return hashlib.sha256(canonicalizar(self._cuerpo())).hexdigest()

    def a_dict(self) -> dict[str, Any]:
        return {**self._cuerpo(), "huella": self.huella}


class Bitacora:
    """Colección de entradas encadenadas.

    No expone modificación ni borrado a propósito: la ausencia de esos métodos
    es la garantía. Persistir es responsabilidad de la capa de
    almacenamiento, que anexa a la tabla `auditoria` sin permitir reemplazo.
    """

    def __init__(self, entradas: list[Entrada] | None = None) -> None:
        self._entradas: list[Entrada] = list(entradas or [])

    def __len__(self) -> int:
        return len(self._entradas)

    def __iter__(self) -> Iterator[Entrada]:
        return iter(self._entradas)

    @property
    def ultima_huella(self) -> str:
        return self._entradas[-1].huella if self._entradas else GENESIS

    def registrar(
        self,
        id_corrida: str,
        id_caso: str,
        usuario: str,
        perfil: Perfil,
        accion: Accion,
        origen: Origen,
        valor_anterior: Any = None,
        valor_posterior: Any = None,
        detalle: str = "",
        momento: datetime | None = None,
    ) -> Entrada:
        """Anexa una entrada. Es la única operación de escritura."""
        if not usuario.strip():
            raise ValueError(
                "Toda acción registrada debe identificar a su responsable."
            )

        modifica = accion in {
            Accion.INSUMOS_EDITADOS,
            Accion.PARAMETROS_CAMBIADOS,
            Accion.COMITE_SELECCIONADO,
        }
        if modifica and valor_anterior is None and valor_posterior is None:
            raise ValueError(
                f"La acción {accion} modifica datos y debe registrar los "
                "valores anterior y posterior."
            )

        parcial = Entrada(
            id_corrida=id_corrida,
            id_caso=id_caso,
            usuario=usuario.strip(),
            perfil=perfil,
            marca_tiempo=momento or datetime.now(timezone.utc),
            accion=accion,
            origen=origen,
            valor_anterior=valor_anterior,
            valor_posterior=valor_posterior,
            detalle=detalle,
            huella_anterior=self.ultima_huella,
        )
        entrada = Entrada(
            **{**parcial.__dict__, "huella": parcial.calcular_huella()}
        )
        self._entradas.append(entrada)
        return entrada

    # --- Consulta ------------------------------------------------------------

    def de_corrida(self, id_corrida: str) -> list[Entrada]:
        return [e for e in self._entradas if e.id_corrida == id_corrida]

    def de_caso(self, id_caso: str) -> list[Entrada]:
        return [e for e in self._entradas if e.id_caso == id_caso]

    def historial_de_cambios(self, id_caso: str) -> list[Entrada]:
        """Requisito 6: historial de cambios de un caso."""
        return [
            e
            for e in self.de_caso(id_caso)
            if e.valor_anterior is not None or e.valor_posterior is not None
        ]

    # --- Verificación de la cadena -------------------------------------------

    def verificar(self) -> None:
        """Recorre la cadena y lanza si alguna entrada fue alterada o suprimida.

        Se ejecuta junto con la verificación programada de reproducibilidad:
        una bitácora rota es un incidente de la misma gravedad que una imagen
        que no reproduce.
        """
        anterior = GENESIS
        for indice, entrada in enumerate(self._entradas):
            if entrada.huella_anterior != anterior:
                raise BitacoraCorrupta(
                    f"Cadena rota en la entrada {indice} "
                    f"({entrada.accion} sobre {entrada.id_corrida}). "
                    "Falta una entrada previa o su orden fue alterado."
                )
            if entrada.huella != entrada.calcular_huella():
                raise BitacoraCorrupta(
                    f"La entrada {indice} fue modificada después de escribirse "
                    f"({entrada.accion}, {entrada.usuario}, {entrada.marca_tiempo})."
                )
            anterior = entrada.huella


# --- Cobertura de los requisitos del alcance ---------------------------------

COBERTURA: dict[int, tuple[str, str]] = {
    1: ("Versionado de insumos", "Entrada.valor_anterior / valor_posterior + VersionInputs.revision"),
    2: ("Parámetros efectivamente empleados", "Contenido.parametros de la imagen sellada, por valor"),
    3: ("Responsable de la carga", "Entrada.usuario + Entrada.perfil"),
    4: ("Fecha y hora de creación y ejecución", "Entrada.marca_tiempo en UTC"),
    5: ("Documentación de respaldo y aprobaciones", "ImagenSellada.respaldos + Accion.RESPALDO_ASOCIADO"),
    6: ("Historial de cambios", "Bitacora.historial_de_cambios"),
    7: ("Origen de la información", "Entrada.origen"),
    8: ("Reproducir con los mismos datos", "sellado.verificar_reproducibilidad"),
}


def informe_cobertura() -> str:
    """Tabla de correspondencia entre requisitos del alcance e implementación.

    Se incluye en el manual técnico y en el paquete de evidencia que se
    entrega a Seguridad de la Información.
    """
    filas = ["| # | Requisito del alcance | Dónde se cumple |", "|---|---|---|"]
    filas += [f"| {n} | {req} | `{donde}` |" for n, (req, donde) in sorted(COBERTURA.items())]
    return "\n".join(filas)
