"""Capital: doble clasificación, totales y las líneas que consume el flujo.

El capital del libro se clasifica dos veces sobre el mismo monto, y las dos
clasificaciones son independientes:

- **por etapa**, que es lo que ve el flujo de inversiones: capex inicial,
  sostenimiento, cierre de mina y otros;
- **por naturaleza contable**, que es lo que gobierna la depreciación: no
  depreciable, maquinaria y equipos, instalaciones y edificaciones.

Que sean independientes significa que un mismo dólar aparece en una etapa y en
una naturaleza, y que **ambas sumas tienen que dar lo mismo**. El libro lo
comprueba con una fila `Check`; aquí es una condición que se verifica al
construir el capital de una unidad, porque un descuadre silencioso desplaza a la
vez el flujo de inversiones y el escudo fiscal.

La hoja `InputsCapex` no tiene ni una fórmula propia: todo su contenido son
enlaces a otros libros y valores. El capital entra al motor como dato.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from minsur_engine.horizonte import Horizonte, Serie

ETAPAS = ("inicial", "sostenimiento", "cierre", "otros")
NATURALEZAS = ("no_depreciable", "maquinaria", "instalaciones", "edificaciones")

TOLERANCIA_CUADRE = 1e-6


class ErrorCapex(ValueError):
    """El capital declarado no cuadra o no es consistente."""


@dataclass(frozen=True)
class CapitalDeUnidad:
    """Capital de una unidad productiva, en dólares, año a año.

    Las dos clasificaciones cubren el mismo monto. Se declaran ambas porque el
    libro las trae ambas y porque cada una alimenta un bloque distinto del
    cálculo.
    """

    unidad: str
    por_etapa: Mapping[str, Serie]
    por_naturaleza: Mapping[str, Serie]

    def __post_init__(self) -> None:
        for nombre, clasificacion, validos in (
            ("etapa", self.por_etapa, ETAPAS),
            ("naturaleza", self.por_naturaleza, NATURALEZAS),
        ):
            desconocidas = set(clasificacion) - set(validos)
            if desconocidas:
                raise ErrorCapex(
                    f"{self.unidad}: {nombre}(s) desconocida(s) {sorted(desconocidas)}. "
                    f"Use {', '.join(validos)}."
                )
        largos = {len(s) for s in (*self.por_etapa.values(), *self.por_naturaleza.values())}
        if len(largos) > 1:
            raise ErrorCapex(
                f"{self.unidad}: las series de capital tienen largos distintos {sorted(largos)}."
            )
        diferencia = abs(self.total_por_etapa() - self.total_por_naturaleza())
        escala = max(1.0, abs(self.total_por_etapa()))
        if diferencia > TOLERANCIA_CUADRE * escala:
            raise ErrorCapex(
                f"{self.unidad}: las dos clasificaciones del capital no cuadran. Por etapa suma "
                f"{self.total_por_etapa():,.2f} y por naturaleza {self.total_por_naturaleza():,.2f}. "
                "Es el descuadre que la fila Check del libro vigila."
            )

    def total_por_etapa(self) -> float:
        return sum(sum(serie) for serie in self.por_etapa.values())

    def total_por_naturaleza(self) -> float:
        return sum(sum(serie) for serie in self.por_naturaleza.values())

    def etapa(self, nombre: str, horizonte: Horizonte) -> Serie:
        return self.por_etapa.get(nombre) or horizonte.ceros()

    def naturaleza(self, nombre: str, horizonte: Horizonte) -> Serie:
        return self.por_naturaleza.get(nombre) or horizonte.ceros()


def capex_total(horizonte: Horizonte, unidades: Sequence[CapitalDeUnidad]) -> Serie:
    """Capital del caso, año a año, sumando las unidades que participan."""
    series = [
        tuple(sum(serie[i] for serie in unidad.por_etapa.values()) for i in range(horizonte.anos))
        for unidad in unidades
    ]
    if not series:
        return horizonte.ceros()
    return tuple(sum(valores) for valores in zip(*series, strict=True))


def capex_de_etapa(horizonte: Horizonte, unidades: Sequence[CapitalDeUnidad], etapa: str) -> Serie:
    """Capital de una etapa concreta, sumado sobre las unidades."""
    if etapa not in ETAPAS:
        raise ErrorCapex(f"Etapa {etapa!r} desconocida. Use {', '.join(ETAPAS)}.")
    series = [unidad.etapa(etapa, horizonte) for unidad in unidades]
    if not series:
        return horizonte.ceros()
    return tuple(sum(valores) for valores in zip(*series, strict=True))


def capex_de_sostenimiento(horizonte: Horizonte, unidades: Sequence[CapitalDeUnidad]) -> Serie:
    """Sostenimiento tal como lo calcula el flujo: el total menos el inicial.

    El libro no lee la fila de sostenimiento: resta el capex inicial del total.
    La diferencia importa cuando hay capital de cierre o de la categoría
    `otros`, que por esa vía quedan dentro del sostenimiento del flujo aunque
    tengan fila propia en la clasificación.
    """
    total = capex_total(horizonte, unidades)
    inicial = capex_de_etapa(horizonte, unidades, "inicial")
    return tuple(t - i for t, i in zip(total, inicial, strict=True))
