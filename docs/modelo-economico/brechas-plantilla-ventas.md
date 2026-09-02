# Brechas de la plantilla de ventas

Auditoria fila a fila de la hoja `Ventas` contra lo que pedia la plantilla de supuestos, lo que
reconocia `supuestos.py` y lo que calculaba `ventas.py`. Repite el metodo de
[brechas-plantilla-capex.md](brechas-plantilla-capex.md) y cierra la cuarta y ultima plantilla, que
era la unica sin auditar.

Fecha de la lectura: 02/09/2026. Las formulas y las cifras estan en el informe de diseccion, en
`00-gestion/03-insumos-minsur/`; aqui van la estructura y el vocabulario.

## 1. Las cifras

| Medida | Valor |
|---|---|
| Filas con etiqueta en `Ventas` | 72 |
| Filas de dato tecleado | **2** |
| Columnas de ano | 36, de la H a la AQ, mas una de total |
| Formulas de la hoja | 1 614 |
| Reglas unicas | 20 |
| Referencias que recibe desde `Supuestos` | 612 |
| Filas que la plantilla pedia y no llegaban al motor | 8 |

**La hoja es calculo, no captura.** De sus setenta y dos filas con contenido solo dos llevan un
numero escrito a mano: `Ajustes finales` y una rotulada `xxx`. Todo lo demas sale de la produccion
de las unidades y de los terminos comerciales de la hoja `Supuestos`. Es la misma naturaleza del
bloque de la refineria, y por eso el motor la rehace entera.

## 2. La forma real de la hoja

Dos bloques, y el segundo alimenta al primero.

| Filas | Bloque | Que hace |
|---|---|---|
| 7 a 27 | `Ventas Netas` | Las cuatro lineas de venta y su total |
| 29 a 66 | `Resumen Ventas Provisionales` | La liquidacion del concentrado de cobre |
| 70 a 72 | `Volumen Pagable` | Contenido pagable de cada metal |

### 2.1 `Ventas Netas`: dos caminos para el mismo metal, con dos precios

| Fila | Linea | Origen |
|---|---|---|
| 9 | `Volumen Sn` refinado | `InputsProd!106` |
| 10 | `Precio total` | fila 11 mas fila 12 |
| 11, 12 | `Precio Spot Sn`, `Premio Sn` | `Supuestos` |
| 13 | `Venta Sn Refinado` | 9 x 10 |
| 15 | `Volumen Sn` spot | `InputsProd!111` |
| 16 | `Precio total` | fila 17 por fila 18 |
| 17, 18 | `Precio Spot Sn`, `Factor Metal Pagable` | `Supuestos` |
| 19 | `Venta Sn Concentrado` | 15 x 16 |
| 20 | `Venta Sn Total` | 13 mas 19 |
| 22 | `Volumen concentrado` | fila 32 |
| 23 | `Precio total` | `IFERROR(66 / 22, 0)` |
| 24 | `Venta Cu + Ag` | 22 x 23 |
| 25 | `Ajustes finales` | **dato tecleado** |
| 26 | `xxx` | **dato tecleado** |
| 27 | `Venta Total` | 20 mas 24 mas 25 mas 26 |

El mismo estano se vende por dos vias y a dos precios distintos: refinado, al spot **mas** un
premio; y en concentrado, al spot **por** el factor de metal pagable. La segunda via es la del
excedente que la refineria no alcanza a tratar.

### 2.2 `Resumen Ventas Provisionales`: la liquidacion

| Fila | Linea | Origen |
|---|---|---|
| 32 | `Toneladas vendidas` | `InputsProd!46`, el concentrado de cobre de la unidad |
| 33 | `Merma` | `Supuestos!49` |
| 34 | `Toneladas vendidas netas` | 32 por (1 menos 33) |
| 35, 36 | `Precio Cu`, `Precio Ag` | `Supuestos!9` y `!10` |
| 38, 39 | Leyes de Cu y Ag | `InputsProd!47` y `!48` |
| 41, 42 | Deducciones minimas | `Supuestos!51` y `!52` |
| 44, 45 | Factor metal pagable | `Supuestos!54` y `!55` |
| 47, 48 | Ley pagable | `Supuestos!57` y `!58`, **calculadas** |
| 50 | `Maquila` | `Supuestos!60` |
| 52, 53 | Refinacion de Cu y Ag | `Supuestos!62` y `!63`, **calculadas** |
| 55, 56 | Valor pagable por metal | ley pagable x precio x toneladas **vendidas** |
| 57 | `Valor Pagable` | 55 mas 56 |
| 59, 60 | Cargos por metal | (maquila mas refinacion) x toneladas **netas** |
| 61 | `Penalidades` | `Supuestos!66` |
| 62 | `Total Concentrado Cu` | 59 mas 60 mas 61 |
| 64, 65 | Valor neto por metal | pagable menos cargo |
| 66 | `Valor neto` | 64 mas 65, y es el que alimenta la fila 23 |
| 71, 72 | `Volumen Pagable` | toneladas vendidas x ley pagable |

## 3. Las brechas, en cuatro clases

**Clase 1 — filas que la plantilla pedia y el motor no recibia.** Ocho campos se leian y se
descartaban en `aplicar()`: `deduccion_minima_cu`, `deduccion_minima_ag`, `factor_pagable_cu`,
`factor_pagable_ag`, `penalidades_ag`, `costo_de_fundicion`, `gasto_de_ventas_sn_refinado` y
`gasto_de_ventas_conc_cu`. El usuario los llenaba, el caso se leia sin incidencias y el dato no
intervenia: el mismo fallo sin sintoma que ya se cerro en produccion.

**Clase 2 — filas derivadas que se pedian como dato y nadie corroboraba.** `Ley Pagable Cu`,
`Ley Pagable Ag` y `Refinacion Ag` llevaban la marca `calculada` en la plantilla, pero el
corroborador solo rehacia las ocho reglas de produccion.

**Clase 3 — filas del libro que la plataforma no exponia.** `Volumen Pagable` se calculaba dentro
de la liquidacion y no salia a ninguna parte, y las cuatro lineas de venta llegaban ya sumadas en
una sola serie: una diferencia contra el modelo no se podia atribuir ni a un camino ni a una unidad.

**Clase 4 — filas del libro que no se reproducen.** La fila 26, rotulada `xxx`, es una ranura
reservada sin nombre, como la cuarta etapa del capex. No se pide y no se reproduce.

## 4. Lo que la plantilla pide ahora

En la pestana comun, los terminos del contrato, que son del caso:

`Merma` · `Deduccion Minima Cu` y `Ag` · `Factor Metal Pagable Cu` y `Ag` · `Maquila` ·
`Tarifa de Refinacion Cu` (`$/lb`) · `Refinacion Cu` · `Tarifa de Refinacion Ag` (`$/oz`) ·
`Penalidades Cu` y `Ag` · `Ajustes de Venta`.

En la pestana de cada unidad, lo que se deriva de **su** concentrado:

`Ley Pagable Cu` · `Ley Pagable Ag` · `Refinacion Ag`.

La separacion no es de comodidad. La ley pagable sale de la ley del concentrado de una unidad
concreta, y el cargo de refinacion de la plata sale de esa ley pagable: dos minas con distinta ley
de cobre no caben en una fila unica. El libro las declara una sola vez porque hoy solo una unidad
vende concentrado polimetalico. Es la regla de oro de la refineria aplicada a la venta.

## 5. Las tres reglas con que se derivan las filas calculadas

    Ley pagable      = max(0, min(ley - deduccion minima, ley x factor pagable))    regla 023
    Refinacion Cu    = tarifa por libra x 2204,62                                   regla 021
    Refinacion Ag    = ley pagable / 31,1035 x tarifa por onza troy                 regla 022

Las tarifas —dos centavos por libra y sesenta centavos por onza— son **datos** y entran por la
plantilla; las conversiones son fisicas y viven en el motor. El libro las lleva incrustadas en la
formula, que es lo que impide cambiarlas sin editar el modelo.

El `x 100` que el libro escribe en la ley pagable no aparece en el motor: su ley esta en porcentaje
y la ingesta convierte la escala en la frontera, de modo que ley y deduccion llegan en la misma
unidad. **Salvo en la plata**, y ahi la formula no se reproduce: ver la seccion 7.

## 6. Donde se corrige cada brecha

| Brecha | Donde |
|---|---|
| Los ocho campos que se leian y se tiraban | `supuestos.py::aplicar` y `_terminos_del_concentrado` |
| Ley pagable y cargos como calculo | `ventas.ley_pagable`, `cargo_de_refinacion_del_cobre`, `cargo_de_refinacion_de_la_plata` |
| Lo declarado manda y lo que falta se calcula | `corrida._ley_pagable_de` y `corrida._refinacion_de` |
| Corroboracion de las tres filas derivadas | `corroboracion._del_concentrado_de` |
| Volumen pagable y desglose por camino y unidad | `corrida._ventas` y los campos nuevos de `Corrida` |
| Contraste del tercer camino de venta | `tests/fidelidad`, caso `caso_polimetalico` |

## 7. Lo que no se implementa, y por que

- **La ley pagable de la plata.** La formula del libro multiplica por cien una ley que viene en
  onzas troy por tonelada: mezcla dos unidades y el factor correcto seria 31,1035. Ponerlo seria
  corregir el modelo. Es la **regla 045**, consultada. Mientras tanto la fila se carga como dato,
  se usa tal cual y no se corrobora.
- **`costo_de_fundicion`, `gasto_de_ventas_sn_refinado` y `gasto_de_ventas_conc_cu`.** Son cargos
  de tratamiento y gastos de venta, y su destino —costo operativo o deduccion del ingreso— es la
  consulta 6 a Finanzas, emitida el 31/08/2026 y sin respuesta. Es la nota 1 de
  [mapa-n1.md](mapa-n1.md). Se siguen pidiendo y no se cablean.
- **La fila 26 (`xxx`).** Ranura reservada, sin nombre y sin formula.
- **El contraste numerico contra el modelo.** Bloqueado por `R-30` y `R-31`.

## 8. Consultas que abre esta lectura

| # | Consulta |
|---|---|
| 042 | Las filas 25 y 26 son las dos unicas celdas tecleadas de la hoja. Se confirma que `xxx` es ranura reservada |
| 043 | El precio unitario del concentrado se obtiene dividiendo el valor neto entre las toneladas y se vuelve a multiplicar por ellas. El rodeo se cancela |
| 044 | La fila de penalidades toma solo la de plata y la copia sin multiplicarla por el embarque; la de cobre no se referencia |
| 045 | La ley pagable de la plata aplica un factor cien sobre una ley en onzas troy por tonelada |

## 9. Estado

Auditoria cerrada el 02/09/2026. Las cuatro plantillas —produccion, opex, capex y ventas— tienen ya
su lectura fila a fila. Las cuatro consultas de la seccion 8 estan registradas en
[reglas-no-documentadas.md](reglas-no-documentadas.md) y ninguna esta confirmada por Finanzas.
