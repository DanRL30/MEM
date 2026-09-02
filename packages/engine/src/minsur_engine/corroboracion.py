"""Recalcula lo que el usuario cargó y reporta dónde no cuadra.

Toda la producción entra como dato, incluidos los valores que el sistema sabe
derivar: el usuario carga las series tal como las tiene en su libro, donde una
fila puede ser un número escrito a mano o el resultado de un cálculo interno que
no viaja con el archivo. Este módulo rehace ese cálculo y compara.

**El dato del usuario es el que usa el flujo.** El recálculo no lo sustituye: lo
audita. Es la misma regla de fidelidad que impide corregir el modelo corporativo,
y es coherente con la desviación `D-01`, donde el LOM prevalece sobre lo calculado
en los tres primeros años.

**Corroborar nunca detiene el cálculo.** Devuelve una lista de discrepancias y la
corrida sigue. Un caso con una ley mal tecleada tiene que llegar hasta el NPV para
que se vea el efecto, no fallar en la lectura.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from minsur_engine.caso import Caso, ProduccionDeUnidad, UnidadProductiva
from minsur_engine.produccion import ley_agregada

TOLERANCIA_POR_DEFECTO = 0.005
"""Diferencia relativa a partir de la cual se reporta una celda.

Es propuesta de INVA y está consultada. No es la tolerancia del contraste N1, que
compara el motor contra el libro y la fija Finanzas (`R-31`): esta compara el dato
del usuario contra el recálculo del propio sistema, y son dos cosas distintas.
"""

_INSIGNIFICANTE = 1e-9


@dataclass(frozen=True)
class Discrepancia:
    """Una celda donde el dato cargado no coincide con el recalculado."""

    unidad: str
    concepto: str
    ano: int
    cargado: float
    recalculado: float

    @property
    def diferencia(self) -> float:
        return self.cargado - self.recalculado

    @property
    def diferencia_relativa(self) -> float:
        escala = max(abs(self.cargado), abs(self.recalculado))
        return abs(self.diferencia) / escala if escala > _INSIGNIFICANTE else 0.0

    def __str__(self) -> str:
        return (
            f"{self.unidad} · {self.concepto} · {self.ano}: cargado {self.cargado:,.2f}, "
            f"recalculado {self.recalculado:,.2f} "
            f"({self.diferencia_relativa:.2%})"
        )


def corroborar(
    caso: Caso, *, tolerancia: float = TOLERANCIA_POR_DEFECTO
) -> tuple[Discrepancia, ...]:
    """Recorre la cadena de producción del caso y devuelve lo que no cuadra.

    Una serie que la unidad no declara no produce discrepancias: significa que el
    concepto no aplica, no que valga cero. Confundir ambas cosas llenaría el
    informe de falsos positivos y lo volvería inútil.
    """
    anos = caso.horizonte.anos_calendario
    halladas: list[Discrepancia] = []
    for unidad in caso.unidades:
        halladas.extend(_de_la_unidad(unidad, anos, tolerancia))
    fundicion = caso.fundicion
    if fundicion is not None:
        halladas.extend(_del_complejo(caso, fundicion, anos, tolerancia))
    return tuple(halladas)


def _de_la_unidad(
    unidad: UnidadProductiva, anos: Sequence[int], tolerancia: float
) -> Iterator[Discrepancia]:
    produccion = unidad.produccion
    yield from _tratado_total_es_la_suma(unidad, anos, tolerancia)
    yield from _ley_del_tratado_es_la_ponderada(unidad, anos, tolerancia)
    for metal in produccion.concentrados:
        yield from _finas_son_tratado_por_ley(unidad, metal, anos, tolerancia)
        yield from _concentrado_sale_de_finas_y_recuperacion(unidad, metal, anos, tolerancia)
    yield from _concentrado_total_es_la_suma_por_metal(unidad, anos, tolerancia)


def _tratado_total_es_la_suma(
    unidad: UnidadProductiva, anos: Sequence[int], tolerancia: float
) -> Iterator[Discrepancia]:
    """`Mineral Tratado Total en Concentradora` = preconcentrado más directo."""
    produccion = unidad.produccion
    total = produccion.tratado_total
    preconcentrado = produccion.preconcentrado_a_concentradora
    directo = produccion.directo_a_concentradora
    if total is None or (preconcentrado is None and directo is None):
        return
    aportes = [c.toneladas for c in (preconcentrado, directo) if c is not None]
    for i, ano in enumerate(anos):
        esperado = sum(_en(serie, i) for serie in aportes)
        yield from _comparar(
            unidad.nombre,
            "Mineral tratado total en concentradora",
            ano,
            _en(total.toneladas, i),
            esperado,
            tolerancia,
        )


def _ley_del_tratado_es_la_ponderada(
    unidad: UnidadProductiva, anos: Sequence[int], tolerancia: float
) -> Iterator[Discrepancia]:
    """La ley del tratado total es la de sus corrientes, ponderada por tonelaje.

    El libro usa `SUMPRODUCT` sobre tonelaje y ley, no el promedio de las leyes.
    Con producción variable la diferencia entre ambas supera la tolerancia de N1.
    """
    produccion = unidad.produccion
    total = produccion.tratado_total
    corrientes = [
        c
        for c in (produccion.preconcentrado_a_concentradora, produccion.directo_a_concentradora)
        if c is not None
    ]
    if total is None or not corrientes:
        return
    for metal, ley_cargada in total.leyes.items():
        if any(metal not in c.leyes for c in corrientes):
            continue
        for i, ano in enumerate(anos):
            esperado = ley_agregada(
                [_en(c.toneladas, i) for c in corrientes],
                [_en(c.leyes[metal], i) for c in corrientes],
            )
            yield from _comparar(
                unidad.nombre,
                f"Ley de {metal} del tratado total",
                ano,
                _en(ley_cargada, i),
                esperado,
                tolerancia,
            )


def _finas_son_tratado_por_ley(
    unidad: UnidadProductiva, metal: str, anos: Sequence[int], tolerancia: float
) -> Iterator[Discrepancia]:
    """Toneladas finas = mineral tratado por su ley."""
    produccion = unidad.produccion
    concentrado = produccion.concentrados[metal]
    ley = produccion.leyes_del_tratado.get(metal, ())
    if not concentrado.toneladas_finas or not ley or not produccion.mineral_tratado:
        return
    for i, ano in enumerate(anos):
        yield from _comparar(
            unidad.nombre,
            f"Toneladas finas de {metal}",
            ano,
            _en(concentrado.toneladas_finas, i),
            _en(produccion.mineral_tratado, i) * _en(ley, i),
            tolerancia,
        )


def _concentrado_sale_de_finas_y_recuperacion(
    unidad: UnidadProductiva, metal: str, anos: Sequence[int], tolerancia: float
) -> Iterator[Discrepancia]:
    """Concentrado = finas por recuperación, dividido por la ley del concentrado."""
    concentrado = unidad.produccion.concentrados[metal]
    if not concentrado.toneladas_finas or not concentrado.recuperacion or not concentrado.ley:
        return
    for i, ano in enumerate(anos):
        ley = _en(concentrado.ley, i)
        if abs(ley) <= _INSIGNIFICANTE:
            continue
        esperado = _en(concentrado.toneladas_finas, i) * _en(concentrado.recuperacion, i) / ley
        yield from _comparar(
            unidad.nombre,
            f"Produccion de concentrado de {metal}",
            ano,
            _en(concentrado.toneladas, i),
            esperado,
            tolerancia,
        )


def _concentrado_total_es_la_suma_por_metal(
    unidad: UnidadProductiva, anos: Sequence[int], tolerancia: float
) -> Iterator[Discrepancia]:
    """Lo que la unidad entrega es la suma de sus concentrados por metal."""
    produccion = unidad.produccion
    if not produccion.concentrados or not produccion.concentrado_producido:
        return
    for i, ano in enumerate(anos):
        esperado = sum(_en(c.toneladas, i) for c in produccion.concentrados.values())
        yield from _comparar(
            unidad.nombre,
            "Produccion de concentrado",
            ano,
            _en(produccion.concentrado_producido, i),
            esperado,
            tolerancia,
        )


def _del_complejo(
    caso: Caso, fundicion: UnidadProductiva, anos: Sequence[int], tolerancia: float
) -> Iterator[Discrepancia]:
    """Lo que el complejo dice recibir de cada unidad es lo que esa unidad entrega."""
    recibido = fundicion.produccion.alimentacion_recibida
    if not recibido:
        return
    por_nombre = {u.nombre: u.produccion for u in caso.unidades_mineras}
    for origen, corriente in recibido.items():
        entregado = _entregado_por(por_nombre.get(origen))
        if entregado is None:
            continue
        for i, ano in enumerate(anos):
            yield from _comparar(
                fundicion.nombre,
                f"Concentrado alimentado desde {origen}",
                ano,
                _en(corriente.toneladas, i),
                _en(entregado, i),
                tolerancia,
            )


def _entregado_por(produccion: ProduccionDeUnidad | None) -> Sequence[float] | None:
    if produccion is None or not produccion.concentrado_producido:
        return None
    return produccion.concentrado_producido


def _comparar(
    unidad: str,
    concepto: str,
    ano: int,
    cargado: float,
    recalculado: float,
    tolerancia: float,
) -> Iterator[Discrepancia]:
    """Emite una discrepancia solo si la diferencia relativa supera la tolerancia.

    Dos ceros coinciden. Un cero contra un valor no nulo se reporta siempre, que
    es el caso de la fila que se olvidó de llenar.
    """
    escala = max(abs(cargado), abs(recalculado))
    if escala <= _INSIGNIFICANTE:
        return
    if abs(cargado - recalculado) / escala <= tolerancia:
        return
    yield Discrepancia(unidad, concepto, ano, cargado, recalculado)


def _en(serie: Sequence[float], i: int) -> float:
    """Valor del año `i`, o cero si la serie no llega.

    Una serie más corta que el horizonte no es un error aquí: el horizonte ya la
    valida al construirse, y el corroborador no debe fallar por algo que no le
    corresponde diagnosticar.
    """
    return serie[i] if i < len(serie) else 0.0
