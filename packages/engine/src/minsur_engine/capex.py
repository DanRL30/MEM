"""Capital: doble clasificación, totales y las líneas que consume el flujo.

El capital del libro se clasifica dos veces sobre el mismo monto, y las dos
clasificaciones son independientes:

- **por etapa**, que es lo que ve el flujo de inversiones: capex inicial,
  sostenimiento, cierre de mina y otros;
- **por naturaleza contable**, que es lo que gobierna la depreciación: no
  depreciable, maquinaria y equipos, instalaciones y edificaciones.

Que sean independientes significa que un mismo dólar aparece en una etapa y en
una naturaleza, y que **ambas sumas tienen que dar lo mismo**. El libro lo
comprueba con una fila `Check`.

**Solo una de las dos es dato: la naturaleza.** La disección de `InputsCapex` del
02/09/2026 mostró que el libro deriva la etapa de ella, y `clasificar_por_etapa`
reproduce esa derivación. El `Check` sigue verificándose al construir el capital,
pero con las dos clasificaciones saliendo de las mismas celdas **se cumple por
construcción**: dejó de ser una comprobación y pasó a ser una condición
estructural. Se conserva porque el capital también se puede construir a mano, y
ahí sí puede descuadrar.
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


def clasificar_por_etapa(
    horizonte: Horizonte,
    por_naturaleza: Mapping[str, Serie],
    *,
    anos_activos: Sequence[int] = (),
) -> dict[str, Serie]:
    """Deriva la etapa del capital a partir de su naturaleza contable.

    El libro no carga la etapa: la calcula, con tres reglas que la disección dejó
    a la vista.

    **El cierre de mina es exactamente lo no depreciable.** No son dos conceptos
    que coincidan: en el libro la fila de cierre se construye sumando el código
    `NOD` de todas las unidades, y ninguna otra naturaleza entra ahí.

    **El capital inicial es el anterior al primer año con producción**, y el
    resto es sostenimiento. El libro lleva la cuenta con un contador escondido en
    una fila que parece una cabecera, y usa un umbral distinto para cada unidad
    sin decir por qué; aquí el primer año con producción lo aporta quien llama,
    con el criterio que Finanzas fijó el 01/09/2026.

    **La cuarta etapa no se emite.** El libro la deja sin rotular y sin fórmula:
    vale cero en todos los ejercicios y en todos los escenarios.

    Una unidad que no produce —una refinería, un depósito de relaves— no tiene
    primer año de producción, de modo que todo su capital depreciable es inicial.
    """
    primero = min(anos_activos) if anos_activos else horizonte.anos
    inicial = [0.0] * horizonte.anos
    sostenimiento = [0.0] * horizonte.anos
    for naturaleza, serie in por_naturaleza.items():
        if naturaleza == "no_depreciable":
            continue
        for i, valor in enumerate(serie[: horizonte.anos]):
            if i < primero:
                inicial[i] += valor
            else:
                sostenimiento[i] += valor
    return {
        "inicial": tuple(inicial),
        "sostenimiento": tuple(sostenimiento),
        "cierre": por_naturaleza.get("no_depreciable") or horizonte.ceros(),
    }


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
