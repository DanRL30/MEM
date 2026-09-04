# Brechas de la hoja `FC NZ`

Auditoria fila a fila de la hoja `FC NZ` contra lo que reproducia `flujos.py` y contra lo que
componia `corrida.calcular`. Repite el metodo de
[brechas-hoja-impuestos.md](brechas-hoja-impuestos.md) y cierra **la ultima hoja de calculo por ano
del libro que quedaba sin leer**.

Fecha de la lectura: 04/09/2026. Las formulas y las cifras estan en el informe de diseccion, en
`00-gestion/03-insumos-minsur/`; aqui van la estructura y el vocabulario.

**Esta hoja no genera plantilla.** Como `Impuestos`, no pide nada al usuario: todas sus filas salen
de las hojas anteriores y de dos celdas de `Control`. Por eso el archivo se llama `brechas-hoja-` y
no `brechas-plantilla-`.

## 1. Las cifras

| Medida | Valor |
|---|---|
| Filas con contenido | 55 |
| Columnas | 43, con 36 de ano desde `H` |
| Formulas | 1 178 |
| Reglas unicas | 22 |
| Filas que la plataforma no exponia | **17 de las 21 de negocio**, mas las cinco de periodo y las cinco del bloque de descuento |
| Anomalias encontradas | 15 |

`FC NZ` era la unica hoja del libro **declarada reproducible con contraste de resultados y sin
lectura de filas**. Las reglas `062` a `064` y la `075` salieron de comparar sus cuatro cierres
contra los del motor; ninguna de leer la hoja. Esta lectura las aporta.

## 2. La forma real de la hoja

Rotulos en la columna `C`, **unidad en la `E`** -`$k`, en las 21 filas de importe- y **columna de
total en la `F`**, que suma `I:AQ` y por tanto excluye el primer ejercicio. Panel congelado en
`H29`, que es lo que deja las banderas y el P&L siempre a la vista.

| Filas | Bloque | Naturaleza |
|---|---|---|
| 6-10 | Banderas de periodo | cinco, y **dos estan muertas** |
| 12 | `Flujo Económico` | el unico titulo de banda de la hoja |
| 14-21 | P&L operativo | ocho conceptos, todos de `Otros` salvo ventas y participaciones |
| 22 | `EBITDA ajustado *` | `SUM(14:21)` |
| 23-26 | Ajustes bajo el EBITDA | capital de trabajo, impuestos, intereses y otros |
| 27 | `Flujo Operativo` | `SUM(22:26)` |
| 28-32 | Inversiones | capex por etapa, estudios, exploraciones y predios |
| 33 | `Flujo Inversiones` | `SUM(28:32)` |
| 35 | `Flujo Económico` | **`27 + 33 - 25`**, no una suma |
| 38-42 | Descuento y resultado | ano, factor, flujo descontado, NPV y TIR |
| 45-49 | Segundo bloque de descuento | **oculto y agrupado**, rebaseado a otro ejercicio |

Filas en blanco: 2, 3, 5, 11, 13, 34, 36, 37, 43, 44. Las 3, 5, 11, 13 y 34 miden 6 pt.

## 3. De donde viene cada fila

Solo dos de las veintiuna filas de importe no salen de otra hoja del libro: los intereses y los
otros del flujo, que vienen de `Supuestos`. El resto es transporte.

| Fila | Rotulo | Origen |
|---|---|---|
| 14 | `Ventas` | `Ventas!27` |
| 15 | `Cash Cost` | `Otros!13` |
| 16 | `Participaciones` | `-Impuestos!53` |
| 17 | `Fletes` | `Otros!26` |
| 18 | `Gasto de Ventas` | `Otros!20` |
| 19 | `Gasto Administrativo` | `-8 x InputsOpex!174`, **con la bandera** |
| 20 | `Gestión Social` | `Otros!29` |
| 21 | `Otros Gastos` | **`Otros!34 - Otros!29`** |
| 23 | `Δ WK` | `Otros!84` |
| 24 | `Impuestos` | `Otros!41`, que es `Pago Impuestos` |
| 25 | `Intereses` | `Supuestos!104` |
| 26 | `Otros` | `Supuestos!107` |
| 28 | `Capex Inicial` | `-Depreciacion!7` |
| 29 | `Capex Sostenimiento` | `-(Depreciacion!11 - Depreciacion!7)` |
| 30 | `Estudios` | `-(InputsOpex!180 + InputsOpex!179)` |
| 31 | `Exploraciones` | `-Supuestos!100` |
| 32 | `Predios` | `Otros!93` |

**La hoja recibe de seis y entrega a cinco.** Cita `Control`, `Ventas`, `Otros`, `Impuestos`,
`InputsOpex`, `InputsProd`, `Depreciacion` y `Supuestos`; y la citan `Control` -que publica su NPV y
su TIR-, `Sensibilidad`, `Depreciacion` -la bandera `Periodo operativo`-, `Otros` -la bandera
`Periodo con gastos`-, `Impuestos` -cinco lineas de gasto- y `FC escenarios`.

## 4. Las tres filas que no dicen lo que su rotulo promete

**La `21`, `Otros Gastos`, se construye restando posiciones.** `Otros!34 - Otros!29` es el total del
bloque de otros gastos menos su primera fila, de modo que recoge la servidumbre, los reguladores con
el fondo de jubilacion, la fila tecleada `Otros` y la regalia de los ejercicios en perdida. **No es
una suma de conceptos**: insertar una fila en `Otros` entre la 29 y la 33 cambia el flujo sin que
nada lo acuse. Es la regla `091`.

**La `20`, `Gestión Social`, lee la celda que `Otros` rotula `Donaciones`.** Las dos son
`InputsOpex!175`, que en su propia hoja se llama `Gestión Social`. **El bloque `InputsOpex!173:182`
no tiene ninguna fila de donaciones**: son diez conceptos y ese no esta. Es la regla `094`, y
arrastra dos correcciones de la plataforma que se detallan en la seccion 6.

**La `35`, `Flujo Económico`, no es una suma.** Es `27 + 33 - 25`: el flujo operativo ya habia
descontado los intereses y esta linea los devuelve, de modo que el resultado no depende de como se
financie el proyecto. Es la regla `095`.

## 5. El NPV tiene dos candados, no uno

La regla `062` registro que el libro **teclea un cero** en el factor de descuento del primer
ejercicio, `H39`, donde el patron daria uno. Esta lectura encuentra el segundo: **`H41` es
`=SUM(I40:AQ40)`**, y arranca en la segunda columna.

Los dos candados son independientes y hacen lo mismo. **Corregir el cero no moveria el NPV**, porque
la fila 41 seguiria ignorando la columna `H`. Es la regla `090`, y es material para la consulta 1
del `CON` Rev. A, emitida el 02/09/2026 y sin respuesta: si Finanzas contesta que la fecha de
valoracion es la que el rotulo dice, hay que tocar dos celdas y no una.

**Y las filas contiguas usan criterios de horizonte opuestos.** La `41` excluye el primer ejercicio
y la `42`, la TIR, lo incluye: `IFERROR(IRR(H35:AQ35),"-")`. La regla `015` registraba esa asimetria
entre `FC NZ` y `FC escenarios`; esta lectura la encuentra **dentro de `FC NZ`**, entre dos filas
adyacentes. Es la regla `093`.

## 6. Brechas contra el motor

**Lo que ya estaba bien.** Los tres escalones del flujo, la participacion de trabajadores dentro del
EBITDA, el signo declarado en el modulo en vez de heredado, y las cuatro lineas de cierre, que
coinciden ejercicio a ejercicio con el libro en los tres casos contrastados -es la regla `075`-.

**Lo que faltaba, y es lo que este trabajo cierra:**

| Brecha | Efecto |
|---|---|
| 17 de las 21 lineas de negocio no salian de la corrida | El flujo no se puede contrastar por fila en N2 |
| Las cinco banderas de periodo no existian como salida | La bandera que sujeta la servidumbre era una comprension anonima |
| Los factores de descuento y el flujo descontado se calculaban y se descartaban | El NPV llegaba sin derivacion |
| `ComponentesOperativos` y `ComponentesDeInversion` se componian y morian en `calcular` | Diecisiete filas colapsadas en tres flotantes por ano |

**Y cuatro diferencias de fidelidad, tres de las cuales cambian cifras.**

1. **La planilla se cobraba dos veces.** `planilla = cash cost x tasa` es una fraccion de un costo
   que la fila `15` ya descuenta entero, y el motor la sumaba ademas a los otros gastos del flujo
   operativo. El libro solo la teclea en `Otros!52`, dentro de la bolsa de egresos, que no vuelve al
   flujo. **Cierra la regla `082`**, abierta desde el 02/09/2026 como sospecha y ahora comprobada con
   la formula delante.
2. **Las donaciones no existen como concepto.** La plataforma las pedia en su plantilla de OPEX y
   las cargaba al flujo junto a la gestion social, de modo que un caso declaraba dos veces el mismo
   concepto. La regla `055` las dedujo del rotulo de `Otros!29` sin leer su formula. Es la regla
   `094`: el rotulo se conserva donde el libro lo escribe -es el que el cliente reconoce- y el
   calculo pasa a ser el del libro.
3. **La regla `081` estaba equivocada y se corrige.** El 04/09/2026 se saco la gestion social de la
   bolsa de egresos diciendo que el libro no la lleva alli. Si la lleva: `Otros!48` se rotula
   `Donaciones` y es `InputsOpex!175`. La bolsa vuelve a llevarla, y la prueba que fijaba la `081`
   pasa a afirmar lo contrario. Es la misma lectura de rotulo que causo la `094`.
4. **El flujo economico dejaba dentro los intereses.** Se corrige por la regla `095`. No mueve
   ninguna cifra publicada: los intereses valen cero en los siete casos del arnes y en el caso 7 del
   libro.

## 7. Lo que no se reproduce, y por que

- **Las filas `7` y `9`.** `Periodo pre-operativo` son treinta y seis ceros tecleados que no lee
  ninguna celda del libro, y `Ano cierre` se calcula comparando la depreciacion contra un umbral
  incrustado en su propia formula y tampoco lo lee nadie. Reproducir la `9` seria implementar una
  constante magica para una fila muerta. Es la regla `092`.
- **La fila `41`, `NPV`.** Es la suma de la fila que tiene encima, y en la plataforma esa suma es su
  columna de total. Emitirla como serie repetiria el mismo numero treinta y seis veces.
- **La fila `42`, `TIR económica`.** No es una serie anual. Viaja con los indicadores, que ademas
  declaran su ausencia con el motivo cuando el caso no la define, por el
  [ADR 0011](../adr/0011-cuando-el-motor-entrega-tir.md).
- **El segundo bloque de descuento, filas `45` a `49`.** El libro lo lleva oculto y agrupado, repite
  los cinco rotulos del visible rebaseados a otro ejercicio y da un NPV casi del doble bajo la misma
  etiqueta. Son dos valoraciones a fechas distintas conviviendo sin que ninguna este rotulada como
  tal: es la regla `063`, abierta, y publicar la segunda seria elegir por Finanzas.
- **El cero del factor de descuento se reproduce desde el 04/09/2026.** El caso declara su ultimo
  ejercicio hundido y esos ejercicios llevan factor cero, con lo que el NPV cierra con brecha 0,00
  contra la fila 41. Lo decide el [ADR 0012](../adr/0012-el-costo-hundido-sale-del-npv.md), y era la
  unica linea del contraste N3 que no cerraba. Queda una discrepancia declarada sobre la **fecha** a
  la que se valora, que es otra cosa y sigue en consulta.

## 8. Lo que queda pendiente de Finanzas

1. **A que fecha se valora el NPV** -reglas `062` y `090`-. Es la consulta 1 del `CON` Rev. A, del
   02/09/2026. La `090` anade que hay que tocar dos celdas y no una.
2. **Cual de las dos valoraciones va al informe** -regla `063`-.
3. **Si el flujo economico del informe es el pre-financiamiento** -regla `095`-. La plataforma se
   alinea al libro; con intereses declarados la diferencia seria visible.
4. **Si `Donaciones` debe seguir existiendo como concepto de negocio** -regla `094`-. El nombre se
   conserva y el calculo se alinea, pero el bloque de gastos del libro no lo tiene.

## 9. Estado

Auditoria cerrada el 04/09/2026. Con ella, **las cinco hojas de calculo por ano del libro tienen su
lectura fila a fila**: `Ventas`, `Otros`, `Impuestos` y `FC NZ`, mas las cuatro plantillas de
entrada. Las seis reglas nuevas, de la `090` a la `095`, estan en
[reglas-no-documentadas.md](reglas-no-documentadas.md); cuatro se implementan citandolas, dos se
consultan y ninguna bloquea el calculo.
