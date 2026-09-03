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
| Equipos de cómputo | Lineal | Lineal |
| Instalaciones y equipos diversos | Lineal | **Agotamiento** |
| Edificaciones y construcciones | Lineal | **Agotamiento** |
| No depreciable | Su tasa | Su tasa |

**Agotamiento** es el método de unidades de producción: cada año se deprecia la
fracción del saldo que representa lo extraído sobre las reservas que quedaban.
Un activo así no se agota en un número fijo de ejercicios, sino al ritmo al que
se vacía el yacimiento, que es lo que la contabilidad financiera persigue.

En el libro los equipos de cómputo caen del lado del agotamiento, porque la fila
que agota resta solo la fila de maquinaria y arrastra un componente de su misma
clase. **La plataforma no lo reproduce**: el cómputo es maquinaria y se deprecia
como ella en las dos vías. Es la regla `036`.

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

## Las dos vías miran la producción de forma distinta

La tributaria acumula:

    IF(SUM(produccion hasta el ano) = 0, 0, ...)

Un activo construido antes del arranque no deprecia hasta que la unidad produce,
y desde entonces deprecia siempre. Es la regla `013`.

La financiera no acumula: multiplica el total del año por una bandera de ese año,
`Ano con produccion`, que vale uno o cero según haya producción **en ese
ejercicio**. La diferencia aparece cuando una unidad para un año a mitad de vida
o termina de producir antes del horizonte: ahí la tributaria sigue depreciando y
la financiera no. Es la regla `041`.

Las dos se aplican **solo a las unidades que producen**: una refinería o un
depósito de relaves no lo hacen nunca por diseño, y aplicárselas les anularía el
escudo entero en vez de retrasarlo.

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

COMPONENTES_POR_AGOTAMIENTO = ("instalaciones", "edificaciones")
"""Lo que la vía financiera agota contra las reservas en vez de depreciar lineal.

**Los equipos de cómputo no están aquí, y el libro los deja dentro.** Su fila de
agotamiento toma el capital de la unidad menos la maquinaria y menos lo no
depreciable, y al restar solo la fila de maquinaria arrastra al cómputo, que
lleva su mismo código contable. MINSUR lo identificó como un arrastre de la
fórmula el 02/09/2026: el cómputo es maquinaria, y se deprecia como ella en las
dos vías. Es la regla `036`, y el segundo punto donde la plataforma no
reproduce el modelo.
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


def cronograma_por_cosecha(
    horizonte: Horizonte, inversiones: Serie, tasa: float
) -> dict[int, Serie]:
    """El triángulo del libro: una serie por año de inversión.

    La hoja abre cada componente en tantas filas como ejercicios tiene el
    horizonte —una por **cosecha**, el año en que se invierte— y cierra con la
    suma en diagonal. Cada cosecha empieza a depreciar en su propio año y no
    interactúa con las demás, que es lo que hace legible la hoja: una cuota fuera
    de sitio se atribuye al año que la generó.

    Solo se emiten las cosechas con inversión. Un año sin capital no abre fila en
    el libro tampoco, y treinta y seis filas en cero no dicen nada.
    """
    if len(inversiones) != horizonte.anos:
        raise ErrorDepreciacion(
            f"La serie de inversiones trae {len(inversiones)} valores y el horizonte tiene "
            f"{horizonte.anos} anos."
        )
    cosechas: dict[int, Serie] = {}
    for ano, base in enumerate(inversiones):
        if base == 0.0:
            continue
        fila = [0.0] * horizonte.anos
        for desplazamiento, valor in enumerate(
            cronograma_de_inversion(base, tasa, horizonte.anos - ano)
        ):
            fila[ano + desplazamiento] = valor
        cosechas[ano] = tuple(fila)
    return cosechas


def depreciar(horizonte: Horizonte, inversiones: Serie, tasa: float) -> Serie:
    """Depreciación anual lineal de una serie de inversiones.

    Es la suma en diagonal de `cronograma_por_cosecha`, que es la fila con que el
    libro cierra cada triángulo. Se deriva de él y no al revés, para que la
    cuota se calcule en un solo sitio.
    """
    cosechas = cronograma_por_cosecha(horizonte, inversiones, tasa)
    return tuple(sum(fila[i] for fila in cosechas.values()) for i in range(horizonte.anos))


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


def _rodar_saldo(
    horizonte: Horizonte, inversiones: Serie, tasas: Serie
) -> tuple[Serie, Serie, Serie]:
    """La recurrencia del agotamiento: saldo inicial, cuota y saldo final.

    Un solo sitio calcula el saldo, y de él salen tanto la cuota que consume el
    cálculo como la tabla que se muestra. Escrita dos veces, la tabla podría
    mostrar un saldo que no es el que dio la cuota.
    """
    saldo = 0.0
    iniciales: list[float] = []
    cuotas: list[float] = []
    finales: list[float] = []
    for i in range(horizonte.anos):
        saldo += _en(inversiones, i)
        iniciales.append(saldo)
        del_ano = saldo * _en(tasas, i)
        cuotas.append(del_ano)
        saldo -= del_ano
        finales.append(saldo)
    return tuple(iniciales), tuple(cuotas), tuple(finales)


def agotar(horizonte: Horizonte, inversiones: Serie, tasas: Serie) -> Serie:
    """Deprecia un saldo de capital al ritmo al que se vacía el yacimiento.

    A diferencia de la lineal, no hay cronograma por año de inversión: hay **un
    solo saldo** que recibe las inversiones del ejercicio y se agota por la tasa
    del año. Es la forma que tiene la hoja, con su saldo inicial, su cuota y su
    saldo final encadenados.
    """
    _, cuotas, _ = _rodar_saldo(horizonte, inversiones, tasas)
    return cuotas


@dataclass(frozen=True)
class TrazaDelAgotamiento:
    """La tabla con que el libro deriva la cuota financiera de una unidad.

    Son las once filas que la hoja escribe debajo de cada bloque financiero, y
    valen porque sin ellas la cuota es un número sin derivación: no se puede
    decir si una diferencia viene de las reservas, de lo extraído o del saldo.
    """

    reservas_iniciales: Serie
    """Saldo con el que abre cada ejercicio: el de cierre del anterior."""

    extraido: Serie
    conversion_de_recursos: Serie
    reservas_finales: Serie
    tasa: Serie
    """`MIN(extraído / reservas, 100 %)`. El tope se aplica siempre, regla `039`."""

    capital: Serie
    """Lo que entra al saldo agotable, que el libro rotula `Capex (sin maquinarias)`."""

    saldo_inicial: Serie
    depreciacion: Serie
    saldo_final: Serie


def trazar_agotamiento(
    horizonte: Horizonte, inversiones: Serie, agotamiento: Agotamiento
) -> TrazaDelAgotamiento:
    """Arma la tabla del libro a partir de lo que ya calculan las tres primitivas."""
    finales = saldo_de_reservas(horizonte, agotamiento)
    iniciales = (agotamiento.reservas, *finales[:-1]) if horizonte.anos else ()
    tasas = tasas_de_agotamiento(horizonte, agotamiento)
    capital = _alineada(horizonte, inversiones)
    saldo_inicial, cuotas, saldo_final = _rodar_saldo(horizonte, capital, tasas)
    return TrazaDelAgotamiento(
        reservas_iniciales=iniciales,
        extraido=_alineada(horizonte, agotamiento.extraido),
        conversion_de_recursos=_alineada(horizonte, agotamiento.conversion_de_recursos),
        reservas_finales=finales,
        tasa=tasas,
        capital=capital,
        saldo_inicial=saldo_inicial,
        depreciacion=cuotas,
        saldo_final=saldo_final,
    )


COHORTE_UNICA = ""
"""Clave de la cosecha sin etapa, la que usa quien no separa por etapa."""


def depreciacion_por_etapa_y_componente(
    horizonte: Horizonte,
    por_etapa_y_naturaleza: Mapping[str, Mapping[str, Serie]],
    tasas: TasasDeDepreciacion,
    *,
    produccion: Serie | None = None,
    agotamiento: Agotamiento | None = None,
    proyeccion: Serie = (),
    estudios: Serie = (),
) -> dict[str, dict[str, Serie]]:
    """Depreciación abierta por línea del libro y, dentro, por componente.

    El resumen con que la hoja abre cada bloque no va por naturaleza contable
    sino **por etapa**: capex inicial, sostenimiento y escudo de cierre, más los
    estudios y la proyección ya contabilizada. Es otro corte del mismo dinero, y
    esta función lo produce depreciando cada cosecha por separado.

    **Partirlo no cambia ningún total, y esa es la condición que lo hace
    legítimo.** La cuota lineal superpone un cronograma independiente por año de
    inversión, y la etapa la decide el año, de modo que las cosechas de dos
    etapas son disjuntas y sus cronogramas no se tocan. El agotamiento lleva un
    saldo único con `cuota = saldo x tasa`, lineal en las inversiones, y su tasa
    sale de las reservas y no del saldo. Las dos puertas de producción también
    son lineales en la serie que reciben. Sumar las etapas devuelve exactamente
    lo que sale de depreciar el conjunto, y `depreciacion_por_componente` lo
    comprueba por construcción al derivarse de aquí.
    """
    ritmo = tasas_de_agotamiento(horizonte, agotamiento) if agotamiento is not None else ()
    lineas: dict[str, dict[str, Serie]] = {}
    for etapa, naturalezas in por_etapa_y_naturaleza.items():
        detalle: dict[str, Serie] = {}
        for componente in NATURALEZAS:
            inversiones = _alineada(horizonte, naturalezas.get(componente, ()))
            if not any(inversiones):
                continue
            if agotamiento is not None and componente in COMPONENTES_POR_AGOTAMIENTO:
                detalle[componente] = agotar(horizonte, inversiones, ritmo)
                continue
            tasa = tasas.de(componente)
            if tasa == 0.0:
                continue
            detalle[componente] = depreciar(horizonte, inversiones, tasa)
        if detalle:
            lineas[etapa] = detalle

    if any(estudios):
        lineas[ESTUDIOS] = {
            ESTUDIOS: depreciar(horizonte, _alineada(horizonte, estudios), tasas.de_estudios)
        }

    if any(proyeccion):
        lineas[PROYECCION_SAP] = {PROYECCION_SAP: _alineada(horizonte, proyeccion)}

    if produccion is None:
        return lineas
    # La via financiera se identifica por traer agotamiento, y es la que el
    # libro cierra ano a ano en vez de acumular.
    puerta = (
        _en_anos_con_produccion if agotamiento is not None else _sin_depreciar_antes_de_producir
    )
    return {
        etapa: {
            componente: puerta(horizonte, serie, produccion)
            for componente, serie in detalle.items()
        }
        for etapa, detalle in lineas.items()
    }


def depreciacion_por_componente(
    horizonte: Horizonte,
    capital: CapitalDeUnidad | None,
    tasas: TasasDeDepreciacion,
    *,
    produccion: Serie | None = None,
    agotamiento: Agotamiento | None = None,
    proyeccion: Serie = (),
    estudios: Serie = (),
    por_etapa_y_naturaleza: Mapping[str, Mapping[str, Serie]] | None = None,
) -> dict[str, Serie]:
    """Depreciación de cada componente contable de una unidad.

    Sin `agotamiento` todos los componentes se deprecian lineal, que es la vía
    tributaria. Con él, los de `COMPONENTES_POR_AGOTAMIENTO` se agotan contra las
    reservas y la maquinaria sigue lineal, que es la financiera.

    Lo no depreciable se deduce entero en su año en las dos, y el estudio
    capitalizable se deprecia lineal en las dos: el libro no los distingue por
    vía.

    **Es la consolidación de `depreciacion_por_etapa_y_componente`**, que es
    donde vive la regla de la cuota. Sin `por_etapa_y_naturaleza` el capital
    entero es una sola cosecha y el resultado es el de siempre; con él, la suma
    de las etapas da exactamente lo mismo.
    """
    if por_etapa_y_naturaleza is None:
        por_naturaleza = (
            {c: capital.naturaleza(c, horizonte) for c in NATURALEZAS}
            if capital is not None
            else {}
        )
        por_etapa_y_naturaleza = {COHORTE_UNICA: por_naturaleza}
    lineas = depreciacion_por_etapa_y_componente(
        horizonte,
        por_etapa_y_naturaleza,
        tasas,
        produccion=produccion,
        agotamiento=agotamiento,
        proyeccion=proyeccion,
        estudios=estudios,
    )
    detalle: dict[str, list[float]] = {}
    for componentes in lineas.values():
        for componente, serie in componentes.items():
            acumulada = detalle.setdefault(componente, [0.0] * horizonte.anos)
            for i, valor in enumerate(serie):
                acumulada[i] += valor
    # El orden es el del catalogo, con los estudios y la proyeccion detras: sin
    # esto lo trae el de las etapas, que pone antes lo de la cosecha inicial.
    orden = [*NATURALEZAS, ESTUDIOS, PROYECCION_SAP]
    return {c: tuple(detalle[c]) for c in orden if c in detalle}


def cosechas_por_etapa_y_componente(
    horizonte: Horizonte,
    por_etapa_y_naturaleza: Mapping[str, Mapping[str, Serie]],
    tasas: TasasDeDepreciacion,
    *,
    produccion: Serie | None = None,
    agotamiento: Agotamiento | None = None,
    estudios: Serie = (),
) -> dict[tuple[str, str], dict[int, Serie]]:
    """Los triángulos del libro, uno por línea y componente.

    Solo los tiene lo que se deprecia lineal. **El agotamiento no abre triángulo
    y el libro tampoco se lo dibuja**: lleva un saldo único, de modo que no hay
    cosecha a la que atribuir una cuota. Lo mismo vale para la proyección ya
    contabilizada, que no sale de ninguna inversión de este caso.

    La puerta de producción se aplica cosecha a cosecha, y sumarlas devuelve la
    misma serie que aplicarla al total: las dos puertas son lineales.
    """
    puerta = (
        _en_anos_con_produccion if agotamiento is not None else _sin_depreciar_antes_de_producir
    )

    def con_puerta(cosechas: dict[int, Serie]) -> dict[int, Serie]:
        if produccion is None:
            return cosechas
        return {ano: puerta(horizonte, fila, produccion) for ano, fila in cosechas.items()}

    triangulos: dict[tuple[str, str], dict[int, Serie]] = {}
    for etapa, naturalezas in por_etapa_y_naturaleza.items():
        for componente in NATURALEZAS:
            inversiones = _alineada(horizonte, naturalezas.get(componente, ()))
            if not any(inversiones):
                continue
            if agotamiento is not None and componente in COMPONENTES_POR_AGOTAMIENTO:
                continue
            tasa = tasas.de(componente)
            if tasa == 0.0:
                continue
            triangulos[etapa, componente] = con_puerta(
                cronograma_por_cosecha(horizonte, inversiones, tasa)
            )

    if any(estudios):
        triangulos[ESTUDIOS, ESTUDIOS] = con_puerta(
            cronograma_por_cosecha(horizonte, _alineada(horizonte, estudios), tasas.de_estudios)
        )
    return triangulos


@dataclass(frozen=True)
class DetalleDeDepreciacionDeUnidad:
    """Todo lo que la hoja del libro muestra de una unidad, las dos vías.

    Se guarda entero porque la hoja lo muestra entero: el resumen por etapa, el
    triángulo de cada línea y la tabla con que la vía financiera deriva su cuota.
    Recomponerlo desde el total es imposible, que es la misma razón por la que la
    depreciación se lleva separada por mina.
    """

    tributaria: dict[str, dict[str, Serie]]
    financiera: dict[str, dict[str, Serie]]
    cosechas_tributarias: dict[tuple[str, str], dict[int, Serie]]
    cosechas_financieras: dict[tuple[str, str], dict[int, Serie]]
    agotamiento: TrazaDelAgotamiento | None
    periodo_con_produccion: Serie
    """La bandera con que el libro cierra los dos bloques. Uno o cero por año."""


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
    cruces: Mapping[str, Mapping[str, Mapping[str, Serie]]] | None = None,
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
    cruzados = cruces or {}
    return {
        nombre: depreciacion_por_componente(
            horizonte,
            por_nombre.get(nombre),
            tasas,
            produccion=series.get(nombre),
            agotamiento=agota.get(nombre),
            proyeccion=proyectada.get(nombre, ()),
            estudios=capitalizados.get(nombre, ()),
            por_etapa_y_naturaleza=cruzados.get(nombre),
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


def _en_anos_con_produccion(horizonte: Horizonte, depreciacion: Serie, produccion: Serie) -> Serie:
    """Deja la cuota solo en los ejercicios con produccion, sin acumular.

    Es la bandera `Ano con produccion` del libro, que multiplica el total de la
    depreciacion financiera de la unidad. Un ano de parada no difiere la cuota:
    la pierde.
    """
    _verificar_produccion(horizonte, produccion)
    return tuple(valor if produccion[i] != 0.0 else 0.0 for i, valor in enumerate(depreciacion))


def _sin_depreciar_antes_de_producir(
    horizonte: Horizonte, depreciacion: Serie, produccion: Serie
) -> Serie:
    """La puerta de la regla `013`: **difiere y libera, no anula.**

    El libro no descarta la cuota de los ejercicios anteriores al primero con
    producción acumulada: la guarda y la reconoce entera en ese primer ejercicio.
    Su fórmula lo dice sin rodeos —`IF(produccion acumulada = 0, 0, SUM(todo el
    cronograma hasta el ano) - SUM(lo ya reconocido))`—, y la diferencia con
    anularla no es de matiz: en el caso 7 vale 382 851,4 k$ concentrados en un
    solo ejercicio.

    Una unidad que no produce nunca deja el saldo diferido y no deprecia, que es
    lo mismo que hacía antes.
    """
    _verificar_produccion(horizonte, produccion)
    acumulada = 0.0
    diferida = 0.0
    resultado: list[float] = []
    for i, valor in enumerate(depreciacion):
        acumulada += produccion[i]
        if acumulada == 0.0:
            diferida += valor
            resultado.append(0.0)
        else:
            resultado.append(valor + diferida)
            diferida = 0.0
    return tuple(resultado)


def _verificar_produccion(horizonte: Horizonte, produccion: Serie) -> None:
    if len(produccion) != horizonte.anos:
        raise ErrorDepreciacion(
            f"La serie de produccion trae {len(produccion)} valores y el horizonte tiene "
            f"{horizonte.anos} anos."
        )
