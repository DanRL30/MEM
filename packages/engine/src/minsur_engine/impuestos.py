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

from minsur_engine.horizonte import Horizonte, Serie

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

    def aportes(self, margen: float) -> tuple[float, ...]:
        """El aporte de cada tramo, que es lo que la hoja escribe fila a fila.

        Reproduce la fórmula de las tablas `Impuestos!72:87` y `!92:108`: un
        tramo por debajo del margen aporta su ancho entero por su tasa, el que
        contiene al margen aporta la porción que le corresponde, y el que queda
        por encima no aporta nada.

        Es la misma cantidad que `coeficientes()` evalúa en forma afín, y las
        dos conviven a propósito: esta sirve para informar la tabla del libro,
        aquella para resolver el sistema sin iterar.
        """
        aportes: list[float] = []
        for tramo in self.tramos:
            if margen > tramo.limite_superior:
                aportes.append((tramo.limite_superior - tramo.limite_inferior) * tramo.tasa)
            elif margen < tramo.limite_inferior:
                aportes.append(0.0)
            else:
                aportes.append((margen - tramo.limite_inferior) * tramo.tasa)
        return tuple(aportes)

    def tasa_efectiva(self, margen: float) -> float:
        """La TEA de las filas 22 y 26: la suma de aportes entre el margen.

        El libro la protege con `IFERROR` porque un margen nulo la indetermina,
        y cero es el resultado esperado (regla `008`).
        """
        if margen == 0.0:
            return 0.0
        return sum(self.aportes(margen)) / margen

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
    limite_arrastre_de_perdidas: float = 0.5
    """Fraccion de la utilidad imponible que el arrastre puede absorber."""


@dataclass(frozen=True)
class ResultadoTributario:
    """Solución del año, con las líneas que el contraste N1 verifica una a una.

    Cada campo es una fila de la hoja `Impuestos`, y el número entre paréntesis
    de su comentario es esa fila. Nada aquí es un intermedio inventado: si un
    valor no está en la hoja, no está en este resultado.
    """

    utilidad_operativa: float
    """`20`, y la incógnita del sistema."""

    margen_operativo: float
    """`21`."""

    tasa_efectiva_regalia: float
    """`22`, la TEA que el libro obtiene sumando la tabla de tramos."""

    regalia_sobre_margen: float
    """`23`."""

    regalia_sobre_ventas: float
    """`24`."""

    regalia: float
    """`25`, la mayor de las dos anteriores."""

    tasa_efectiva_iem: float
    """`26`."""

    impuesto_especial_mineria: float
    """`27`."""

    utilidad_imponible: float
    """`47`."""

    deduccion_perdidas: float
    """`48`, negativa, y también la fila `66` con el signo del libro."""

    utilidad_luego_de_deduccion: float
    """`49`, y la fila `56`, que es la misma celda."""

    fondo_jubilacion_minera: float
    """`51`. Es lo único que realimenta: la fila `19` lo descuenta."""

    participacion_trabajadores: float
    """`53`."""

    utilidad_luego_de_participaciones: float
    """`59`."""

    impuesto_renta: float
    """`61`."""

    aportes_de_regalia: tuple[float, ...]
    """Las 16 filas `72:87`, una por tramo de la escala."""

    aportes_de_iem: tuple[float, ...]
    """Las 17 filas `92:108`."""


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
    limite = entradas.limite_arrastre_de_perdidas
    return (
        ((1.0 - limite) * ui_const, (1.0 - limite) * ui_pend),
        (ui_const - entradas.saldo_perdidas, ui_pend),
        (ui_const, ui_pend),
    )


def _armar(entradas: EntradasTributarias, utilidad_operativa: float) -> ResultadoTributario:
    """Evalúa la cadena completa hacia adelante, sin suposiciones de rama."""
    ventas = entradas.ventas_totales
    margen = utilidad_operativa / ventas if ventas else 0.0

    # El libro escribe la regalia como TEA por utilidad operativa, y el motor
    # como suma de tramos por ventas. Son la misma cantidad -el margen se
    # cancela contra si mismo, ver el encabezado- y aqui se conserva la segunda,
    # que es la forma con que se derivo la solucion cerrada. La TEA se informa
    # como la escribe la hoja, y `test_la_tea_reconstruye_la_regalia` ata las dos.
    regalia_por_margen = entradas.escala_regalia.suma_de_tramos(margen) * ventas
    regalia_por_ventas = entradas.tasa_regalia_ventas * ventas
    regalia = max(regalia_por_margen, regalia_por_ventas)
    iem = entradas.escala_iem.suma_de_tramos(margen) * ventas

    imponible = entradas.base_imponible - regalia - iem
    if imponible > 0.0:
        deduccion = -min(imponible * entradas.limite_arrastre_de_perdidas, entradas.saldo_perdidas)
    else:
        deduccion = 0.0
    neta = imponible + deduccion

    fondo = max(neta * entradas.tasa_fondo_jubilacion, 0.0)
    participacion = max(neta * entradas.tasa_participacion, 0.0)
    renta = max((neta - fondo - participacion) * entradas.tasa_impuesto_renta, 0.0)

    return ResultadoTributario(
        utilidad_operativa=utilidad_operativa,
        margen_operativo=margen,
        tasa_efectiva_regalia=entradas.escala_regalia.tasa_efectiva(margen),
        regalia_sobre_margen=regalia_por_margen,
        regalia_sobre_ventas=regalia_por_ventas,
        regalia=regalia,
        tasa_efectiva_iem=entradas.escala_iem.tasa_efectiva(margen),
        impuesto_especial_mineria=iem,
        utilidad_imponible=imponible,
        deduccion_perdidas=deduccion,
        utilidad_luego_de_deduccion=neta,
        fondo_jubilacion_minera=fondo,
        participacion_trabajadores=participacion,
        utilidad_luego_de_participaciones=neta - fondo - participacion,
        impuesto_renta=renta,
        aportes_de_regalia=entradas.escala_regalia.aportes(margen),
        aportes_de_iem=entradas.escala_iem.aportes(margen),
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
        tasa_efectiva_regalia=0.0,
        regalia_sobre_margen=0.0,
        regalia_sobre_ventas=0.0,
        regalia=0.0,
        tasa_efectiva_iem=0.0,
        impuesto_especial_mineria=0.0,
        utilidad_imponible=neta,
        deduccion_perdidas=0.0,
        utilidad_luego_de_deduccion=neta,
        fondo_jubilacion_minera=fondo,
        participacion_trabajadores=participacion,
        utilidad_luego_de_participaciones=neta - fondo - participacion,
        impuesto_renta=max((neta - fondo - participacion) * entradas.tasa_impuesto_renta, 0.0),
        aportes_de_regalia=tuple(0.0 for _ in entradas.escala_regalia.tramos),
        aportes_de_iem=tuple(0.0 for _ in entradas.escala_iem.tramos),
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


# ---------------------------------------------------------------------------
# La hoja entera
# ---------------------------------------------------------------------------
#
# Lo de arriba resuelve un ano. Lo que sigue arma la hoja `Impuestos` completa
# a partir de los bloques anteriores del motor, con una serie por fila y con el
# signo del libro: las ventas positivas y los gastos negativos, de modo que la
# utilidad operativa es literalmente la suma de las filas que tiene encima.
#
# La auditoria fila a fila esta en
# `docs/modelo-economico/brechas-hoja-impuestos.md`.


@dataclass(frozen=True)
class AporteDeTramo:
    """Una fila de las tablas `Impuestos!72:87` y `!92:108`."""

    limite_inferior: float
    limite_superior: float
    tasa: float
    aporte: Serie


@dataclass(frozen=True)
class BloqueDeRegalias:
    """`Impuestos!8:27`, la base sobre la que se calculan regalia e IEM."""

    ventas_totales: Serie
    costo_de_produccion: Serie
    fletes: Serie
    gastos_de_ventas: Serie
    gastos_administrativos: Serie
    gasto_estudios: Serie
    depreciacion_financiera: Serie
    gestion_social_deducible: Serie
    otros_gastos: Serie
    osinergmin: Serie
    oefa: Serie
    fondo_de_jubilacion: Serie
    """`19`, que es la fila `57` y cierra el unico lazo de la hoja."""

    utilidad_operativa: Serie
    margen_operativo: Serie
    tasa_efectiva_regalia: Serie
    regalia_sobre_margen: Serie
    regalia_sobre_ventas: Serie
    regalia_mayor: Serie
    tasa_efectiva_iem: Serie
    impuesto_especial: Serie

    @property
    def conceptos(self) -> tuple[Serie, ...]:
        """Las doce filas `8:19` que la `20` suma, en el orden del libro."""
        return (
            self.ventas_totales,
            self.costo_de_produccion,
            self.fletes,
            self.gastos_de_ventas,
            self.gastos_administrativos,
            self.gasto_estudios,
            self.depreciacion_financiera,
            self.gestion_social_deducible,
            self.otros_gastos,
            self.osinergmin,
            self.oefa,
            self.fondo_de_jubilacion,
        )


@dataclass(frozen=True)
class BloqueDeRenta:
    """`Impuestos!30:53`, la base imponible y lo que cuelga de ella.

    Se parece al bloque de regalias y no es el mismo: cambia la via de la
    depreciacion, no descuenta el fondo de jubilacion, y suma tres conceptos
    que aquel no tiene -la regalia, la exploracion y el IEM-.
    """

    ventas_netas: Serie
    """`30`. Es la misma celda que la `8` pese a la etiqueta: regla `057`."""

    costo_de_produccion: Serie
    fletes: Serie
    gastos_de_ventas: Serie
    gastos_administrativos: Serie
    gasto_estudios: Serie
    depreciacion_tributaria: Serie
    gestion_social_deducible: Serie
    otros_gastos: Serie
    osinergmin: Serie
    oefa: Serie
    utilidad_operativa: Serie
    regalias_mineras: Serie
    gastos_de_exploracion: Serie
    ingresos_financieros: Serie
    """`44`, vacia en el libro. Se declara y vale cero: ver la nota 2 de `mapa-n1.md`."""

    gastos_financieros: Serie
    """`45`, vacia por el mismo motivo."""

    impuesto_especial: Serie
    utilidad_imponible: Serie
    deduccion_por_perdidas: Serie
    utilidad_luego_de_deduccion: Serie
    tasa_fondo_de_jubilacion: Serie
    fondo_de_jubilacion: Serie
    tasa_participacion: Serie
    participacion_trabajadores: Serie

    @property
    def conceptos(self) -> tuple[Serie, ...]:
        """Las once filas `30:40` que la `41` suma."""
        return (
            self.ventas_netas,
            self.costo_de_produccion,
            self.fletes,
            self.gastos_de_ventas,
            self.gastos_administrativos,
            self.gasto_estudios,
            self.depreciacion_tributaria,
            self.gestion_social_deducible,
            self.otros_gastos,
            self.osinergmin,
            self.oefa,
        )

    @property
    def sumandos_de_la_imponible(self) -> tuple[Serie, ...]:
        """Las seis filas `41:46` que la `47` suma."""
        return (
            self.utilidad_operativa,
            self.regalias_mineras,
            self.gastos_de_exploracion,
            self.ingresos_financieros,
            self.gastos_financieros,
            self.impuesto_especial,
        )


@dataclass(frozen=True)
class BloqueDeImpuestoALaRenta:
    """`Impuestos!56:61`."""

    utilidad_imponible: Serie
    fondo_de_jubilacion: Serie
    participacion_trabajadores: Serie
    utilidad_luego_de_participaciones: Serie
    tasa_impuesto_renta: Serie
    impuesto_a_la_renta: Serie

    @property
    def sumandos(self) -> tuple[Serie, ...]:
        """Las tres filas `56:58` que la `59` suma."""
        return (
            self.utilidad_imponible,
            self.fondo_de_jubilacion,
            self.participacion_trabajadores,
        )


@dataclass(frozen=True)
class BloqueDePerdidaTributaria:
    """`Impuestos!64:67`, el arrastre de las perdidas de ejercicios anteriores."""

    saldo_inicial: Serie
    perdida_de_ejercicio: Serie
    """`65`, medida sobre la fila `56` y no sobre la `47`. Coinciden siempre,
    porque la deduccion vale cero cuando el ejercicio es perdida."""

    perdida_a_amortizar: Serie
    """`66`. Es la fila `48` escrita al reves, y da el mismo numero."""

    saldo_final: Serie


@dataclass(frozen=True)
class BloqueDeImpuestos:
    """La hoja `Impuestos` entera, bloque a bloque."""

    regalias: BloqueDeRegalias
    renta: BloqueDeRenta
    impuesto_a_la_renta: BloqueDeImpuestoALaRenta
    perdida_tributaria: BloqueDePerdidaTributaria
    tramos_de_regalia: tuple[AporteDeTramo, ...]
    tramos_de_iem: tuple[AporteDeTramo, ...]
    por_ano: tuple[ResultadoTributario, ...]
    """La solucion de cada ejercicio, para quien necesite el ano y no la fila."""


def calcular(
    horizonte: Horizonte,
    *,
    ventas: Serie,
    cash_cost: Serie,
    fletes: Serie,
    gasto_de_ventas: Serie,
    administrativos: Serie,
    estudios_deducibles: Serie,
    gestion_social_deducible: Serie,
    otros_gastos: Serie,
    tasa_osinergmin: Serie,
    tasa_oefa: Serie,
    depreciacion_financiera: Serie,
    depreciacion_tributaria: Serie,
    exploraciones: Serie,
    escala_regalia: EscalaProgresiva,
    escala_iem: EscalaProgresiva,
    tasa_regalia_ventas: float,
    tasa_fondo_jubilacion: float,
    tasa_participacion: float,
    tasa_impuesto_renta: float,
    limite_arrastre_de_perdidas: float,
    saldo_inicial_de_perdidas: float,
) -> BloqueDeImpuestos:
    """Reproduce la hoja `Impuestos` desde los bloques anteriores del motor.

    Recibe los gastos en positivo, que es como los lleva el resto del motor, y
    los escribe con el signo del libro. Las dos bases no se arman sumando
    conceptos en un escalar: se construyen las filas, y **la utilidad operativa
    es la suma de sus filas**, que es lo que hace contrastable el bloque en N1.

    Los gastos entran por su parte deducible, no por su importe. La gestion
    social y los estudios salen enteros del flujo y solo en parte de la base: la
    fraccion deducible de la primera la declara cada unidad, y de los segundos
    solo deduce el que es gasto, porque el capitalizable se deprecia.

    Las dos bases difieren en tres cosas, no en una: la via de la depreciacion,
    el fondo de jubilacion -que solo descuenta la de regalias- y los tres
    conceptos que solo tiene la de renta. Confundirlas desplaza los tributos sin
    que el flujo economico lo delate.
    """
    costo_de_produccion = _negada(cash_cost)
    fletes_negados = _negada(fletes)
    gastos_de_ventas = _negada(gasto_de_ventas)
    gastos_administrativos = _negada(administrativos)
    gasto_estudios = _negada(estudios_deducibles)
    gestion_social = _negada(gestion_social_deducible)
    otros = _negada(otros_gastos)
    osinergmin = tuple(-ventas[i] * tasa_osinergmin[i] for i in range(horizonte.anos))
    oefa = tuple(-ventas[i] * tasa_oefa[i] for i in range(horizonte.anos))
    depreciacion_financiera_negada = _negada(depreciacion_financiera)
    depreciacion_tributaria_negada = _negada(depreciacion_tributaria)
    exploracion_negada = _negada(exploraciones)
    ceros = horizonte.ceros()

    # Los nueve conceptos que las dos bases comparten. Es la unica suma que se
    # hace fuera de las filas, y existe porque las dos bases la repiten igual.
    comunes = tuple(
        ventas[i]
        + costo_de_produccion[i]
        + fletes_negados[i]
        + gastos_de_ventas[i]
        + gastos_administrativos[i]
        + gasto_estudios[i]
        + gestion_social[i]
        + otros[i]
        + osinergmin[i]
        + oefa[i]
        for i in range(horizonte.anos)
    )

    resultados: list[ResultadoTributario] = []
    saldos_iniciales: list[float] = []
    saldo = saldo_inicial_de_perdidas

    for i in range(horizonte.anos):
        entradas = EntradasTributarias(
            ventas_totales=ventas[i],
            # La fila `20` sin la `19`, que es la incognita del sistema.
            base_operativa=comunes[i] + depreciacion_financiera_negada[i],
            # La fila `41` mas la `43`; la regalia y el IEM los descuenta el
            # solucionador, porque dependen de la incognita.
            base_imponible=(comunes[i] + depreciacion_tributaria_negada[i] + exploracion_negada[i]),
            saldo_perdidas=saldo,
            escala_regalia=escala_regalia,
            escala_iem=escala_iem,
            tasa_regalia_ventas=tasa_regalia_ventas,
            tasa_fondo_jubilacion=tasa_fondo_jubilacion,
            tasa_participacion=tasa_participacion,
            tasa_impuesto_renta=tasa_impuesto_renta,
            limite_arrastre_de_perdidas=limite_arrastre_de_perdidas,
        )
        resultado = resolver(entradas)
        resultados.append(resultado)
        saldos_iniciales.append(saldo)

        # La fila `65` mide sobre la `56` y la `66` es la `48` con su signo.
        saldo = (
            saldo + max(-resultado.utilidad_luego_de_deduccion, 0.0) + resultado.deduccion_perdidas
        )

    def linea(campo: str) -> Serie:
        return tuple(getattr(r, campo) for r in resultados)

    perdidas_del_ejercicio = tuple(max(-r.utilidad_luego_de_deduccion, 0.0) for r in resultados)
    return BloqueDeImpuestos(
        regalias=BloqueDeRegalias(
            ventas_totales=ventas,
            costo_de_produccion=costo_de_produccion,
            fletes=fletes_negados,
            gastos_de_ventas=gastos_de_ventas,
            gastos_administrativos=gastos_administrativos,
            gasto_estudios=gasto_estudios,
            depreciacion_financiera=depreciacion_financiera_negada,
            gestion_social_deducible=gestion_social,
            otros_gastos=otros,
            osinergmin=osinergmin,
            oefa=oefa,
            fondo_de_jubilacion=_negada(linea("fondo_jubilacion_minera")),
            utilidad_operativa=linea("utilidad_operativa"),
            margen_operativo=linea("margen_operativo"),
            tasa_efectiva_regalia=linea("tasa_efectiva_regalia"),
            regalia_sobre_margen=linea("regalia_sobre_margen"),
            regalia_sobre_ventas=linea("regalia_sobre_ventas"),
            regalia_mayor=linea("regalia"),
            tasa_efectiva_iem=linea("tasa_efectiva_iem"),
            impuesto_especial=linea("impuesto_especial_mineria"),
        ),
        renta=BloqueDeRenta(
            ventas_netas=ventas,
            costo_de_produccion=costo_de_produccion,
            fletes=fletes_negados,
            gastos_de_ventas=gastos_de_ventas,
            gastos_administrativos=gastos_administrativos,
            gasto_estudios=gasto_estudios,
            depreciacion_tributaria=depreciacion_tributaria_negada,
            gestion_social_deducible=gestion_social,
            otros_gastos=otros,
            osinergmin=osinergmin,
            oefa=oefa,
            utilidad_operativa=tuple(
                comunes[i] + depreciacion_tributaria_negada[i] for i in range(horizonte.anos)
            ),
            regalias_mineras=_negada(linea("regalia")),
            gastos_de_exploracion=exploracion_negada,
            ingresos_financieros=ceros,
            gastos_financieros=ceros,
            impuesto_especial=_negada(linea("impuesto_especial_mineria")),
            utilidad_imponible=linea("utilidad_imponible"),
            deduccion_por_perdidas=linea("deduccion_perdidas"),
            utilidad_luego_de_deduccion=linea("utilidad_luego_de_deduccion"),
            tasa_fondo_de_jubilacion=_constante(tasa_fondo_jubilacion, horizonte),
            fondo_de_jubilacion=linea("fondo_jubilacion_minera"),
            tasa_participacion=_constante(tasa_participacion, horizonte),
            participacion_trabajadores=linea("participacion_trabajadores"),
        ),
        impuesto_a_la_renta=BloqueDeImpuestoALaRenta(
            utilidad_imponible=linea("utilidad_luego_de_deduccion"),
            fondo_de_jubilacion=_negada(linea("fondo_jubilacion_minera")),
            participacion_trabajadores=_negada(linea("participacion_trabajadores")),
            utilidad_luego_de_participaciones=linea("utilidad_luego_de_participaciones"),
            tasa_impuesto_renta=_constante(tasa_impuesto_renta, horizonte),
            impuesto_a_la_renta=linea("impuesto_renta"),
        ),
        perdida_tributaria=BloqueDePerdidaTributaria(
            saldo_inicial=tuple(saldos_iniciales),
            perdida_de_ejercicio=perdidas_del_ejercicio,
            perdida_a_amortizar=linea("deduccion_perdidas"),
            saldo_final=tuple(
                saldos_iniciales[i] + perdidas_del_ejercicio[i] + resultados[i].deduccion_perdidas
                for i in range(horizonte.anos)
            ),
        ),
        tramos_de_regalia=_tabla(escala_regalia, resultados, "aportes_de_regalia"),
        tramos_de_iem=_tabla(escala_iem, resultados, "aportes_de_iem"),
        por_ano=tuple(resultados),
    )


def _negada(serie: Serie) -> Serie:
    """El resto del motor lleva los gastos en positivo; la hoja, en negativo."""
    return tuple(-valor for valor in serie)


def _constante(valor: float, horizonte: Horizonte) -> Serie:
    """Una tasa que el libro repite en las 36 columnas."""
    return tuple(valor for _ in range(horizonte.anos))


def _tabla(
    escala: EscalaProgresiva, resultados: Sequence[ResultadoTributario], campo: str
) -> tuple[AporteDeTramo, ...]:
    """Una fila por tramo de la escala, con su aporte ano a ano."""
    aportes: tuple[tuple[float, ...], ...] = tuple(getattr(r, campo) for r in resultados)
    return tuple(
        AporteDeTramo(
            limite_inferior=tramo.limite_inferior,
            limite_superior=tramo.limite_superior,
            tasa=tramo.tasa,
            aporte=tuple(fila[posicion] for fila in aportes),
        )
        for posicion, tramo in enumerate(escala.tramos)
    )
