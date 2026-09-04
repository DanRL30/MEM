"""Casos sintéticos del contraste, con la forma de los tres arquetipos.

No contienen datos de MINSUR. Son casos inventados con cifras redondas,
elegidas para que la aritmética se pueda seguir a mano: es lo que permite que
el contraste sea una comprobación y no un registro de lo que el motor devolvió
la primera vez.

Los tres reproducen la **forma** de los arquetipos del libro, que es lo que
importa para el contraste estructural:

    unidad simple       una mina que vende metal refinado
    refinería            minas que alimentan una refineria con tope de capacidad
    dos proyectos       una operacion en marcha y un proyecto que entra tarde
    agotamiento         minas cuyo capital se agota contra sus reservas
    polimetálico        dos minas que liquidan concentrado de cobre con plata
    capital de trabajo  una mina con parada intermedia y cuentas que rotan
    hoja `Otros`        una mina con las nueve bandas de egreso llenas
    bloque tributario   una mina de margen alto, con escalas progresivas

Los casos certificados con datos reales son otra cosa: viven en el tenant de
MINSUR, se referencian por manifiesto en `fixtures/certificados/` y sus pruebas
se marcan `tenant_minsur`.
"""

from __future__ import annotations

from minsur_engine.capex import CapitalDeUnidad, clasificar_por_etapa
from minsur_engine.caso import (
    Caso,
    DatosComunes,
    DatosMaestros,
    MetalDelConcentrado,
    ProduccionDeUnidad,
    TerminosComerciales,
    TerminosDelConcentrado,
    UnidadProductiva,
)
from minsur_engine.depreciacion import TasasDeDepreciacion
from minsur_engine.horizonte import Horizonte
from minsur_engine.impuestos import EscalaProgresiva, Tramo
from minsur_engine.parametros import ParametrosCorporativos

# Escala de regalia plana al 1 %: con un solo tramo, la tasa efectiva no
# depende del margen y la aritmetica del caso se puede seguir a mano.
ESCALA_PLANA = EscalaProgresiva(tramos=(Tramo(0.0, 10.0, 0.01),))
SIN_IEM = EscalaProgresiva(tramos=(Tramo(0.0, 10.0, 0.0),))

PARAMETROS = ParametrosCorporativos(
    version_datos_maestros="CP-SINTETICO-01",
    tasa_descuento=0.10,
    participacion_trabajadores=0.08,
    impuesto_renta=0.295,
    regalia_minima=0.01,
    osinergmin=0.0,
    oefa=0.0,
    fondo_jubilacion_minera=0.005,
)

MAESTROS = DatosMaestros(
    parametros=PARAMETROS,
    # Al 50 % un activo se agota en dos ejercicios, que es lo que hace legible
    # el cronograma en un horizonte de tres anos.
    tasas_tributarias=TasasDeDepreciacion(maquinaria=0.50, instalaciones=0.10, edificaciones=0.05),
    tasas_financieras=TasasDeDepreciacion(maquinaria=0.50, instalaciones=0.10, edificaciones=0.05),
    escala_regalia=ESCALA_PLANA,
    escala_iem=SIN_IEM,
)


def unidad_simple() -> Caso:
    """Una mina, tres años, sin capital de trabajo ni gastos comunes.

    El primer ejercicio invierte y no produce; los dos siguientes producen lo
    mismo. Es el caso cuyos números se verifican uno a uno.
    """
    horizonte = Horizonte(primer_ano=2027, anos=3)
    # La etapa no se declara: se deriva de la naturaleza y de los anos con
    # produccion, que es lo que hace el libro y lo que hace la ingesta.
    naturaleza = {"maquinaria": horizonte.serie([1_000_000.0, 0.0, 0.0], nombre="maquinaria")}
    capital = CapitalDeUnidad(
        unidad="Mina Unica",
        por_etapa=clasificar_por_etapa(horizonte, naturaleza, anos_activos=(1, 2)),
        por_naturaleza=naturaleza,
    )
    unidad = UnidadProductiva(
        nombre="Mina Unica",
        tipo="mina",
        produccion=ProduccionDeUnidad(
            mineral_tratado=horizonte.serie([0.0, 1_000.0, 1_000.0], nombre="tratado"),
            concentrado_producido=horizonte.ceros(),
            metal_refinado_vendido=horizonte.serie([0.0, 100.0, 100.0], nombre="refinado"),
        ),
        costos={"Mina": horizonte.serie([0.0, 200_000.0, 200_000.0], nombre="mina")},
        capital=capital,
    )
    return Caso(
        nombre="Sintetico: unidad simple",
        horizonte=horizonte,
        unidades=(unidad,),
        terminos=TerminosComerciales(
            precio_metal_refinado=horizonte.serie([10_000.0] * 3, nombre="precio"),
            premio_metal_refinado=horizonte.ceros(),
            precio_metal_en_concentrado=horizonte.ceros(),
            factor_metal_pagable=horizonte.ceros(),
        ),
        datos_comunes=DatosComunes(gastos_administrativos=horizonte.ceros()),
    )


def caso_con_refineria() -> Caso:
    """Dos minas que alimentan una refinería cuyo tope acota el tratamiento.

    Es el arquetipo de operación consolidada: el cuello de botella está en la
    refinería y el concentrado que no cabe queda como excedente.
    """
    horizonte = Horizonte(primer_ano=2027, anos=4)

    def mina(nombre: str, concentrado: list[float]) -> UnidadProductiva:
        serie = horizonte.serie(concentrado, nombre=f"{nombre}/concentrado")
        return UnidadProductiva(
            nombre=nombre,
            tipo="mina",
            produccion=ProduccionDeUnidad(
                mineral_tratado=horizonte.serie(
                    [c * 10.0 for c in concentrado], nombre=f"{nombre}/tratado"
                ),
                concentrado_producido=serie,
                metal_en_concentrado_vendido=horizonte.serie(
                    [c * 0.5 for c in concentrado], nombre=f"{nombre}/fino"
                ),
            ),
            costos={"Mina": horizonte.serie([c * 100.0 for c in concentrado], nombre="mina")},
        )

    refineria = UnidadProductiva(
        nombre="Refineria",
        tipo="refineria",
        produccion=ProduccionDeUnidad(
            mineral_tratado=horizonte.serie([100.0] * 4, nombre="refineria/tratado"),
            concentrado_producido=horizonte.ceros(),
            capacidad_de_tratamiento=horizonte.serie([1_500.0] * 4, nombre="capacidad"),
        ),
        costos={"Fundición": horizonte.serie([50_000.0] * 4, nombre="refineria")},
    )

    return Caso(
        nombre="Sintetico: dos minas y una refineria",
        horizonte=horizonte,
        unidades=(
            mina("Mina Norte", [800.0, 900.0, 1_000.0, 1_000.0]),
            mina("Mina Sur", [400.0, 500.0, 600.0, 700.0]),
            refineria,
        ),
        terminos=TerminosComerciales(
            precio_metal_refinado=horizonte.ceros(),
            premio_metal_refinado=horizonte.ceros(),
            precio_metal_en_concentrado=horizonte.serie([20_000.0] * 4, nombre="precio"),
            factor_metal_pagable=horizonte.serie([0.9] * 4, nombre="factor"),
        ),
        datos_comunes=DatosComunes(
            gastos_administrativos=horizonte.serie([100_000.0] * 4, nombre="admin"),
            dias_por_cobrar=horizonte.serie([40.0] * 4, nombre="dias cxc"),
            dias_por_pagar=horizonte.serie([55.0] * 4, nombre="dias cxp"),
        ),
    )


def dos_proyectos() -> Caso:
    """Una operación en marcha y un proyecto que entra en el tercer año.

    Es el arquetipo combinado, y el que comprueba que la participación de una
    unidad se deriva de sus datos: el proyecto no tiene interruptor, tiene
    ceros hasta que arranca.
    """
    horizonte = Horizonte(primer_ano=2027, anos=5)
    en_marcha = UnidadProductiva(
        nombre="Operacion",
        tipo="mina",
        produccion=ProduccionDeUnidad(
            mineral_tratado=horizonte.serie([1_000.0] * 5, nombre="tratado"),
            concentrado_producido=horizonte.ceros(),
            metal_refinado_vendido=horizonte.serie([80.0] * 5, nombre="refinado"),
        ),
        costos={"Mina": horizonte.serie([300_000.0] * 5, nombre="mina")},
    )
    proyecto = UnidadProductiva(
        nombre="Proyecto X",
        tipo="mina",
        produccion=ProduccionDeUnidad(
            mineral_tratado=horizonte.serie([0.0, 0.0, 500.0, 800.0, 800.0], nombre="tratado"),
            concentrado_producido=horizonte.ceros(),
            metal_refinado_vendido=horizonte.serie([0.0, 0.0, 40.0, 60.0, 60.0], nombre="refinado"),
        ),
        costos={
            "Mina": horizonte.serie([0.0, 0.0, 150_000.0, 240_000.0, 240_000.0], nombre="mina")
        },
        capital=CapitalDeUnidad(
            unidad="Proyecto X",
            por_etapa={
                "inicial": horizonte.serie([0.0, 600_000.0, 0.0, 0.0, 0.0], nombre="inicial")
            },
            por_naturaleza={
                "maquinaria": horizonte.serie([0.0, 600_000.0, 0.0, 0.0, 0.0], nombre="maquinaria")
            },
        ),
    )
    return Caso(
        nombre="Sintetico: dos proyectos",
        horizonte=horizonte,
        unidades=(en_marcha, proyecto),
        terminos=TerminosComerciales(
            precio_metal_refinado=horizonte.serie([12_000.0] * 5, nombre="precio"),
            premio_metal_refinado=horizonte.serie([200.0] * 5, nombre="premio"),
            precio_metal_en_concentrado=horizonte.ceros(),
            factor_metal_pagable=horizonte.ceros(),
        ),
        datos_comunes=DatosComunes(
            gastos_administrativos=horizonte.serie([50_000.0] * 5, nombre="admin"),
            capacidad_para_intensidad=800.0,
        ),
    )


def caso_con_agotamiento() -> Caso:
    """Dos minas cuyo capital se agota al ritmo al que se vacía el yacimiento.

    Es el arquetipo que separa las dos vías de la depreciación, que no se
    distinguen por la tasa sino por el método: la tributaria reparte lineal y la
    financiera agota las instalaciones y las edificaciones contra las reservas.

    Las dos unidades cubren los dos orígenes de la reserva. `Mina Larga` la
    declara —es una unidad en marcha, que la trae de su plan de vida de mina— y
    para el último ejercicio sin haber agotado su capital, que es donde las dos
    vías se separan del todo: la tributaria sigue depreciando y la financiera
    pierde la cuota del año de parada. `Proyecto Y` la deja vacía, de modo que
    sale de lo que su propio plan extrae, y termina agotando exactamente lo que
    invirtió.
    """
    horizonte = Horizonte(primer_ano=2027, anos=4)

    # 2 000 t extraidas contra 4 000 declaradas: el saldo cierra en 4 000,
    # 3 000, 2 000 y 2 000, y las tasas de agotamiento salen 0, 1/4, 1/3 y 0.
    naturaleza_larga = {
        "maquinaria": horizonte.serie([400_000.0, 0.0, 0.0, 0.0], nombre="maquinaria"),
        "edificaciones": horizonte.serie([1_000_000.0, 0.0, 0.0, 0.0], nombre="edificaciones"),
    }
    larga = UnidadProductiva(
        nombre="Mina Larga",
        tipo="mina",
        produccion=ProduccionDeUnidad(
            mineral_tratado=horizonte.serie([0.0, 1_000.0, 1_000.0, 0.0], nombre="tratado"),
            mineral_extraido=horizonte.serie([0.0, 1_000.0, 1_000.0, 0.0], nombre="extraido"),
            concentrado_producido=horizonte.ceros(),
            metal_refinado_vendido=horizonte.serie([0.0, 200.0, 200.0, 0.0], nombre="refinado"),
        ),
        costos={"Mina": horizonte.serie([0.0, 400_000.0, 400_000.0, 0.0], nombre="mina")},
        capital=CapitalDeUnidad(
            unidad="Mina Larga",
            por_etapa=clasificar_por_etapa(horizonte, naturaleza_larga, anos_activos=(1, 2)),
            por_naturaleza=naturaleza_larga,
        ),
        reservas=4_000.0,
    )

    # Sin reservas declaradas son las 1 000 t que extrae el plan, y la tasa del
    # ultimo ejercicio llega al 100 %: el activo se agota justo cuando ellas.
    naturaleza_proyecto = {
        "instalaciones": horizonte.serie([0.0, 600_000.0, 0.0, 0.0], nombre="instalaciones"),
    }
    proyecto = UnidadProductiva(
        nombre="Proyecto Y",
        tipo="mina",
        produccion=ProduccionDeUnidad(
            mineral_tratado=horizonte.serie([0.0, 0.0, 500.0, 500.0], nombre="tratado"),
            mineral_extraido=horizonte.serie([0.0, 0.0, 500.0, 500.0], nombre="extraido"),
            concentrado_producido=horizonte.ceros(),
            metal_refinado_vendido=horizonte.serie([0.0, 0.0, 50.0, 50.0], nombre="refinado"),
        ),
        costos={"Mina": horizonte.serie([0.0, 0.0, 100_000.0, 100_000.0], nombre="mina")},
        capital=CapitalDeUnidad(
            unidad="Proyecto Y",
            por_etapa=clasificar_por_etapa(horizonte, naturaleza_proyecto, anos_activos=(2, 3)),
            por_naturaleza=naturaleza_proyecto,
        ),
    )

    return Caso(
        nombre="Sintetico: agotamiento contra reservas",
        horizonte=horizonte,
        unidades=(larga, proyecto),
        terminos=TerminosComerciales(
            precio_metal_refinado=horizonte.serie([10_000.0] * 4, nombre="precio"),
            premio_metal_refinado=horizonte.ceros(),
            precio_metal_en_concentrado=horizonte.ceros(),
            factor_metal_pagable=horizonte.ceros(),
        ),
        datos_comunes=DatosComunes(gastos_administrativos=horizonte.ceros()),
    )


# --- Concentrado polimetalico --------------------------------------------------

MERMA = 0.10
MAQUILA = 100.0
DEDUCCION_MINIMA_CU = 0.01
FACTOR_PAGABLE_CU = 0.90
PRECIO_CU = 10_000.0
PRECIO_AG = 30.0
TARIFA_RC_CU = 0.02
"""Dolares por libra: es la tarifa que el libro incrusta en la formula."""

TARIFA_RC_AG = 0.60
"""Dolares por onza troy."""

PENALIDAD_CU = 5.0
PENALIDAD_AG = 2.0

LEY_CU_ALFA = 0.30
LEY_CU_BETA = 0.20
LEY_PAGABLE_AG_ALFA = 100.0
LEY_PAGABLE_AG_BETA = 50.0
"""Gramos por tonelada. La de plata se declara: el libro la calcula con un factor
cien sobre una ley en onzas por tonelada y esa formula esta consultada (regla 045).
"""


def caso_polimetalico() -> Caso:
    """Dos minas que venden concentrado de cobre con plata dentro.

    Las dos leyes de cobre son distintas a proposito: **es lo que hace observable
    la regla de oro**. Con 0,30 la ley pagable la fija el factor y con 0,20 la
    fija tambien el factor, pero el valor liquidado de cada una es suyo y no se
    puede reconstruir desde un total agregado.

    Ninguna declara ley pagable de cobre ni cargo de refinacion: los dos salen de
    las condiciones del contrato, que es lo que hace el libro en su hoja de
    supuestos. La de plata si se declara, porque su formula esta consultada.
    """
    horizonte = Horizonte(primer_ano=2027, anos=3)

    def mina(
        nombre: str, concentrado: float, ley_cu: float, ley_pagable_ag: float, costo: float
    ) -> UnidadProductiva:
        return UnidadProductiva(
            nombre=nombre,
            tipo="mina",
            produccion=ProduccionDeUnidad(
                mineral_tratado=horizonte.serie(
                    [0.0, concentrado * 10.0, concentrado * 10.0], nombre=f"{nombre}/tratado"
                ),
                mineral_extraido=horizonte.serie(
                    [0.0, concentrado * 10.0, concentrado * 10.0], nombre=f"{nombre}/extraido"
                ),
                concentrado_producido=horizonte.ceros(),
                concentrado_de_cu=horizonte.serie(
                    [0.0, concentrado, concentrado], nombre=f"{nombre}/concentrado de Cu"
                ),
                ley_cu=horizonte.serie([ley_cu] * 3, nombre=f"{nombre}/ley Cu"),
            ),
            ley_pagable_declarada={"Ag": horizonte.serie([ley_pagable_ag] * 3, nombre="Ag")},
            costos={"Mina": horizonte.serie([0.0, costo, costo], nombre="mina")},
        )

    return Caso(
        nombre="Sintetico: concentrado polimetalico",
        horizonte=horizonte,
        unidades=(
            mina("Mina Alfa", 1_000.0, LEY_CU_ALFA, LEY_PAGABLE_AG_ALFA, 1_000_000.0),
            mina("Mina Beta", 500.0, LEY_CU_BETA, LEY_PAGABLE_AG_BETA, 400_000.0),
        ),
        terminos=TerminosComerciales(
            precio_metal_refinado=horizonte.ceros(),
            premio_metal_refinado=horizonte.ceros(),
            precio_metal_en_concentrado=horizonte.ceros(),
            factor_metal_pagable=horizonte.ceros(),
            ajustes=horizonte.serie([0.0, 50_000.0, 0.0], nombre="ajustes"),
            concentrado=TerminosDelConcentrado(
                merma=horizonte.serie([MERMA] * 3, nombre="merma"),
                maquila_por_tonelada=horizonte.serie([MAQUILA] * 3, nombre="maquila"),
                metales=(
                    MetalDelConcentrado(
                        nombre="Cu",
                        ley_pagable=(),
                        precio=horizonte.serie([PRECIO_CU] * 3, nombre="precio Cu"),
                        cargo_de_refinacion=(),
                        deduccion_minima=horizonte.serie(
                            [DEDUCCION_MINIMA_CU] * 3, nombre="deduccion Cu"
                        ),
                        factor_pagable=horizonte.serie([FACTOR_PAGABLE_CU] * 3, nombre="factor Cu"),
                        tarifa_de_refinacion=horizonte.serie([TARIFA_RC_CU] * 3, nombre="RC Cu"),
                        penalidades_por_tonelada=horizonte.serie(
                            [PENALIDAD_CU] * 3, nombre="penalidad Cu"
                        ),
                    ),
                    MetalDelConcentrado(
                        nombre="Ag",
                        ley_pagable=(),
                        precio=horizonte.serie([PRECIO_AG] * 3, nombre="precio Ag"),
                        cargo_de_refinacion=(),
                        en_onzas_troy=True,
                        tarifa_de_refinacion=horizonte.serie([TARIFA_RC_AG] * 3, nombre="RC Ag"),
                        penalidades_por_tonelada=horizonte.serie(
                            [PENALIDAD_AG] * 3, nombre="penalidad Ag"
                        ),
                    ),
                ),
            ),
        ),
        datos_comunes=DatosComunes(gastos_administrativos=horizonte.ceros()),
    )


# --- Capital de trabajo --------------------------------------------------------

DIAS_POR_COBRAR = 36.0
"""Un decimo del ano comercial: la cartera es el 10 % de la venta del ano."""

DIAS_POR_PAGAR = 72.0
"""Un quinto: la deuda es el 20 % de la bolsa de egresos del ano."""

TASA_IGV = 0.18
PORCENTAJE_DE_VENTAS = 0.50
PORCENTAJE_DE_COMPRAS = 0.50
OTRAS_POR_COBRAR = 5_000.0
OTRAS_POR_PAGAR = 3_000.0


def caso_de_capital_de_trabajo() -> Caso:
    """Una mina que produce dos años, para uno y vuelve a producir.

    La parada es lo que separa las dos banderas posibles: el libro liquida las
    cuentas en el **ultimo ano con produccion**, y tomar la venta por bandera
    las liquidaria en la parada y las reabriria despues.

    Las cifras son redondas a proposito: 100 tmf a 10 000 dan una venta de un
    millon, y con 36 dias sobre 360 la cartera es la decima parte.
    """
    horizonte = Horizonte(primer_ano=2027, anos=5)
    # Dos anos de produccion, una parada y un reinicio: los tres casos que
    # distingue la formula del libro caben en un solo horizonte.
    tratado = [0.0, 1_000.0, 1_000.0, 0.0, 1_000.0]
    naturaleza = {
        "maquinaria": horizonte.serie([1_000_000.0, 0.0, 0.0, 0.0, 0.0], nombre="maquinaria")
    }
    unidad = UnidadProductiva(
        nombre="Mina Intermitente",
        tipo="mina",
        produccion=ProduccionDeUnidad(
            mineral_tratado=horizonte.serie(tratado, nombre="tratado"),
            mineral_extraido=horizonte.serie(tratado, nombre="extraido"),
            concentrado_producido=horizonte.ceros(),
            metal_refinado_vendido=horizonte.serie(
                [0.0, 100.0, 100.0, 0.0, 100.0], nombre="refinado"
            ),
        ),
        costos={
            "Mina": horizonte.serie([0.0, 200_000.0, 200_000.0, 0.0, 200_000.0], nombre="mina")
        },
        capital=CapitalDeUnidad(
            unidad="Mina Intermitente",
            por_etapa=clasificar_por_etapa(horizonte, naturaleza, anos_activos=(1, 2, 4)),
            por_naturaleza=naturaleza,
        ),
    )
    return Caso(
        nombre="Sintetico: capital de trabajo",
        horizonte=horizonte,
        unidades=(unidad,),
        terminos=TerminosComerciales(
            precio_metal_refinado=horizonte.serie([10_000.0] * 5, nombre="precio"),
            premio_metal_refinado=horizonte.ceros(),
            precio_metal_en_concentrado=horizonte.ceros(),
            factor_metal_pagable=horizonte.ceros(),
        ),
        datos_comunes=DatosComunes(
            gastos_administrativos=horizonte.ceros(),
            dias_por_cobrar=horizonte.serie([DIAS_POR_COBRAR] * 5, nombre="dias por cobrar"),
            dias_por_pagar=horizonte.serie([DIAS_POR_PAGAR] * 5, nombre="dias por pagar"),
            otras_cuentas_por_cobrar=horizonte.serie(
                [OTRAS_POR_COBRAR] * 5, nombre="otras cuentas por cobrar"
            ),
            otras_cuentas_por_pagar=horizonte.serie(
                [OTRAS_POR_PAGAR] * 5, nombre="otras cuentas por pagar"
            ),
            tasa_igv=TASA_IGV,
            porcentaje_de_ventas_de_exportacion=PORCENTAJE_DE_VENTAS,
            porcentaje_de_compras_locales=PORCENTAJE_DE_COMPRAS,
        ),
    )


# --- Hoja `Otros` --------------------------------------------------------------

GESTION_SOCIAL_DEL_CASO = 60_000.0
"""El gasto que el libro **no** lleva a su bolsa de egresos: la regla `081`."""

DONACIONES_DEL_CASO = 10_000.0
SERVIDUMBRE_DEL_CASO = 30_000.0
PREDIOS_DEL_CASO = 25_000.0
EXPLORACIONES_DEL_CASO = 50_000.0
ESTUDIOS_DEL_CASO = 15_000.0
ADMINISTRATIVOS_DEL_CASO = 40_000.0
OTROS_GASTOS_DEL_CASO = 12_000.0
OTROS_EGRESOS_DEL_CASO = 20_000.0
FLETES_LOM = 8_000.0
GASTO_DE_VENTAS_LOM = 6_000.0
TARIFA_DE_FLETE = 4.0
TARIFA_DE_GASTO_DE_VENTAS = 3.0


def caso_de_la_hoja_otros(*, gestion_social: float = GESTION_SOCIAL_DEL_CASO) -> Caso:
    """Una mina con las nueve bandas de la hoja `Otros` llenas.

    **El primer ejercicio cierra en perdida y los otros dos en ganancia**, que es
    lo unico que separa las dos filas de regalia del libro: la misma cifra va a
    `Otros!33` o a `Otros!37` segun el signo de la utilidad operativa. Es la
    regla `080`.

    `gestion_social` es parametro y no constante para poder correr el mismo caso
    con y sin ella: la bolsa de egresos tiene que salir identica en los dos, que
    es la regla `081`. Con la gestion social dentro, las dos bolsas diferian en
    exactamente ese gasto y nada lo acusaba.
    """
    horizonte = Horizonte(primer_ano=2027, anos=3)
    naturaleza = {"maquinaria": horizonte.serie([1_000_000.0, 0.0, 0.0], nombre="maquinaria")}
    # Venta baja contra costo alto en el primer ejercicio: con la regalia minima
    # al 1 % de la venta, ese ano tiene regalia y no tiene utilidad operativa.
    unidad = UnidadProductiva(
        nombre="Mina de Nueve Bandas",
        tipo="mina",
        produccion=ProduccionDeUnidad(
            mineral_tratado=horizonte.serie([1_000.0] * 3, nombre="tratado"),
            mineral_extraido=horizonte.serie([1_000.0] * 3, nombre="extraido"),
            concentrado_producido=horizonte.serie([500.0] * 3, nombre="concentrado"),
            metal_refinado_vendido=horizonte.serie([20.0, 200.0, 200.0], nombre="refinado"),
        ),
        costos={"Mina": horizonte.serie([500_000.0] * 3, nombre="mina")},
        gastos={
            "Gastos administrativos": horizonte.serie(
                [ADMINISTRATIVOS_DEL_CASO] * 3, nombre="administrativos"
            ),
            "Gestión Social": horizonte.serie([gestion_social] * 3, nombre="gestion social"),
            "Donaciones": horizonte.serie([DONACIONES_DEL_CASO] * 3, nombre="donaciones"),
            "Servidumbres y usufructos": horizonte.serie(
                [SERVIDUMBRE_DEL_CASO] * 3, nombre="servidumbre"
            ),
            "Estudios Pre Factibilidad (Gasto)": horizonte.serie(
                [ESTUDIOS_DEL_CASO] * 3, nombre="estudios"
            ),
            "Predios": horizonte.serie([PREDIOS_DEL_CASO] * 3, nombre="predios"),
            "Exploraciones": horizonte.serie([EXPLORACIONES_DEL_CASO] * 3, nombre="exploraciones"),
        },
        capital=CapitalDeUnidad(
            unidad="Mina de Nueve Bandas",
            por_etapa=clasificar_por_etapa(horizonte, naturaleza, anos_activos=(0, 1, 2)),
            por_naturaleza=naturaleza,
        ),
    )
    return Caso(
        nombre="Sintetico: hoja Otros",
        horizonte=horizonte,
        unidades=(unidad,),
        terminos=TerminosComerciales(
            precio_metal_refinado=horizonte.serie([10_000.0] * 3, nombre="precio"),
            premio_metal_refinado=horizonte.ceros(),
            precio_metal_en_concentrado=horizonte.ceros(),
            factor_metal_pagable=horizonte.ceros(),
        ),
        datos_comunes=DatosComunes(
            gastos_administrativos=horizonte.ceros(),
            otros_gastos=horizonte.serie([OTROS_GASTOS_DEL_CASO] * 3, nombre="otros gastos"),
            otros_egresos=horizonte.serie([OTROS_EGRESOS_DEL_CASO] * 3, nombre="otros egresos"),
            fletes_lom=horizonte.serie([FLETES_LOM] * 3, nombre="fletes LOM"),
            fletes_por_tonelada=horizonte.serie([TARIFA_DE_FLETE] * 3, nombre="tarifa de flete"),
            gasto_de_ventas_lom=horizonte.serie(
                [GASTO_DE_VENTAS_LOM] * 3, nombre="gasto de ventas LOM"
            ),
            gasto_de_ventas_por_tonelada=horizonte.serie(
                [TARIFA_DE_GASTO_DE_VENTAS] * 3, nombre="tarifa de gasto de ventas"
            ),
            dias_por_cobrar=horizonte.serie([DIAS_POR_COBRAR] * 3, nombre="dias por cobrar"),
            dias_por_pagar=horizonte.serie([DIAS_POR_PAGAR] * 3, nombre="dias por pagar"),
            tasa_igv=TASA_IGV,
            porcentaje_de_ventas_de_exportacion=PORCENTAJE_DE_VENTAS,
            porcentaje_de_compras_locales=PORCENTAJE_DE_COMPRAS,
        ),
    )


# --- Bloque tributario ---------------------------------------------------------

# Escalas de verdad progresivas, con tramos anchos y tasas redondas para que la
# tasa efectiva se pueda calcular a mano. Las del servicio tienen dieciseis y
# diecisiete tramos; aqui lo que se ejercita es la rama, no la tabla.
ESCALA_PROGRESIVA = EscalaProgresiva(
    tramos=(
        Tramo(0.0, 0.10, 0.02),
        Tramo(0.10, 0.20, 0.04),
        Tramo(0.20, 10.0, 0.10),
    )
)
IEM_PROGRESIVO = EscalaProgresiva(
    tramos=(
        Tramo(0.0, 0.10, 0.01),
        Tramo(0.10, 10.0, 0.03),
    )
)

MAESTROS_PROGRESIVOS = DatosMaestros(
    parametros=PARAMETROS,
    tasas_tributarias=MAESTROS.tasas_tributarias,
    tasas_financieras=MAESTROS.tasas_financieras,
    escala_regalia=ESCALA_PROGRESIVA,
    escala_iem=IEM_PROGRESIVO,
)
"""Los mismos parametros con las dos escalas progresivas.

Van aparte y no sustituyen a `MAESTROS` porque los seis casos anteriores anclan
con cifras calculadas a mano -la participacion de 46 400, la renta de 156 556,5,
el EBITDA de 750 700- que cambiarian con otra escala sin que el cambio fuera
suyo.
"""

SALDO_INICIAL_DE_PERDIDAS = 1_000_000.0
"""Un saldo de apertura mayor que la mitad de la imponible del primer ejercicio.

Es lo que separa las dos ramas del limite del 50 %: con este saldo manda el
limite y no el saldo entero. Ningun otro caso del arnes declara uno, pese a que
`Impuestos!H64` es la unica constante del libro que es un dato.
"""


def caso_del_bloque_tributario() -> Caso:
    """Una mina de margen alto que arrastra perdidas desde antes del horizonte.

    Tres cosas que ningun otro caso ejercita. **La rama progresiva de la regalia
    gana a la minima sobre ventas**, porque con la escala plana al 1 % del resto
    del arnes las dos empatan y manda siempre la minima. **El impuesto especial
    deja de ser cero.** Y **el saldo inicial de perdidas topa contra el limite
    del 50 %**, que es la rama que solo estaba probada llamando a `resolver`.

    Sin capital: lo que se mira aqui es la hoja tributaria, y una depreciacion
    que corre estrecharia el margen sin aportar nada a lo que se verifica.
    """
    horizonte = Horizonte(primer_ano=2027, anos=3)
    unidad = UnidadProductiva(
        nombre="Mina de Margen Alto",
        tipo="mina",
        produccion=ProduccionDeUnidad(
            mineral_tratado=horizonte.serie([1_000.0] * 3, nombre="tratado"),
            mineral_extraido=horizonte.serie([1_000.0] * 3, nombre="extraido"),
            concentrado_producido=horizonte.ceros(),
            metal_refinado_vendido=horizonte.serie([200.0] * 3, nombre="refinado"),
        ),
        costos={"Mina": horizonte.serie([400_000.0] * 3, nombre="mina")},
    )
    return Caso(
        nombre="Sintetico: bloque tributario",
        horizonte=horizonte,
        unidades=(unidad,),
        terminos=TerminosComerciales(
            precio_metal_refinado=horizonte.serie([10_000.0] * 3, nombre="precio"),
            premio_metal_refinado=horizonte.ceros(),
            precio_metal_en_concentrado=horizonte.ceros(),
            factor_metal_pagable=horizonte.ceros(),
        ),
        datos_comunes=DatosComunes(
            gastos_administrativos=horizonte.ceros(),
            saldo_inicial_de_perdidas=SALDO_INICIAL_DE_PERDIDAS,
        ),
    )
