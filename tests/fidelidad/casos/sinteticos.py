"""Casos sintéticos del contraste, con la forma de los tres arquetipos.

No contienen datos de MINSUR. Son casos inventados con cifras redondas,
elegidas para que la aritmética se pueda seguir a mano: es lo que permite que
el contraste sea una comprobación y no un registro de lo que el motor devolvió
la primera vez.

Los tres reproducen la **forma** de los arquetipos del libro, que es lo que
importa para el contraste estructural:

    unidad simple       una mina que vende metal refinado
    refinería            minas que alimentan una fundicion con tope de capacidad
    dos proyectos       una operacion en marcha y un proyecto que entra tarde

Los casos certificados con datos reales son otra cosa: viven en el tenant de
MINSUR, se referencian por manifiesto en `fixtures/certificados/` y sus pruebas
se marcan `tenant_minsur`.
"""

from __future__ import annotations

from minsur_engine.capex import CapitalDeUnidad
from minsur_engine.caso import (
    Caso,
    DatosComunes,
    DatosMaestros,
    ProduccionDeUnidad,
    TerminosComerciales,
    UnidadProductiva,
)
from minsur_engine.depreciacion import TasasDeDepreciacion
from minsur_engine.horizonte import Horizonte
from minsur_engine.parametros import ParametrosCorporativos
from minsur_engine.tributos import EscalaProgresiva, Tramo

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
    capital = CapitalDeUnidad(
        unidad="Mina Unica",
        por_etapa={"inicial": horizonte.serie([1_000_000.0, 0.0, 0.0], nombre="inicial")},
        por_naturaleza={
            "maquinaria": horizonte.serie([1_000_000.0, 0.0, 0.0], nombre="maquinaria")
        },
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
    """Dos minas que alimentan una fundición cuyo tope acota el tratamiento.

    Es el arquetipo de operación consolidada: el cuello de botella está en la
    fundición y el concentrado que no cabe queda como excedente.
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

    fundicion = UnidadProductiva(
        nombre="Fundicion",
        tipo="fundicion",
        produccion=ProduccionDeUnidad(
            mineral_tratado=horizonte.serie([100.0] * 4, nombre="fundicion/tratado"),
            concentrado_producido=horizonte.ceros(),
            capacidad_de_tratamiento=horizonte.serie([1_500.0] * 4, nombre="capacidad"),
        ),
        costos={"Fundicion": horizonte.serie([50_000.0] * 4, nombre="fundicion")},
    )

    return Caso(
        nombre="Sintetico: refinería con fundicion",
        horizonte=horizonte,
        unidades=(
            mina("Mina Norte", [800.0, 900.0, 1_000.0, 1_000.0]),
            mina("Mina Sur", [400.0, 500.0, 600.0, 700.0]),
            fundicion,
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
