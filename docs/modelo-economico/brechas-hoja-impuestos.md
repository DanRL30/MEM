# Brechas de la hoja `Impuestos`

Auditoria fila a fila de la hoja `Impuestos` contra lo que reproduce `impuestos.py` y contra lo que
armaba `corrida._resolver_tributos`. Repite el metodo de
[brechas-plantilla-otros.md](brechas-plantilla-otros.md) y cierra la ultima hoja de calculo por ano
del libro.

Fecha de la lectura: 02/09/2026. Las formulas y las cifras estan en el informe de diseccion, en
`00-gestion/03-insumos-minsur/`; aqui van la estructura y el vocabulario.

**Esta hoja no genera plantilla y no la generara.** Es la unica hoja de calculo por ano que no pide
nada al usuario: todas sus filas salen de los bloques anteriores y de cinco tasas de `Control`. Por
eso el archivo se llama `brechas-hoja-` y no `brechas-plantilla-`.

## 1. Las cifras

| Medida | Valor |
|---|---|
| Filas con contenido | 109 |
| Columnas | 43, con 36 de ano desde `H` |
| Formulas | 3 098 |
| Reglas unicas | 21 |
| Constantes numericas tecleadas | 69, de las que **una sola es un dato**: `H64` |
| Errores silenciados (`IFERROR`) | 684 |
| Filas que la plataforma no expone hoy | 36 de las 45 de negocio, mas las 33 de tramo |

## 2. La forma real de la hoja

| Filas | Bloque | Naturaleza |
|---|---|---|
| 8-27 | Regalias e IEM | doce conceptos, utilidad operativa, margen, dos TEA, tres regalias e IEM |
| 30-53 | Renta | once conceptos, utilidad operativa, regalia, exploracion, IEM, imponible, deduccion, fondo y participacion |
| 56-61 | Impuesto a la Renta | imponible, fondo, participacion, utilidad tras participaciones, tasa e impuesto |
| 64-67 | Perdida Tributaria | saldo inicial, perdida del ejercicio, perdida a amortizar, saldo final |
| 69-87 | Tabla Regalias | 16 tramos marginales sobre el margen operativo |
| 89-108 | Tabla IEM | 17 tramos marginales sobre el mismo margen |

Las filas 1 a 6 son cabecera: la 5 trae el ano, que el primer ejercicio toma de `Control!$G$25` y
los siguientes de `FC NZ`.

## 3. Las dos bases, y en que se diferencian de verdad

Los dos bloques se parecen tanto que invitan a tratarlos como uno con una variante. No lo son. Esta
es la correspondencia fila a fila:

| Concepto | Regalias (8-19) | Renta (30-40) | De donde sale |
|---|---|---|---|
| Ventas | 8 `Ventas Totales` | 30 `Ventas Netas` | **la misma celda**, `Ventas!27` |
| Costo de produccion | 9 | 31 | `FC NZ!15` |
| Fletes | 10 | 32 | `FC NZ!17` |
| Gastos de ventas | 11 | 33 | `FC NZ!18` |
| Gastos administrativos | 12 | 34 | `FC NZ!19` |
| Gasto estudios | 13 | 35 | `InputsOpex!179`, **solo el deducible** |
| Depreciacion | 14 **financiera** | 36 **tributaria** | `Depreciacion!1418` y `Depreciacion!126` |
| Gestion social deducible | 15 | 37 | `InputsOpex!182` |
| Otros gastos / ingresos | 16 | 38 | `Otros!49` mas `Otros!50` |
| Osinergmin | 17 | 39 | la fila de ventas por `Supuestos!124` |
| OEFA | 18 | 40 | la fila de ventas por `Supuestos!123` |
| Fondo de jubilacion | 19 | **no aparece** | `=57`, que es el lazo |

**Tres diferencias, no una.** La depreciacion cambia de via, el fondo de jubilacion solo descuenta
en la base de regalias, y la base de renta suma ademas tres conceptos que la otra no tiene: la
regalia mayor (42), los gastos de exploracion (43, de `FC NZ!31`) y el IEM (46).

**`Ventas Totales` y `Ventas Netas` son la misma celda.** Dos etiquetas distintas para
`Ventas!27` en las dos bases. Es una etiqueta que engana, del mismo tipo que la regla `016`, y
conviene no deducir de ella que existe una venta neta que el libro no calcula. Regla `057`.

**Las filas 44 `Ingresos Financieros` y 45 `Gastos Financieros` estan vacias** en las 36 columnas:
sin formula y sin constante. Concuerda con la nota 2 de [mapa-n1.md](mapa-n1.md): son lineas que el
estandar corporativo nombra y que el libro no alimenta. Se declaran y valen cero; omitirlas
desplazaria la numeracion de un bloque que se contrasta por fila.

## 4. Las dos tablas de tramos

Cada tabla lleva el limite del tramo en la columna `D` y su tasa marginal en la `E`, y una fila por
tramo con una formula por ano que calcula **el aporte de ese tramo al margen del ejercicio**:

    IF(margen > limite, (limite - limite anterior) * tasa,
       IF(margen < limite anterior, 0, (margen - limite anterior) * tasa))

La TEA de cada tributo es la suma de esos aportes dividida entre el margen (filas 22 y 26), y el
tributo es la TEA por la utilidad operativa (filas 23 y 27). Esa cancelacion del margen contra si
mismo es lo que hace afin al sistema y lo que permite resolverlo sin iterar; esta explicada en el
encabezado del modulo y en [ADR 0009](../adr/0009-resolucion-de-la-circularidad-tributaria.md).

**El ultimo tramo de cada tabla no tiene limite numerico**: `D87` es el texto `>80%` y `D108` el
texto `>85%`. La comparacion `margen > texto` es siempre falsa en Excel, de modo que la formula cae
en su segunda rama y el tramo se comporta como abierto por arriba. No es un fallo: es como el libro
escribe un tramo sin tope. Regla `058`.

**La tabla de regalias protege cada tramo con `IFERROR` y la de IEM no.** Las dos se comportan igual,
lo que confirma que ahi el `IFERROR` es defensivo y no tapa nada: si tapara algo, la tabla sin el
daria distinto. Es la lectura de 668 de los 684 errores silenciados de la hoja.

Los limites y las tasas de las dos escalas son **dato maestro** que mantiene MINSUR (`R-32`) y
viven en `DatosMaestros`, no en el codigo ni en este documento.

## 5. El lazo, celda a celda

    19 `Fondo de jubilacion minero`  =  57
    57 `Fondo de Jubilacion Minera`  = -51
    51 `Fondo de Jubilacion Minera`  = IF(49 * 50 > 0, 49 * 50, 0)
    49 `Utilidad luego de deduccion` = 47 + 48
    47 `Utilidad Imponible`          = SUM(41:46)

y la fila 20, `Utilidad Operativa`, suma de la 8 a la 19 — la 19 incluida. El fondo de jubilacion
descuenta la misma utilidad operativa que sirve para calcularlo. **Ese es el unico lazo de la
hoja**: la participacion de trabajadores (53) y el impuesto a la renta (61) cuelgan del final y
nadie los vuelve a leer.

Los 16 restantes de los 684 `IFERROR` estan en las filas 21, 22 y 26 y guardan la division entre el
margen y entre las ventas. Cero es el resultado esperado cuando no hay ventas, que es lo que
`_sin_actividad` reproduce.

## 6. Las 69 constantes

Sesenta y ocho son el `50%` del limite de arrastre de perdidas, repetido en las filas 48 y 66 a lo
largo de las 36 columnas. **La unica constante que es un dato es `H64`**, el saldo inicial de
perdidas tributarias del primer ejercicio, que la plataforma ya pide como
`DatosComunes.saldo_inicial_de_perdidas`. De la segunda columna en adelante la fila 64 arrastra el
saldo final del ejercicio anterior.

**Las filas 48 y 66 son la misma regla escrita al reves.** La 48 reparte segun `47*50% <= 64` y la
66 segun `64 > 47*50%`; las dos ramas se cruzan y en el empate dan el mismo numero. El motor calcula
el valor una vez y escribe las dos filas.

**La perdida del ejercicio (65) se mide sobre la fila 56**, que es la utilidad *despues* de la
deduccion, no sobre la 47. Coinciden siempre, porque la deduccion vale cero cuando el ejercicio es
perdida, pero la fila del libro es la 56 y es la que el motor debe escribir.

## 7. Brechas contra el motor

**Lo que ya estaba bien.** La resolucion de la circularidad, las escalas progresivas, el maximo
entre las dos regalias, el limite del 50 %, el arrastre del saldo, las dos vias de depreciacion y
los aportes reguladores como serie del caso. La aritmetica de la hoja esta reproducida.

**Lo que faltaba, y es lo que este trabajo cierra:**

| Brecha | Efecto |
|---|---|
| 36 de las 45 lineas de negocio no salian del motor | La hoja no se puede contrastar por fila en N1 |
| Las 33 filas de aporte por tramo no existian como salida | Una TEA que no cuadre no se localiza en un tramo |
| El bloque de perdida tributaria era una variable local | Sus cuatro filas no se pueden contrastar ni mostrar |
| El armado de las dos bases vivia en `corrida.py` | Doce conceptos colapsados en dos escalares, fuera del modulo del bloque |

**Una brecha de fondo, que no se cierra aqui.** La fila 16 del libro -y su gemela, la 38- suma
`Otros!49` (`Otros Egresos`, tecleada) y `Otros!50` (`Servidumbre`, entera). El motor alimenta esa
misma linea con `DatosComunes.otros_gastos` -que es `Otros!32`-, la planilla y las donaciones. Son
cinco conceptos que no coinciden:

- **`Servidumbre` rebaja la base imponible en el libro** y en la plataforma va a `predios`, al flujo
  de inversiones, sin tocar la base.
- **`Otros Egresos` la rebaja en el libro** y en la plataforma solo entra a la bolsa de egresos.
- **Las donaciones y la planilla la rebajan en la plataforma** y en el libro no llegan a esta hoja:
  viajan por `FC NZ!21`, que ninguna de las dos bases lee.
- `Otros!32` vale cero en las 36 columnas del libro, de modo que la diferencia **no se ve en las
  cifras de este archivo** y solo aparece al leer de donde viene cada fila.

Que un gasto sea deducible o no lo decide la norma tributaria, no el motor, y la deducibilidad de
las donaciones esta limitada por ley. **No se implementa sin la confirmacion de Finanzas**, conforme
a la regla de este registro. Queda como regla `059`, pendiente, y como consulta abierta. Mientras
tanto la base se arma como hoy y el traslado del codigo no mueve ni un decimal.

## 8. Lo que queda pendiente de Finanzas

1. **Que conceptos alimentan la fila 16.** La brecha de la seccion 7. Es la unica que cambia cifras.
2. **Si `Ingresos Financieros` y `Gastos Financieros` entran al alcance.** Hoy el libro las deja
   vacias y el estandar las nombra. Ver la nota 2 de [mapa-n1.md](mapa-n1.md) y `R-32`.
3. **Si el limite del 50 % de arrastre de perdidas es el vigente.** Esta incrustado en las filas 48
   y 66 y no aparece en ningun parametro; el estandar corporativo no lo menciona.
