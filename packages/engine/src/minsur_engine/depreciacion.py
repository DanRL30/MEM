"""Depreciación tributaria y financiera, por mina y por componente.

Es el bloque más denso del libro: 58 767 fórmulas, y la desviación acordada
`D-04` obliga además a calcularlo **separado por mina** en todos los casos, no
solo en los que el libro lo hace.

## Dos vías, y dos métodos distintos

Hasta el 02/09/2026 este módulo asumía que las dos vías compartían el mecanismo
y solo cambiaban las tasas. La disección de la hoja mostró que no:

| Componente | Tributaria | Financiera |
|---|---|---|
| Maquinaria, equipos y vehículos | Lineal | Lineal |
| Equipos de cómputo | Lineal | **Agotamiento** |
| Instalaciones y equipos diversos | Lineal | **Agotamiento** |
| Edificaciones y construcciones | Lineal | **Agotamiento** |
| No depreciable | Su tasa | Su tasa |

**Agotamiento** es el método de unidades de producción: cada año se deprecia la
fracción del saldo que representa lo extraído sobre las reservas que quedaban.
Un activo así no se agota en un número fijo de ejercicios, sino al ritmo al que
se vacía el yacimiento, que es lo que la contabilidad financiera persigue.

Los equipos de cómputo caen del lado del agotamiento aunque su clasificación
contable sea la de la maquinaria, porque la fila que agota toma el capital de la
unidad menos la maquinaria y menos lo no depreciable, y ahí el libro resta solo
la fila de maquinaria. Se reproduce y está consultado: es la regla `036`.

## Cada componente se deprecia y se informa por separado

El libro consolida los equipos de cómputo con la maquinaria bajo un solo código.
La plataforma no lo hace: **un proyecto nuevo puede traer componentes que hoy no
existen**, y si la depreciación llega ya sumada, separarla después es imposible.
Por eso la salida es un mapa por componente y el total se obtiene sumándolo.

## La cuota lineal, tal como la escribe el libro

    IF(base - acumulado > base * tasa,  base * tasa,  base - acumulado)

Depreciación lineal sobre el valor original, con **la última cuota ajustada al
saldo**. Sin ese ajuste, el último ejercicio arrastra un residuo que el contraste
detecta como una diferencia pequeña y persistente.

## La depreciación no corre antes de producir

    IF(SUM(produccion hasta el ano) = 0, 0, ...)

Un activo construido antes del arranque no deprecia hasta que la unidad produce.
La condición se aplica **solo a las unidades que producen**: una refinería o un
depósito de relaves no lo hacen nunca por diseño, y aplicársela les anularía el
escudo fiscal entero en vez de retrasarlo.

## La proyección de SAP no es un componente del capital

Es la depreciación ya contabilizada de los activos que existen antes del primer
año del caso, y el libro la trae como supuesto por unidad y por vía. Viaja en el
mismo mapa que los componentes porque se suma con ellos, pero no sale de ninguna
inversión de este caso.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from minsur_engine.capex import NATURALEZAS, CapitalDeUnidad
from minsur_engine.horizonte import Horizonte, Serie

COMPONENTES_POR_AGOTAMIENTO = ("equipos_de_computo", "instalaciones", "edificaciones")
"""Lo que la vía financiera agota contra las reservas en vez de depreciar lineal.

Es la lectura literal del libro: la fila que agota toma el capital de la unidad
menos la maquinaria y menos lo no depreciable, y al restar solo la fila de
maquinaria deja dentro los equipos de cómputo, que comparten su clasificación.
"""

PROYECCION_SAP = "Proyeccion SAP"
"""Clave de la depreciación ya contabilizada, que no viene de este caso."""

ESTUDIOS = "Estudios capitalizables"
"""Clave del estudio de factibilidad, que se deprecia sin ser capital del bloque.

El libro lo lee de la hoja de opex y lo deprecia en las dos vías. Aquí llega por
el mismo camino: es un gasto capitalizable, no una fila de `InputsCapex`.
"""


class ErrorDepreciacion(ValueError):
    """Las tasas o las bases de depreciación no son consistentes."""


@dataclass(frozen=True)
class TasasDeDepreciacion:
    """Tasa anual por componente contable, en tanto por uno.

    **`no_depreciable` se deduce entero en su año**, con tasa uno. El nombre viene
    del libro y engaña: no es que no se deprecie, es que no se reparte. Es el
    escudo del capital de cierre, y la regla `034`.

    **Los equipos de cómputo no llevan tasa propia, y no es un pendiente.** Su
    clasificación contable es `MAQ`, la misma que la maquinaria, de modo que su
    tasa es la de su clase. Que el componente se informe por separado no lo saca
    de esa clase: separa el detalle, no la clasificación.

    `estudios` sí es opcional, y sin declarar usa la de edificaciones, que es la
    que el libro les aplica.
    """

    maquinaria: float
    instalaciones: float
    edificaciones: float
    estudios: float | None = None
    no_depreciable: float = 1.0

    def __post_init__(self) -> None:
        for nombre in (
            "maquinaria",
            "instalaciones",
            "edificaciones",
            "estudios",
            "no_depreciable",
        ):
            tasa = getattr(self, nombre)
            if tasa is None:
                continue
            if not 0.0 < tasa <= 1.0:
                raise ErrorDepreciacion(
                    f"La tasa de {nombre} vale {tasa} y se espera una fraccion mayor que 0 y "
                    "hasta 1. Una tasa del 10 % se escribe 0.10."
                )

    def de(self, componente: str) -> float:
        if componente not in NATURALEZAS:
            raise ErrorDepreciacion(f"Naturaleza {componente!r} desconocida.")
        if componente == "equipos_de_computo":
            # Su clasificacion contable es MAQ: la tasa es la de su clase.
            return self.maquinaria
        tasa: float = getattr(self, componente)
        return tasa

    @property
    def de_estudios(self) -> float:
        """Tasa del estudio capitalizable. Sin declarar, la de edificaciones."""
        return self.edificaciones if self.estudios is None else self.estudios


@dataclass(frozen=True)
class Agotamiento:
    """Lo que la vía financiera necesita para agotar el capital de una unidad.

    Las reservas son un **saldo de apertura**, no una serie: el libro las lee una
    vez y las rueda restando lo extraído y sumando lo convertido.
    """

    extraido: Serie
    reservas: float
    conversion_de_recursos: Serie = ()
    """Recursos que pasan a reserva, que es lo que permite el acuerdo 9."""


def cuota(base: float, tasa: float, acumulado: float) -> float:
    """Cuota de un ejercicio, con la última ajustada al saldo pendiente."""
    pendiente = base - acumulado
    if pendiente <= 0.0:
        return 0.0
    lineal = base * tasa
    return lineal if pendiente > lineal else pendiente


def cronograma_de_inversion(base: float, tasa: float, ejercicios: int) -> Serie:
    """Cuotas que genera una inversión desde el ejercicio en que se realiza."""
    if ejercicios < 0:
        raise ErrorDepreciacion(f"Numero de ejercicios negativo: {ejercicios}.")
    cuotas: list[float] = []
    acumulado = 0.0
    for _ in range(ejercicios):
        actual = cuota(base, tasa, acumulado)
        cuotas.append(actual)
        acumulado += actual
    return tuple(cuotas)


def depreciar(horizonte: Horizonte, inversiones: Serie, tasa: float) -> Serie:
    """Depreciación anual lineal de una serie de inversiones.

    Cada año de inversión abre su cronograma y los cronogramas se superponen,
    que es exactamente la forma triangular que tiene la hoja: una fila por año
    de inversión y una suma en diagonal.
    """
    if len(inversiones) != horizonte.anos:
        raise ErrorDepreciacion(
            f"La serie de inversiones trae {len(inversiones)} valores y el horizonte tiene "
            f"{horizonte.anos} anos."
        )
    total = [0.0] * horizonte.anos
    for ano, base in enumerate(inversiones):
        if base == 0.0:
            continue
        for desplazamiento, valor in enumerate(
            cronograma_de_inversion(base, tasa, horizonte.anos - ano)
        ):
            total[ano + desplazamiento] += valor
    return tuple(total)


def saldo_de_reservas(horizonte: Horizonte, agotamiento: Agotamiento) -> Serie:
    """Reservas que quedan al cierre de cada ejercicio.

    `reservas finales = reservas anteriores - extraido + conversion`, redondeado
    a tonelada entera. El redondeo es la regla `001`, y esta pendiente de
    reconfirmar con Finanzas.
    """
    saldo = agotamiento.reservas
    cierres: list[float] = []
    for i in range(horizonte.anos):
        saldo = round(
            saldo - _en(agotamiento.extraido, i) + _en(agotamiento.conversion_de_recursos, i)
        )
        cierres.append(saldo)
    return tuple(cierres)


def tasas_de_agotamiento(horizonte: Horizonte, agotamiento: Agotamiento) -> Serie:
    """Fracción del saldo que se agota cada año: lo extraído sobre las reservas.

    El primer ejercicio la mide contra las reservas de apertura y los siguientes
    contra el saldo de cierre del anterior.

    **El tope del 100 % se aplica siempre.** El libro lo omite en una de las
    seis unidades, y sin él una extracción mayor que el saldo depreciaría más
    capital del que queda. No se reproduce la omisión, y no solo porque el
    resultado sea imposible: la plataforma evalúa un proyecto que hoy no existe
    con los mismos conceptos y las mismas reglas que las unidades actuales, y
    una excepción que vive en la fórmula de una unidad concreta no tiene dónde
    alojarse ahí.
    """
    apertura = agotamiento.reservas
    cierres = saldo_de_reservas(horizonte, agotamiento)
    tasas: list[float] = []
    for i in range(horizonte.anos):
        disponible = apertura if i == 0 else cierres[i - 1]
        extraccion = _en(agotamiento.extraido, i)
        tasas.append(min(extraccion / disponible, 1.0) if disponible > 0.0 else 0.0)
    return tuple(tasas)


def agotar(horizonte: Horizonte, inversiones: Serie, tasas: Serie) -> Serie:
    """Deprecia un saldo de capital al ritmo al que se vacía el yacimiento.

    A diferencia de la lineal, no hay cronograma por año de inversión: hay **un
    solo saldo** que recibe las inversiones del ejercicio y se agota por la tasa
    del año. Es la forma que tiene la hoja, con su saldo inicial, su cuota y su
    saldo final encadenados.
    """
    saldo = 0.0
    cuotas: list[float] = []
    for i in range(horizonte.anos):
        saldo += _en(inversiones, i)
        del_ano = saldo * _en(tasas, i)
        cuotas.append(del_ano)
        saldo -= del_ano
    return tuple(cuotas)


def depreciacion_por_componente(
    horizonte: Horizonte,
    capital: CapitalDeUnidad | None,
    tasas: TasasDeDepreciacion,
    *,
    produccion: Serie | None = None,
    agotamiento: Agotamiento | None = None,
    proyeccion: Serie = (),
    estudios: Serie = (),
) -> dict[str, Serie]:
    """Depreciación de cada componente contable de una unidad.

    Sin `agotamiento` todos los componentes se deprecian lineal, que es la vía
    tributaria. Con él, los tres de `COMPONENTES_POR_AGOTAMIENTO` se agotan
    contra las reservas y la maquinaria sigue lineal, que es la financiera.

    Lo no depreciable se deduce entero en su año en las dos, y el estudio
    capitalizable se deprecia lineal en las dos: el libro no los distingue por
    vía.
    """
    ritmo = tasas_de_agotamiento(horizonte, agotamiento) if agotamiento is not None else ()
    detalle: dict[str, Serie] = {}
    if capital is not None:
        for componente in NATURALEZAS:
            inversiones = capital.naturaleza(componente, horizonte)
            if not any(inversiones):
                continue
            if agotamiento is not None and componente in COMPONENTES_POR_AGOTAMIENTO:
                detalle[componente] = agotar(horizonte, inversiones, ritmo)
                continue
            tasa = tasas.de(componente)
            if tasa == 0.0:
                continue
            detalle[componente] = depreciar(horizonte, inversiones, tasa)

    if any(estudios):
        detalle[ESTUDIOS] = depreciar(horizonte, _alineada(horizonte, estudios), tasas.de_estudios)

    if any(proyeccion):
        detalle[PROYECCION_SAP] = _alineada(horizonte, proyeccion)

    if produccion is None:
        return detalle
    return {
        componente: _sin_depreciar_antes_de_producir(horizonte, serie, produccion)
        for componente, serie in detalle.items()
    }


def depreciacion_de_unidad(
    horizonte: Horizonte,
    capital: CapitalDeUnidad | None,
    tasas: TasasDeDepreciacion,
    *,
    produccion: Serie | None = None,
    agotamiento: Agotamiento | None = None,
    proyeccion: Serie = (),
    estudios: Serie = (),
) -> Serie:
    """Depreciación de una unidad, sumando sus componentes."""
    detalle = depreciacion_por_componente(
        horizonte,
        capital,
        tasas,
        produccion=produccion,
        agotamiento=agotamiento,
        proyeccion=proyeccion,
        estudios=estudios,
    )
    return sumar(horizonte, detalle)


def depreciacion_por_mina(
    horizonte: Horizonte,
    capitales: Sequence[CapitalDeUnidad],
    tasas: TasasDeDepreciacion,
    *,
    produccion: Mapping[str, Serie] | None = None,
    agotamientos: Mapping[str, Agotamiento] | None = None,
    proyecciones: Mapping[str, Serie] | None = None,
    estudios: Mapping[str, Serie] | None = None,
) -> dict[str, dict[str, Serie]]:
    """Depreciación separada por unidad y por componente, que es lo que exige `D-04`.

    MINSUR pidió expresamente que el cálculo sea por mina en todos los casos,
    incluso donde el modelo de referencia consolida. Devolver el desglose y no el
    total es lo que hace esa desviación verificable: el agregado se obtiene
    sumando, pero el detalle no se puede recuperar de un agregado. Lo mismo vale
    un nivel más abajo, entre los componentes.
    """
    series = produccion or {}
    agota = agotamientos or {}
    proyectada = proyecciones or {}
    capitalizados = estudios or {}
    por_nombre = {capital.unidad: capital for capital in capitales}
    # Una unidad puede depreciar sin haber invertido: le basta con un estudio
    # capitalizable o con la proyeccion de lo ya contabilizado. Recorrer solo los
    # capitales dejaria esa depreciacion fuera sin que nada lo acusara.
    nombres = list(por_nombre) + [
        nombre
        for nombre in (*capitalizados, *proyectada)
        if nombre not in por_nombre
        and (any(capitalizados.get(nombre, ())) or any(proyectada.get(nombre, ())))
    ]
    return {
        nombre: depreciacion_por_componente(
            horizonte,
            por_nombre.get(nombre),
            tasas,
            produccion=series.get(nombre),
            agotamiento=agota.get(nombre),
            proyeccion=proyectada.get(nombre, ()),
            estudios=capitalizados.get(nombre, ()),
        )
        for nombre in dict.fromkeys(nombres)
    }


def sumar(horizonte: Horizonte, detalle: Mapping[str, Serie]) -> Serie:
    """Suma las series de un desglose, sea por componente o por unidad."""
    if not detalle:
        return horizonte.ceros()
    return tuple(sum(valores) for valores in zip(*detalle.values(), strict=True))


def por_unidad(
    horizonte: Horizonte, detalle: Mapping[str, Mapping[str, Serie]]
) -> dict[str, Serie]:
    """Colapsa el desglose por componente y deja el total de cada unidad."""
    return {unidad: sumar(horizonte, componentes) for unidad, componentes in detalle.items()}


def total_depreciado(horizonte: Horizonte, por_mina: Mapping[str, Serie]) -> Serie:
    """Suma del desglose por mina, para las líneas que consolidan."""
    return sumar(horizonte, por_mina)


def _alineada(horizonte: Horizonte, serie: Serie) -> Serie:
    return tuple(_en(serie, i) for i in range(horizonte.anos))


def _en(serie: Sequence[float], i: int) -> float:
    return serie[i] if i < len(serie) else 0.0


def _sin_depreciar_antes_de_producir(
    horizonte: Horizonte, depreciacion: Serie, produccion: Serie
) -> Serie:
    if len(produccion) != horizonte.anos:
        raise ErrorDepreciacion(
            f"La serie de produccion trae {len(produccion)} valores y el horizonte tiene "
            f"{horizonte.anos} anos."
        )
    acumulada = 0.0
    resultado: list[float] = []
    for i, valor in enumerate(depreciacion):
        acumulada += produccion[i]
        resultado.append(valor if acumulada != 0.0 else 0.0)
    return tuple(resultado)
