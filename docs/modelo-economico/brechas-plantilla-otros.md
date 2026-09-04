# Brechas de la hoja `Otros`

Auditoria fila a fila de la hoja `Otros` contra lo que reproducia `capital_trabajo.py`, lo que
pedian las dos plantillas y lo que consumia `corrida.py`. Repite el metodo de
[brechas-plantilla-ventas.md](brechas-plantilla-ventas.md) y cierra la ultima hoja de calculo por
ano que quedaba sin auditar.

Fecha de la lectura: 02/09/2026. Las formulas y las cifras estan en el informe de diseccion, en
`00-gestion/03-insumos-minsur/`; aqui van la estructura y el vocabulario.

## 1. Las cifras

| Medida | Valor |
|---|---|
| Filas con contenido | 93 |
| Columnas | 45, con 36 de ano |
| Formulas | 2 157 |
| Reglas unicas | 33 |
| Constantes numericas tecleadas | **191** |
| Formulas con enlace a otro libro | 72 |
| Filas que la plataforma no pedia en ninguna plantilla | 12 |

`Otros` era **la unica hoja que el proyecto declaraba reproducible sin publicar su forma**:
[anatomia-del-libro.md](anatomia-del-libro.md) la listaba entre las que se reproducen y no daba ni
filas ni columnas ni reglas. Esta lectura las aporta.

## 2. La forma real de la hoja

| Filas | Bloque | Naturaleza |
|---|---|---|
| 6-13 | Cash Cost por unidad | todo desde `InputsOpex` |
| 15-20 | Gasto de Ventas | la fila 16 viene de otro libro; 17-19 se calculan |
| 22-26 | Fletes | la fila 23 viene de otro libro; 24-25 se calculan |
| 28-34 | Otros Gastos/Ingresos | donaciones, servidumbre, reguladores, regalias y **32, tecleada** |
| 36-41 | Impuestos | desde la hoja `Impuestos`, mas **40 `xxx`, tecleada y siempre cero** |
| 43-55 | Compras / `Bolsa Egresos` | once conceptos, mas **49 `Otros Egresos`, tecleada** |
| 57-66 | IGV | bases, tasa incrustada, credito, pago y la variacion que se anula |
| 68-73 | Cuentas por Cobrar | ventas, **dias tecleados**, saldo y variacion |
| 75-80 | Cuentas por Pagar | `Bolsa Egresos`, **dias tecleados**, saldo y variacion |
| 82-84 | Otras cuentas y total | **82 y 83 tecleadas**; 84 es la variacion que va al flujo |
| 86-88 | Tipo de Compra/Venta | **dos porcentajes tecleados** |
| 90 | `Ano con produccion` | desde `InputsProd` |
| 92-93 | Otros Flujo de Caja | compra de predios, desde `InputsOpex` |

## 3. Las 191 constantes, y donde va cada una

**Cuatro filas de dato, con un valor por cada uno de los 36 anos:**

| Fila | Etiqueta | Destino |
|---|---|---|
| 32 | `Otros` | `DatosComunes.otros_gastos`, que ya pide la hoja `Caso` |
| 49 | `Otros Egresos` | `DatosComunes.otros_egresos`, fila nueva de supuestos |
| 82 | `CxC otros` | `DatosComunes.otras_cuentas_por_cobrar`, fila nueva |
| 83 | `CxP otros` | `DatosComunes.otras_cuentas_por_pagar`, fila nueva |

Mas la **fila 40, `xxx`**: tecleada, cero en las 36 columnas y sin nombre. Es la tercera ranura
reservada del libro, tras `InputsCapex!10` (regla 032) y `Ventas!26` (regla 042). No se pide.

**Siete semillas del primer ano, que las formulas copian hacia la derecha** — no son series, son un
valor unico que rige el horizonte, y la plantilla les deja una sola celda:

| Fila | Etiqueta | Destino |
|---|---|---|
| 64, 65, 66 | arranque del bloque de IGV | resultado del calculo, no se piden |
| 71 | `Dias` de cuentas por cobrar | `Dias de Cuentas por Cobrar` |
| 78 | `Dias` de cuentas por pagar | `Dias de Cuentas por Pagar` |
| 87 | `% Ventas de Exportacion` | `Porcentaje de Ventas de Exportacion` |
| 88 | `% Compras locales` | `Porcentaje de Compras Locales` |

Mas cuatro celdas de columna de total. **Y una constante que no es celda**: la tasa de IGV vive
dentro de las formulas de las filas 61 y 62 y no se declara en ninguna parte del libro. Es la
regla 046, y pasa a ser la fila `Tasa de IGV`.

## 4. Las brechas, en cuatro clases

**Clase 1 — filas del libro que ninguna plantilla pedia.** Las diez de la seccion 3, mas las dos
de enlace externo (16 y 23) y la fila `Donaciones` (29), que no existia en el catalogo de OPEX.

**Clase 2 — funcionalidad construida y sin camino de datos.** `igv()` y `credito_y_pago_de_igv()`
existian, estaban probadas y **no las llamaba nadie**: la regla 014 se cumplia por omision y no por
reproducir el cero del libro. El interruptor `Control!$G$21` tenia campo, motor y prueba, y la
unica fila que podia escribirlo estaba mal rotulada —hablaba del IGV cuando gobierna las cuentas
comerciales— y ademas se leia como numero, de modo que llenarla producia una incidencia.
`DatosMaestros.tasa_igv` llevaba la tasa y no tenia un solo lector.

**Clase 3 — filas del libro que la plataforma calculaba y no exponia.** Los saldos de las dos
cuentas (72 y 79) y la bolsa de egresos (55) vivian dentro del calculo y no salian a ninguna parte.

**Clase 4 — diferencias de fidelidad.** Tres, y las tres cambian cifras:

- **La base de las cuentas por pagar.** El motor usaba `cash cost + administrativos + fletes +
  gasto de ventas` y el libro usa su `Bolsa Egresos`, que suma ademas donaciones, servidumbre,
  estudios, planilla, **capex**, exploraciones y otros egresos. Con el saldo en `base x dias / 360`,
  omitir el capital del primer ejercicio mueve la variacion muy por encima de la tolerancia de N1.
- **La bandera de liquidacion.** Era `ventas != 0` y el libro usa su fila 90, `Ano con produccion`.
- **La variacion en un ano sin produccion.** El libro multiplica la fila entera por la bandera del
  ejercicio, de modo que una parada no mueve la cuenta. Sin eso, una parada intermedia recupera el
  saldo dos veces y el ciclo no cierra.

**Los dias eran un solo numero duplicado.** La hoja `Caso` pedia `Dias de working capital` y la
ingesta llenaba con el las dos cuentas; el libro las lleva en dos filas distintas.

## 5. Donde se corrige cada brecha

| Brecha | Donde |
|---|---|
| Las diez filas nuevas y su volcado | `supuestos.py`, `FILAS_DE_SUPUESTOS` y `aplicar` |
| `Donaciones` | `cash_cost.py`, `opex.py` y `_gastos` de `corrida.py` |
| Interruptor, dias y rotulo | `generar_plantilla_inputs.py` y `plantilla.py` |
| Bloque de IGV cableado | `capital_trabajo.bloque_de_igv` y `corrida.calcular` |
| Bolsa de egresos | `corrida._bolsa_de_egresos` |
| Bandera y ano sin produccion | `capital_trabajo.variacion_de_cuenta` y `corrida._capital_de_trabajo` |
| Saldos y bloque expuestos | `Corrida.bolsa_de_egresos`, `.cuentas_por_cobrar`, `.cuentas_por_pagar`, `.igv` |
| Contraste N1 | `tests/fidelidad`, caso `caso_de_capital_de_trabajo` |

## 6. Lo que no se implementa, y por que

- **El IGV no llega al flujo.** Se calcula entero y se multiplica por cero, que es lo que hace el
  libro. El cero es `PESO_DEL_IGV_EN_EL_FLUJO` y esta en un solo sitio: el dia que Finanzas
  confirme la regla 014, es esa linea la que cambia.
- **Las tres lineas de gasto de ventas y las dos de fletes no se separan.** Su clasificacion entre
  costo operativo y deduccion del ingreso es la consulta 6 a Finanzas, emitida el 31/08/2026 y sin
  respuesta: es la nota 1 de [mapa-n1.md](mapa-n1.md).
- **La servidumbre si se movio**, y esta seccion decia lo contrario. La regla 055 anotaba la
  sospecha y no la tocaba porque cambiaba la base imponible; la lectura de `Impuestos!16` el mismo
  02/09/2026 mostro que el libro si la descuenta, y la regla 059 la cerro alineandose al modelo.
- **La fila 40 (`xxx`) y la 58 no se reproducen**: la primera es la tercera ranura reservada del
  libro -regla 048- y la segunda repite bajo el rotulo `IGV Ventas Locales` la variacion que la
  misma banda trae nueve filas mas abajo, que es la regla 085.
- **Los costos hundidos siguen sin implementarse.** Estan declarados en cuatro documentos y no
  existen en el codigo; no son de esta hoja. Lo que si cambia es que ahora, si alguien los llena,
  la ingesta lo reporta en vez de descartarlos en silencio.

## 7. Consultas que abre esta lectura

| # | Consulta |
|---|---|
| 050 | La fila 84 suma **saldos** (82 y 83) junto a **variaciones** (73 y 80) |
| 051 | La base del IGV de ventas es `Ventas x % de exportacion` mientras la fila se rotula `IGV Ventas Locales` |
| 055 | `Servidumbre` y `Compra de Predios` son dos lineas del libro que la plataforma fusiona en una de inversion |
| 056 | Un saldo que abre en un ejercicio sin produccion no entra al flujo, pero su reduccion posterior si |

## 8. Estado

Auditoria cerrada el 02/09/2026. Con ella, las cuatro plantillas y las dos hojas de calculo por ano
que alimentan el flujo —`Ventas` y `Otros`— tienen ya su lectura fila a fila. Las once reglas
nuevas, de la `046` a la `056`, estan en
[reglas-no-documentadas.md](reglas-no-documentadas.md); cuatro siguen consultadas y ninguna bloquea
el calculo.

## 9. La hoja pasa a mostrarse entera

El 04/09/2026 la pestana `Otros` recibio la forma del libro: trece grupos en el orden de la hoja, en
miles y no en dolares, con el signo de caja en las bandas 6 a 41 y el positivo en la bolsa de
egresos. Hasta entonces emitia doce series planas en dos secciones, de las cuales seis salian por
reflexion con la etiqueta que daba el nombre del campo.

Dos defectos de presentacion se cerraron con ello. Los tres saldos -las dos cuentas y el credito
acumulado- se acumulaban en la columna de total, que sumaba treinta y seis aperturas. Y
`Otros!66`, la unica linea de la banda de IGV que llega al flujo, no se emitia: es una propiedad del
bloque del motor y la reflexion solo ve campos.

Siete reglas mas, de la `080` a la `086`. La `081` es la unica que cambia el motor: la bolsa de
egresos sumaba doce conceptos donde el libro suma once, con la gestion social de mas. El Project
Manager decidio alinearse al modelo, y como ningun caso del arnes declaraba ese gasto, el cambio
entra con una prueba que corre el mismo caso con y sin el.
