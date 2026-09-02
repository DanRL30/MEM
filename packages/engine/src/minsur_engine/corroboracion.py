"""Rehace los cálculos de producción y avisa dónde no cuadran.

Toda la producción entra como dato, incluidos los valores que salen de un
cálculo interno: el usuario carga sus series tal como las tiene y el sistema las
rehace y compara. **Es una alarma y un control de calidad, no una corrección.**
El dato del usuario es el que usa el flujo; el recálculo lo audita.

Las ocho reglas de aquí no son una interpretación nuestra: son las fórmulas del
bloque `Cálculo Interno` del libro de producción de MINSUR, fila por fila.

    Mineral Directo             = extraído - tratado en preconcentración
    Ley del directo             = (extraído x ley - preconc x ley entrada) / directo
    Mineral Tratado Total       = directo + preconcentrado
    Ley del tratado total       = ponderado por tonelaje de las dos corrientes
    Tratado Total (Cash Cost)   = extraído
    Ley del cash cost           = ley de cabeza
    Toneladas finas             = tratado total x su ley x recuperación
    Producción Concentrado      = toneladas finas / ley del concentrado

Las divisiones van envueltas en `IFERROR(..., 0)` en el libro, y aquí un
denominador nulo devuelve cero por lo mismo: una indeterminación no puede
detener la corrida.

El bloque comercial entra en el mismo trato. La hoja `Supuestos` declara como si
fueran datos tres filas que el libro deriva, y aquí se rehacen igual:

    Ley Pagable Cu   = max(0, min(ley - deduccion minima, ley x factor pagable))
    Refinacion Cu    = tarifa por libra x 2204,62
    Refinacion Ag    = ley pagable de la plata / 31,1035 x tarifa por onza

Son las reglas 023, 021 y 022. **La ley pagable de la plata no se corrobora**: la
fórmula del libro multiplica por cien una ley que viene en onzas por tonelada, y
sin la respuesta de Finanzas —regla 045— no hay contra qué compararla.

**Corroborar nunca detiene el cálculo.** Devuelve la lista de discrepancias y la
corrida sigue, para que una ley mal tecleada llegue hasta el NPV y se vea su
efecto.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from minsur_engine.caso import (
    Caso,
    ProduccionDeUnidad,
    TerminosDelConcentrado,
    UnidadProductiva,
)
from minsur_engine.ventas import (
    cargo_de_refinacion_de_la_plata,
    cargo_de_refinacion_del_cobre,
    ley_pagable,
)

TOLERANCIA_POR_DEFECTO = 0.005
"""Diferencia relativa a partir de la cual se reporta una celda.

Es propuesta de INVA y está consultada. No es la tolerancia del contraste N1, que
compara el motor contra el libro y la fija Finanzas (`R-31`): esta compara el
dato del usuario contra el recálculo del propio sistema.
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
            f"{self.unidad} · {self.concepto} · {self.ano}: cargado {self.cargado:,.4f}, "
            f"recalculado {self.recalculado:,.4f} ({self.diferencia_relativa:.2%})"
        )


def corroborar(
    caso: Caso, *, tolerancia: float = TOLERANCIA_POR_DEFECTO
) -> tuple[Discrepancia, ...]:
    """Recorre la producción y el bloque comercial y devuelve lo que no cuadra."""
    anos = caso.horizonte.anos_calendario
    condiciones = caso.terminos.concentrado
    halladas: list[Discrepancia] = []
    for unidad in caso.unidades:
        halladas.extend(_de_la_unidad(unidad, anos, tolerancia))
        if condiciones is not None:
            halladas.extend(_del_concentrado_de(unidad, condiciones, anos, tolerancia))
    return tuple(halladas)


def _de_la_unidad(
    unidad: UnidadProductiva, anos: Sequence[int], tolerancia: float
) -> Iterator[Discrepancia]:
    p = unidad.produccion
    for i, ano in enumerate(anos):
        extraido = _en(p.mineral_extraido, i)
        ley_cabeza = _en(p.ley_de_cabeza, i)
        preconc_tratado = _en(p.tratado_en_preconcentracion, i)
        ley_entrada = _en(p.ley_de_entrada, i)
        preconcentrado = _en(p.preconcentrado, i)
        ley_preconcentrado = _en(p.ley_del_preconcentrado, i)

        directo = extraido - preconc_tratado
        ley_directo = _dividir(extraido * ley_cabeza - preconc_tratado * ley_entrada, directo)
        tratado_total = directo + preconcentrado
        ley_tratado = _dividir(
            preconcentrado * ley_preconcentrado + directo * ley_directo, tratado_total
        )
        finas = tratado_total * ley_tratado * _en(p.recuperacion, i)
        concentrado = _dividir(finas, _en(p.ley_del_concentrado, i))

        esperados = (
            ("Mineral Directo a Planta Concentradora", p.directo, directo),
            ("Ley de Sn del mineral directo", p.ley_del_directo, ley_directo),
            ("Mineral Tratado Total en Concentradora", p.tratado_total, tratado_total),
            ("Ley Sn del tratado total", p.ley_del_tratado_total, ley_tratado),
            ("Mineral Tratado Total (Cash Cost)", p.mineral_tratado, extraido),
            ("Ley Sn del cash cost", p.ley_del_cash_cost, ley_cabeza),
            ("Toneladas finas", p.toneladas_finas, finas),
            ("Produccion Concentrado", p.concentrado_producido, concentrado),
        )
        for concepto, cargada, recalculado in esperados:
            if not cargada:
                continue
            yield from _comparar(
                unidad.nombre, concepto, ano, _en(cargada, i), recalculado, tolerancia
            )


def _del_concentrado_de(
    unidad: UnidadProductiva,
    condiciones: TerminosDelConcentrado,
    anos: Sequence[int],
    tolerancia: float,
) -> Iterator[Discrepancia]:
    """Rehace las tres filas comerciales que el libro deriva y las compara.

    Solo corrobora lo que puede rehacer: sin la tarifa de refinación no hay con
    qué recalcular el cargo, y sin el factor pagable no hay con qué recalcular la
    ley. Callar es lo correcto ahí, porque una alarma contra cero diría que
    sobra un dato que en realidad falta.
    """
    if not unidad.produccion.concentrado_de_cu:
        return
    for metal in condiciones.metales:
        ley_cargada = _declarada(unidad.ley_pagable_declarada, metal.ley_pagable, metal.nombre)
        refinacion = _declarada(
            unidad.refinacion_declarada, metal.cargo_de_refinacion, metal.nombre
        )
        ley_bruta = _ley_del_concentrado(unidad, metal.nombre)
        for i, ano in enumerate(anos):
            # La ley pagable de la plata no se rehace: es la regla 045.
            if ley_cargada and metal.factor_pagable and not metal.en_onzas_troy:
                yield from _comparar(
                    unidad.nombre,
                    f"Ley Pagable {metal.nombre}",
                    ano,
                    _en(ley_cargada, i),
                    ley_pagable(
                        _en(ley_bruta, i),
                        _en(metal.deduccion_minima, i),
                        _en(metal.factor_pagable, i),
                    ),
                    tolerancia,
                )
            if refinacion and metal.tarifa_de_refinacion:
                esperado = (
                    cargo_de_refinacion_de_la_plata(
                        _en(ley_cargada, i), _en(metal.tarifa_de_refinacion, i)
                    )
                    if metal.en_onzas_troy
                    else cargo_de_refinacion_del_cobre(_en(metal.tarifa_de_refinacion, i))
                )
                yield from _comparar(
                    unidad.nombre,
                    f"Refinacion {metal.nombre}",
                    ano,
                    _en(refinacion, i),
                    esperado,
                    tolerancia,
                )


def series_comerciales_calculadas(
    unidad: UnidadProductiva, condiciones: TerminosDelConcentrado, anos: int
) -> dict[str, list[float]]:
    """Rehace las filas comerciales derivadas, para mostrarlas junto a las cargadas.

    Es la vista que acompaña a la alarma, igual que en producción: sin el valor
    recalculado, la diferencia no dice qué esperaba el sistema.
    """
    salida: dict[str, list[float]] = {}
    for metal in condiciones.metales:
        ley_cargada = _declarada(unidad.ley_pagable_declarada, metal.ley_pagable, metal.nombre)
        ley_bruta = _ley_del_concentrado(unidad, metal.nombre)
        if metal.factor_pagable and not metal.en_onzas_troy:
            salida[f"ley_pagable_{metal.nombre.lower()}"] = [
                ley_pagable(
                    _en(ley_bruta, i), _en(metal.deduccion_minima, i), _en(metal.factor_pagable, i)
                )
                for i in range(anos)
            ]
        if metal.tarifa_de_refinacion:
            salida[f"refinacion_{metal.nombre.lower()}"] = [
                cargo_de_refinacion_de_la_plata(
                    _en(ley_cargada, i), _en(metal.tarifa_de_refinacion, i)
                )
                if metal.en_onzas_troy
                else cargo_de_refinacion_del_cobre(_en(metal.tarifa_de_refinacion, i))
                for i in range(anos)
            ]
    return salida


def _declarada(
    por_unidad: Mapping[str, Sequence[float]], del_caso: Sequence[float], metal: str
) -> Sequence[float]:
    """Serie que el usuario cargó: la de la unidad manda sobre la del caso."""
    propia = por_unidad.get(metal, ())
    return propia if propia else del_caso


def _ley_del_concentrado(unidad: UnidadProductiva, metal: str) -> Sequence[float]:
    """Ley del metal en el concentrado comercial, tal como la carga producción."""
    if metal == "Cu":
        return unidad.produccion.ley_cu
    if metal == "Ag":
        return unidad.produccion.ley_ag
    return ()


def series_calculadas(produccion: ProduccionDeUnidad, anos: int) -> dict[str, list[float]]:
    """Rehace las ocho series calculadas, para mostrarlas junto a las cargadas.

    Es la vista que la plataforma pone al lado del dato del usuario cuando avisa
    de una diferencia: sin el valor recalculado, la alarma no dice qué esperaba.
    """
    salida: dict[str, list[float]] = {
        "directo": [],
        "ley_del_directo": [],
        "tratado_total": [],
        "ley_del_tratado_total": [],
        "mineral_tratado": [],
        "ley_del_cash_cost": [],
        "toneladas_finas": [],
        "concentrado_producido": [],
    }
    for i in range(anos):
        extraido = _en(produccion.mineral_extraido, i)
        ley_cabeza = _en(produccion.ley_de_cabeza, i)
        preconc_tratado = _en(produccion.tratado_en_preconcentracion, i)
        preconcentrado = _en(produccion.preconcentrado, i)

        directo = extraido - preconc_tratado
        ley_directo = _dividir(
            extraido * ley_cabeza - preconc_tratado * _en(produccion.ley_de_entrada, i), directo
        )
        tratado_total = directo + preconcentrado
        ley_tratado = _dividir(
            preconcentrado * _en(produccion.ley_del_preconcentrado, i) + directo * ley_directo,
            tratado_total,
        )
        finas = tratado_total * ley_tratado * _en(produccion.recuperacion, i)

        salida["directo"].append(directo)
        salida["ley_del_directo"].append(ley_directo)
        salida["tratado_total"].append(tratado_total)
        salida["ley_del_tratado_total"].append(ley_tratado)
        salida["mineral_tratado"].append(extraido)
        salida["ley_del_cash_cost"].append(ley_cabeza)
        salida["toneladas_finas"].append(finas)
        salida["concentrado_producido"].append(
            _dividir(finas, _en(produccion.ley_del_concentrado, i))
        )
    return salida


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


def _dividir(numerador: float, denominador: float) -> float:
    """División del libro: envuelta en `IFERROR(..., 0)`."""
    if abs(denominador) <= _INSIGNIFICANTE:
        return 0.0
    return numerador / denominador


def _en(serie: Sequence[float], i: int) -> float:
    """Valor del año `i`, o cero si la serie no llega."""
    return serie[i] if i < len(serie) else 0.0
