"""El bloque de la refinería: todo resultado, y componente a componente.

Ninguna fila de este bloque es un dato. La lectura de las fórmulas del libro lo
confirmó una por una: lo que alimenta a la refinería es el concentrado de cada mina
y su ley, el consolidado es la suma acotada por la capacidad, la ley promedio es
el ponderado por tonelaje, y el excedente es lo que pasa del tope. Pedir
cualquiera de ellas como entrada invitaría a que contradijese a su origen.

**Regla de oro: nada se agrupa.** Cada unidad aporta con su propia recuperación
y su aporte al refinado se calcula por separado; el total es la suma de esos
aportes y no un cálculo hecho sobre magnitudes agregadas. El libro corporativo
agrupa —lleva una `Recuperación Sn SR + B2` y otra `NZ + SRP`— y ahí está el
problema: un proyecto nuevo no cabe en ningún grupo sin decidir a cuál se parece,
y una diferencia en el total no se puede atribuir a una unidad.

Las dos únicas entradas del bloque son supuestos, no producción: la capacidad de la
refinería y la recuperación de cada componente. En el libro viven en la hoja
`Supuestos`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from minsur_engine.horizonte import Horizonte, Serie
from minsur_engine.produccion import (
    alimentacion_a_la_refineria,
    excedente_por_capacidad,
    ley_agregada,
    tratamiento_limitado,
)


@dataclass(frozen=True)
class Componente:
    """Lo que una unidad entrega a la refinería, con su propia recuperación."""

    unidad: str
    concentrado: Serie
    ley: Serie
    recuperacion: Serie = ()
    margen: Serie = ()
    """Lo que gana la refinería por refinar una tonelada de este concentrado.

    Desempata el reparto cuando dos unidades tienen la misma ley. Lo calcula
    `margen_de_refinar`; sin él, el desempate cae en el nombre, que ordena pero
    no decide nada.
    """


@dataclass(frozen=True)
class AporteALaRefineria:
    """El aporte de una unidad, calculado sin mezclarlo con el de las demás.

    Que el refinado de cada componente salga por separado es lo que permite
    atribuir una diferencia a la unidad que la produce. Un total agregado solo
    dice que algo no cuadra.
    """

    unidad: str
    concentrado: Serie
    ley: Serie
    recuperacion: Serie
    a_spot: Serie
    """Parte de su concentrado que no se refina y se vende como concentrado."""

    refinado: Serie
    """Lo que se refina de esta unidad, ya descontado lo que fue a spot."""

    refinado_sin_restriccion: Serie
    """Lo que se refinaría si la refinería no tuviera tope."""


@dataclass(frozen=True)
class BloqueDeLaRefineria:
    """El bloque completo, tal como lo escribe el libro."""

    aportes: tuple[AporteALaRefineria, ...]
    concentrado_entregado: Serie
    """Suma de lo que entregan las minas, antes del tope."""

    concentrado_alimentado: Serie
    """Lo que entra, ya acotado por la capacidad."""

    ley_de_alimentacion: Serie
    toneladas_alimentadas: Serie
    """Alimentado más escoria. En el libro la escoria no aporta nada."""

    refinado: Serie
    """Lo que la refinería refina de verdad, con el tope aplicado."""

    refinado_sin_restriccion: Serie
    """Lo que refinaría sin tope. Es la línea que el libro rotula así."""

    concentrado_excedente: Serie
    ley_del_excedente: Serie
    """Ley de lo que efectivamente fue a spot, no la del conjunto."""

    refinado_del_excedente: Serie
    """Venta spot. El libro no le aplica recuperación: es metal contenido."""

    check: Serie
    """Alimentado más excedente menos lo entregado. Debe ser cero."""


def calcular(
    horizonte: Horizonte,
    componentes: Sequence[Componente],
    capacidad: Serie = (),
) -> BloqueDeLaRefineria:
    """Rehace el bloque de la refinería a partir de lo que producen las minas.

    Sin capacidad declarada no hay cuello de botella: todo lo entregado se trata
    y el excedente es cero.
    """
    concentrados = [_serie(c.concentrado, horizonte) for c in componentes]
    entregado = alimentacion_a_la_refineria(horizonte, concentrados)
    if capacidad:
        tope = _serie(capacidad, horizonte)
        alimentado = tratamiento_limitado(entregado, tope)
        excedente = excedente_por_capacidad(entregado, tope)
    else:
        alimentado, excedente = entregado, horizonte.ceros()

    a_spot = _reparto_por_merito(componentes, excedente, horizonte)
    aportes = tuple(_aporte(c, a_spot[c.unidad], horizonte) for c in componentes)

    ley = tuple(
        ley_agregada(
            [_en(c.concentrado, i) for c in componentes],
            [_en(c.ley, i) for c in componentes],
        )
        for i in range(horizonte.anos)
    )
    ley_spot = tuple(
        ley_agregada(
            [a.a_spot[i] for a in aportes],
            [a.ley[i] for a in aportes],
        )
        for i in range(horizonte.anos)
    )

    return BloqueDeLaRefineria(
        aportes=aportes,
        concentrado_entregado=entregado,
        concentrado_alimentado=alimentado,
        ley_de_alimentacion=ley,
        toneladas_alimentadas=alimentado,
        refinado=tuple(sum(a.refinado[i] for a in aportes) for i in range(horizonte.anos)),
        refinado_sin_restriccion=tuple(
            sum(a.refinado_sin_restriccion[i] for a in aportes) for i in range(horizonte.anos)
        ),
        concentrado_excedente=excedente,
        ley_del_excedente=ley_spot,
        refinado_del_excedente=tuple(excedente[i] * ley_spot[i] for i in range(horizonte.anos)),
        check=tuple(alimentado[i] + excedente[i] - entregado[i] for i in range(horizonte.anos)),
    )


def _reparto_por_merito(
    componentes: Sequence[Componente], excedente: Serie, horizonte: Horizonte
) -> dict[str, list[float]]:
    """Reparte el recorte mandando a spot primero el concentrado de menor ley.

    Cuando las minas entregan más de lo que la refinería puede tratar, alguien se
    queda fuera, y quién se queda fuera cambia el resultado: cada unidad entrega
    concentrado de distinta ley y se refina con distinta recuperación.

    **El criterio es de mérito: se refina el mejor concentrado y se vende el
    peor.** Es lo que haría cualquier operador y es una decisión del servicio,
    no una regla del libro: el libro le resta el recorte entero a la última
    unidad en entrar, y esa asimetría no se puede generalizar a un proyecto
    nuevo. Queda registrada como desviación acordada.

    Con leyes iguales decide el **margen por tonelada**: entre dos concentrados
    del mismo contenido se refina el que más deja y se vende el otro. Con la
    misma ley, esa diferencia es la de sus recuperaciones, que es exactamente lo
    que debe decidir. El nombre queda como último desempate, y solo para que dos
    corridas del mismo caso den lo mismo.

    **El análisis es de cada año y solo de ese año.** El orden se decide con las
    leyes de ese ejercicio y el excedente de ese ejercicio; nada se arrastra del
    anterior. Una unidad que no produce ese año no cede nada, aunque haya sido la
    de menor ley en otros: en el modelo, B2 tiene cinco años con dato sobre un
    horizonte de treinta y siete, y en los demás el recorte lo absorbe quien
    corresponda entre las que sí están produciendo.

    El empate se resuelve por nombre, para que dos corridas del mismo caso den
    exactamente lo mismo.
    """
    reparto = {c.unidad: [0.0] * horizonte.anos for c in componentes}
    for i in range(horizonte.anos):
        resto = excedente[i]
        if resto <= 0.0:
            continue
        # Solo entran al reparto las que entregan concentrado ese año. Sin este
        # filtro, una unidad parada ordenaria primero -su ley es cero- y no
        # cederia nada, dejando el orden real escondido detras de ella.
        activas = [c for c in componentes if _en(c.concentrado, i) > 0.0]
        orden = sorted(activas, key=lambda c: (_en(c.ley, i), _en(c.margen, i), c.unidad))
        for componente in orden:
            if resto <= 0.0:
                break
            cede = min(_en(componente.concentrado, i), resto)
            reparto[componente.unidad][i] = cede
            resto -= cede
    return reparto


def _aporte(
    componente: Componente, a_spot: Sequence[float], horizonte: Horizonte
) -> AporteALaRefineria:
    """El refinado de una unidad, con su recuperación y solo la suya."""
    concentrado = _serie(componente.concentrado, horizonte)
    ley = _serie(componente.ley, horizonte)
    recuperacion = _serie(componente.recuperacion, horizonte)
    return AporteALaRefineria(
        unidad=componente.unidad,
        concentrado=concentrado,
        ley=ley,
        recuperacion=recuperacion,
        a_spot=tuple(a_spot),
        refinado=tuple(
            (concentrado[i] - a_spot[i]) * ley[i] * recuperacion[i] for i in range(horizonte.anos)
        ),
        refinado_sin_restriccion=tuple(
            concentrado[i] * ley[i] * recuperacion[i] for i in range(horizonte.anos)
        ),
    )


def margen_de_refinar(
    horizonte: Horizonte,
    ley: Serie,
    recuperacion: Serie,
    *,
    precio_refinado: Serie,
    premio: Serie,
    precio_en_concentrado: Serie,
    factor_pagable: Serie,
) -> Serie:
    """Lo que deja refinar una tonelada de concentrado en vez de venderla.

    Refinarla rinde `ley x recuperacion` toneladas de metal, que se cobran al
    precio mas el premio. Venderla como concentrado rinde `ley` toneladas de
    contenido, de las que se paga la fraccion pagable. La diferencia es lo que
    la refinería gana por tratarla, y es lo que decide a quien conviene refinar
    cuando dos concentrados tienen la misma ley.

    **Falta el cargo de tratamiento**, que va por tonelada de concentrado y vive
    en la hoja `Supuestos`, sin plantilla todavia. Mientras sea el mismo para
    todos los origenes se cancela al comparar y no altera el orden; solo importa
    si difiere por origen, que es justo lo que esa hoja tiene que decir.
    """
    ley = _serie(ley, horizonte)
    recuperacion = _serie(recuperacion, horizonte)
    precio_refinado = _serie(precio_refinado, horizonte)
    premio = _serie(premio, horizonte)
    precio_en_concentrado = _serie(precio_en_concentrado, horizonte)
    factor_pagable = _serie(factor_pagable, horizonte)
    return tuple(
        (precio_refinado[i] + premio[i]) * ley[i] * recuperacion[i]
        - precio_en_concentrado[i] * factor_pagable[i] * ley[i]
        for i in range(horizonte.anos)
    )


def _serie(valores: Serie, horizonte: Horizonte) -> Serie:
    return horizonte.ceros() if not valores else valores


def _en(serie: Serie, i: int) -> float:
    return serie[i] if i < len(serie) else 0.0
