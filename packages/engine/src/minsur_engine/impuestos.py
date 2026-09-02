"""Tributos y la circularidad del modelo, resuelta en forma cerrada.

Este es el bloque delicado del motor. La hoja `Impuestos` del libro corporativo
encadena regalía minera, impuesto especial a la minería, fondo de jubilación
minera, participación de trabajadores e impuesto a la renta, y **se muerde la
cola**: el fondo de jubilación es gasto deducible de la utilidad operativa que
sirve de base para calcular... el propio fondo.

El libro cierra ese ciclo con el cálculo iterativo de Excel. El motor no:
resuelve el sistema exactamente, según [ADR 0009](../../../../docs/adr/0009-resolucion-de-la-circularidad-tributaria.md).

## Dónde está el ciclo, exactamente

Al derivarlo se vio que no es el que se suponía. La participación de
trabajadores y el impuesto a la renta **no** se realimentan: cuelgan del final
de la cadena y nadie los vuelve a leer. El único lazo lo cierra el fondo de
jubilación minera:

    utilidad operativa --> margen --> regalía e IEM --> utilidad imponible
           ^                                                  |
           |                                                  v
           +------------- fondo de jubilación minera ---------+

## Por qué el sistema es afín, aunque no lo parezca

La tasa efectiva de regalía sale de una tabla de tramos sobre el **margen**
operativo, y el libro la calcula como `SUM(tramos) / margen` para después
multiplicarla por la utilidad operativa. Escrito así parece cuadrático: una
tasa que depende de `utilidad / ventas`, multiplicada por la utilidad.

No lo es. Dentro de un tramo, la suma de tramos es afín en el margen, y al
dividir por el margen y volver a multiplicar por la utilidad, el margen se
cancela contra sí mismo:

    regalía = [(C + t·m) / m] · U  =  V·C + t·U        con m = U / V

que es afín en la utilidad operativa. Esa cancelación es la razón de que la
solución cerrada exista, y es también la razón por la que conviene no
"simplificar" la fórmula del libro al implementarla.

Lo que queda es una ecuación afín a trozos en una sola incógnita, la utilidad
operativa. Se resuelve por tramo y se acepta la solución consistente.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

TOLERANCIA_CONSISTENCIA = 1e-9


class ErrorTributos(ValueError):
    """El sistema tributario no tiene solución consistente, o los datos no lo permiten."""


@dataclass(frozen=True)
class Tramo:
    """Tramo de una escala progresiva sobre el margen operativo."""

    limite_inferior: float
    limite_superior: float
    tasa: float

    def __post_init__(self) -> None:
        if self.limite_superior <= self.limite_inferior:
            raise ErrorTributos(
                f"Tramo invertido: {self.limite_inferior} a {self.limite_superior}."
            )
        if not 0.0 <= self.tasa <= 1.0:
            raise ErrorTributos(f"Tasa de tramo fuera de rango: {self.tasa}.")


@dataclass(frozen=True)
class EscalaProgresiva:
    """Escala de tramos marginales, como las tablas de regalía e IEM del libro.

    Reproduce la mecánica de la hoja: cada tramo aporta su tasa aplicada a la
    porción del margen que cae dentro de él, y la suma de aportes se divide
    entre el margen para obtener la tasa efectiva.
    """

    tramos: tuple[Tramo, ...]

    def __post_init__(self) -> None:
        if not self.tramos:
            raise ErrorTributos("La escala no tiene tramos.")
        for anterior, siguiente in pairwise(self.tramos):
            if abs(anterior.limite_superior - siguiente.limite_inferior) > TOLERANCIA_CONSISTENCIA:
                raise ErrorTributos(
                    f"La escala tiene un hueco entre {anterior.limite_superior} y "
                    f"{siguiente.limite_inferior}."
                )

    @property
    def cortes(self) -> tuple[float, ...]:
        """Márgenes donde la escala cambia de pendiente."""
        return (self.tramos[0].limite_inferior, *(t.limite_superior for t in self.tramos))

    def coeficientes(self, margen: float) -> tuple[float, float]:
        """Constante y pendiente de la suma de tramos en el punto dado.

        Devuelve `(constante, pendiente)` tales que, mientras el margen no
        cambie de tramo, `suma_de_tramos(m) = constante + pendiente * m`.
        """
        constante = 0.0
        for tramo in self.tramos:
            if margen >= tramo.limite_superior:
                # Tramo completo: aporta su ancho por su tasa, y no depende del margen.
                constante += (tramo.limite_superior - tramo.limite_inferior) * tramo.tasa
            elif margen > tramo.limite_inferior:
                # Tramo donde cae el margen: aqui esta toda la pendiente.
                return constante - tramo.limite_inferior * tramo.tasa, tramo.tasa
            else:
                break
        return constante, 0.0

    def suma_de_tramos(self, margen: float) -> float:
        constante, pendiente = self.coeficientes(margen)
        return constante + pendiente * margen


@dataclass(frozen=True)
class EntradasTributarias:
    """Todo lo que un año necesita para resolver sus tributos.

    Las bases llegan ya calculadas por los bloques anteriores del motor. La
    utilidad operativa no está entre ellas: es la incógnita del sistema.
    """

    ventas_totales: float
    """Ventas del bloque de regalías, denominador del margen operativo."""

    base_operativa: float
    """Utilidad operativa antes de descontar el fondo de jubilación minera."""

    base_imponible: float
    """Utilidad del bloque de renta antes de regalía, IEM y deducciones."""

    saldo_perdidas: float
    """Pérdidas tributarias acumuladas de ejercicios anteriores."""

    escala_regalia: EscalaProgresiva
    escala_iem: EscalaProgresiva
    tasa_regalia_ventas: float
    tasa_fondo_jubilacion: float
    tasa_participacion: float
    tasa_impuesto_renta: float


@dataclass(frozen=True)
class ResultadoTributario:
    """Solución del año, con las líneas que el contraste N1 verifica una a una."""

    utilidad_operativa: float
    margen_operativo: float
    regalia: float
    impuesto_especial_mineria: float
    utilidad_imponible: float
    deduccion_perdidas: float
    fondo_jubilacion_minera: float
    participacion_trabajadores: float
    impuesto_renta: float


def resolver(entradas: EntradasTributarias) -> ResultadoTributario:
    """Resuelve el sistema tributario de un año sin iterar.

    Recorre los tramos en que la ecuación es afín, resuelve el sistema lineal
    de cada uno y devuelve la única solución consistente. Si ninguna lo es, o
    si hay más de una, falla: un resultado aproximado sería peor que un error.
    """
    if entradas.ventas_totales <= 0.0:
        # Sin ventas no hay margen que calcular ni regalia que aplicar. El
        # libro protege esta division con IFERROR y devuelve cero (regla 008).
        return _sin_actividad(entradas)

    candidatas = [
        solucion
        for margen in _margenes_de_prueba(entradas)
        for solucion in _resolver_en_el_tramo(entradas, margen)
        if _es_consistente(entradas, solucion)
    ]
    unicas = _descartar_repetidas(candidatas)

    if not unicas:
        raise ErrorTributos(
            "El sistema tributario no tiene solucion consistente. Revisa las escalas y las "
            "bases del ano: una escala con huecos o una base incoherente lo produce."
        )
    if len(unicas) > 1:
        raise ErrorTributos(
            f"El sistema tributario admite {len(unicas)} soluciones consistentes. "
            "El motor no elige entre ellas."
        )
    return unicas[0]


def _margenes_de_prueba(entradas: EntradasTributarias) -> list[float]:
    """Un punto interior por cada tramo en que la ecuación puede ser afín.

    Las dos escalas parten el eje del margen en intervalos; dentro de cada uno
    los coeficientes son constantes. Se prueba el punto medio de cada intervalo
    y también los cortes, porque la solución puede caer justo en uno.
    """
    cortes = sorted({*entradas.escala_regalia.cortes, *entradas.escala_iem.cortes})
    puntos: list[float] = [cortes[0] - 1.0, cortes[-1] + 1.0]
    puntos.extend(cortes)
    puntos.extend((a + b) / 2.0 for a, b in pairwise(cortes))
    return puntos


def _resolver_en_el_tramo(
    entradas: EntradasTributarias, margen_de_prueba: float
) -> list[ResultadoTributario]:
    """Resuelve la ecuación afín del tramo, para cada rama de los máximos.

    La ecuación es `U = base_operativa - fondo(U)`, donde el fondo depende de
    `U` a través de la regalía, el IEM y la deducción por pérdidas. Cada rama
    de un `MAX` o de un `IF` da un sistema lineal distinto.
    """
    ventas = entradas.ventas_totales
    c_reg, t_reg = entradas.escala_regalia.coeficientes(margen_de_prueba)
    c_iem, t_iem = entradas.escala_iem.coeficientes(margen_de_prueba)

    # regalia_por_margen(U) = ventas * c_reg + t_reg * U
    # iem(U)                = ventas * c_iem + t_iem * U
    ramas_regalia = (
        (ventas * c_reg, t_reg),
        (entradas.tasa_regalia_ventas * ventas, 0.0),
    )

    soluciones: list[ResultadoTributario] = []
    for reg_const, reg_pend in ramas_regalia:
        # utilidad imponible antes de deduccion: afin en U
        ui_const = entradas.base_imponible - reg_const - ventas * c_iem
        ui_pend = -reg_pend - t_iem
        for neta_const, neta_pend in _ramas_de_deduccion(entradas, ui_const, ui_pend):
            for fondo_const, fondo_pend in (
                (
                    entradas.tasa_fondo_jubilacion * neta_const,
                    entradas.tasa_fondo_jubilacion * neta_pend,
                ),
                (0.0, 0.0),
            ):
                # U = base_operativa - (fondo_const + fondo_pend * U)
                denominador = 1.0 + fondo_pend
                if abs(denominador) < TOLERANCIA_CONSISTENCIA:
                    continue
                utilidad = (entradas.base_operativa - fondo_const) / denominador
                soluciones.append(_armar(entradas, utilidad))
    return soluciones


def _ramas_de_deduccion(
    entradas: EntradasTributarias, ui_const: float, ui_pend: float
) -> tuple[tuple[float, float], ...]:
    """Utilidad neta de deducción, en cada rama de la fórmula del libro.

    `IF(AND(UI>0, UI*50% <= saldo), -UI*50%, IF(AND(UI>0, UI*50% > saldo), -saldo, 0))`.
    El límite del 50 % sobre la utilidad imponible es la regla que la hoja
    oculta `Inputs` menciona y que el estándar corporativo no documenta.

    Devuelve los coeficientes de la utilidad **neta**, no del descuento: la
    rama del 50 % escala la utilidad imponible entera, y tratarla como una
    constante aditiva deja el sistema sin solución consistente.
    """
    return (
        (0.5 * ui_const, 0.5 * ui_pend),
        (ui_const - entradas.saldo_perdidas, ui_pend),
        (ui_const, ui_pend),
    )


def _armar(entradas: EntradasTributarias, utilidad_operativa: float) -> ResultadoTributario:
    """Evalúa la cadena completa hacia adelante, sin suposiciones de rama."""
    ventas = entradas.ventas_totales
    margen = utilidad_operativa / ventas if ventas else 0.0

    regalia_por_margen = entradas.escala_regalia.suma_de_tramos(margen) * ventas
    regalia_por_ventas = entradas.tasa_regalia_ventas * ventas
    regalia = max(regalia_por_margen, regalia_por_ventas)
    iem = entradas.escala_iem.suma_de_tramos(margen) * ventas

    imponible = entradas.base_imponible - regalia - iem
    if imponible > 0.0:
        deduccion = -min(imponible * 0.5, entradas.saldo_perdidas)
    else:
        deduccion = 0.0
    neta = imponible + deduccion

    fondo = max(neta * entradas.tasa_fondo_jubilacion, 0.0)
    participacion = max(neta * entradas.tasa_participacion, 0.0)
    renta = max((neta - fondo - participacion) * entradas.tasa_impuesto_renta, 0.0)

    return ResultadoTributario(
        utilidad_operativa=utilidad_operativa,
        margen_operativo=margen,
        regalia=regalia,
        impuesto_especial_mineria=iem,
        utilidad_imponible=imponible,
        deduccion_perdidas=deduccion,
        fondo_jubilacion_minera=fondo,
        participacion_trabajadores=participacion,
        impuesto_renta=renta,
    )


def _es_consistente(entradas: EntradasTributarias, solucion: ResultadoTributario) -> bool:
    """Comprueba que la solución cierra la ecuación que la generó."""
    esperada = entradas.base_operativa - solucion.fondo_jubilacion_minera
    escala = max(1.0, abs(esperada))
    return abs(solucion.utilidad_operativa - esperada) <= TOLERANCIA_CONSISTENCIA * escala


def _descartar_repetidas(soluciones: Sequence[ResultadoTributario]) -> list[ResultadoTributario]:
    unicas: list[ResultadoTributario] = []
    for solucion in soluciones:
        escala = max(1.0, abs(solucion.utilidad_operativa))
        if not any(
            abs(u.utilidad_operativa - solucion.utilidad_operativa)
            <= TOLERANCIA_CONSISTENCIA * escala
            for u in unicas
        ):
            unicas.append(solucion)
    return unicas


def _sin_actividad(entradas: EntradasTributarias) -> ResultadoTributario:
    neta = entradas.base_imponible
    fondo = max(neta * entradas.tasa_fondo_jubilacion, 0.0)
    participacion = max(neta * entradas.tasa_participacion, 0.0)
    return ResultadoTributario(
        utilidad_operativa=entradas.base_operativa - fondo,
        margen_operativo=0.0,
        regalia=0.0,
        impuesto_especial_mineria=0.0,
        utilidad_imponible=neta,
        deduccion_perdidas=0.0,
        fondo_jubilacion_minera=fondo,
        participacion_trabajadores=participacion,
        impuesto_renta=max((neta - fondo - participacion) * entradas.tasa_impuesto_renta, 0.0),
    )


def resolver_por_punto_fijo(
    entradas: EntradasTributarias, *, iteraciones: int = 200
) -> ResultadoTributario:
    """Resolución aproximada, **solo para verificar** la solución cerrada.

    No participa del cálculo de una corrida. Existe porque el ADR 0009 exige
    que la solución exacta se contraste contra una aproximación independiente:
    si ambas difieren más allá de la precisión de coma flotante, la derivación
    está mal y la prueba lo detecta.
    """
    utilidad = entradas.base_operativa
    for _ in range(iteraciones):
        siguiente = _armar(entradas, utilidad)
        candidata = entradas.base_operativa - siguiente.fondo_jubilacion_minera
        if abs(candidata - utilidad) <= TOLERANCIA_CONSISTENCIA * max(1.0, abs(candidata)):
            return _armar(entradas, candidata)
        utilidad = candidata
    raise ErrorTributos("El punto fijo de verificacion no convergio.")
