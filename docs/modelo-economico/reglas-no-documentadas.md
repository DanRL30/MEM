# Reglas no documentadas del modelo de referencia

Registro de comportamientos del libro corporativo que no están escritos en ninguna especificación
y que el motor debe reproducir: redondeos, valores incrustados, comportamiento de macros,
tratamientos de excepción.

**Ninguna regla se implementa sin la confirmación de vigencia por parte de Finanzas.**
Conforme a las exclusiones del alcance, INVA reproduce la lógica vigente; no la corrige.

Las nueve primeras salen de la disección del 01/09/2026 sobre
`Modelo Nazareth Abr_26 + Santo Domingo 11.05 (MOD).xlsx`. Las celdas exactas y las fórmulas
completas están en el informe de disección, en `00-gestion/03-insumos-minsur/`; aquí va la regla,
que es lo que el motor necesita.

## Registro

| # | Origen (hoja!celda) | Comportamiento observado | Hipótesis | Confirmada por | Fecha | Implementada en |
|---|---|---|---|---|---|---|
| 001 | `Depreciacion`, filas de reservas (877, 940, 1265), 105 celdas | `ROUND(reservas iniciales - extraido + adiciones, 0)` | Redondeo a tonelada entera del saldo de **reservas**, no del saldo depreciable. **Pendiente de reconfirmar**: ver el detalle | Finanzas, sobre una descripción imprecisa | 01/09/2026 | `produccion.py` |
| 002 | `InputsProd`, 596 celdas | Tope de 90 000 incrustado en el mineral tratado, con fórmula complementaria que reparte el exceso | Capacidad máxima de planta. **Pasa a ser input del caso**, editable por unidad | Finanzas | 01/09/2026 | `produccion.py` |
| 003 | Todo el libro | Factores `10^3` y `/1000` al cruzar de hoja | Convivencia de US$ y miles de US$ sin declaración de unidades | | | |
| 004 | `Impuestos`, 576 celdas | Tributo por tramos: tasa aplicada al exceso sobre un umbral, con dos ramas y un tercer caso nulo | Escalas progresivas de regalía e IEM sobre el margen operativo, derivadas y reproducidas | Derivada del libro | 01/09/2026 | `impuestos.py` |
| 005 | `FC escenarios!I43` | Descuento `1/(1+r)^t` con `t` entero desde 0 | Se reproduce el descuento a fin de año. La discrepancia con `DM-STD-PE-27` §5.1 queda reportada | Finanzas | 01/09/2026 | `indicadores.py` |
| 006 | Configuración del libro | Cálculo iterativo activado (`iterate=1`) | Circularidad deliberada. Finanzas delega el criterio en INVA y pide el más fiable y preciso: ver [ADR 0009](../adr/0009-resolucion-de-la-circularidad-tributaria.md) | Finanzas | 01/09/2026 | `impuestos.py` |
| 007 | Configuración del libro | `calcOnSave=0` | Los valores guardados pueden no corresponder a las fórmulas guardadas | | | |
| 008 | `InputsOpex`, 5 661 celdas | `IFERROR(x/y*10^3, 0)` | **Cero es el resultado esperado.** Una indeterminación como 0/0 no detiene el cálculo | Finanzas | 01/09/2026 | `cash_cost.py` |
| 009 | `InputsCapex` | Ninguna fórmula propia: 5 394 enlaces externos y el resto valores | El capital entra al modelo ya calculado desde otros libros | | | |
| 010 | `Ventas`, filas 61 a 66 | Las penalidades del concentrado se calculan y se suman al total de cargos, pero el valor neto que alimenta la venta no las incluye | Puede ser deliberado —penalidad liquidada aparte— o un arrastre. Se reproduce | | | `ventas.py` |
| 012 | `Depreciacion`, filas 132 y siguientes | `IF(base - acumulado > base * tasa, base * tasa, base - acumulado)` | Depreciación lineal sobre el valor original, con la última cuota ajustada al saldo pendiente | Derivada del libro | 01/09/2026 | `depreciacion.py` |
| 013 | `Depreciacion`, fila 168 | `IF(SUM(produccion hasta el ano) = 0, 0, ...)` | La depreciación no corre en los años previos al primero con producción acumulada | Derivada del libro | 01/09/2026 | `depreciacion.py` |
| 014 | `Otros`, filas 58 y 66 | La variación de IGV se calcula entera y se lleva al flujo multiplicada por cero: `-(credito - credito anterior) * 0` | El IGV no se considera en el capital de trabajo, como anota la hoja oculta `Inputs`. El bloque **se calcula, se informa y llega al flujo multiplicado por cero**: el cero vive en `PESO_DEL_IGV_EN_EL_FLUJO` y es lo unico que cambia el dia que Finanzas lo confirme | | | `capital_trabajo.py` |
| 015 | `FC escenarios`, filas 44 a 46 | El NPV suma desde la primera columna del horizonte y la TIR arranca una columna después | Asimetría entre dos indicadores de la misma serie. En `FC NZ` ambos cubren el mismo rango | | | `indicadores.py` |
| 011 | `Ventas`, filas 55 a 60 | El contenido pagable se valoriza sobre las toneladas vendidas y los cargos se cobran sobre las netas de merma | Asimetría deliberada de la liquidación comercial | | | `ventas.py` |
| 016 | `InputsProd`, filas 104 a 106 | La fila se rotula `Recuperación Sn NZ + SRP`, pero en la fórmula del refinado San Rafael Potencial usa la recuperación de `SR + B2`. Solo Nazareth usa la segunda | La etiqueta está mal: en `Supuestos` la misma fila se llama `Recuperación Nazareth`. **Resuelta el 01/09/2026 sin reproducir el agrupamiento**: la plataforma calcula por componente, ver abajo | Project Manager | 01/09/2026 | `refineria.py` |
| 017 | `InputsProd`, fila 106 | Santo Domingo entra al refinado como `(alimentado − excedente)`: **el recorte por capacidad se le resta entero a esa unidad**, no se prorratea | Puede ser un orden de despacho deliberado —la última unidad en entrar absorbe el recorte— o un arrastre | | | |
| 018 | `InputsProd`, filas 100 y 109 frente a `Supuestos!H120` | La capacidad de 90 000 está escrita dentro de la fórmula aunque `Supuestos` declara `Capacidad Máxima de Pisco` con ese mismo valor. La fórmula no lee esa celda | Dato duplicado en dos sitios que pueden divergir. Refina la regla `002` | | | `produccion.py` |
| 019 | `InputsProd`, fila 111 | La venta spot del excedente vale `excedente × ley`, sin factor de recuperación, pese a llamarse `Producción Sn Refinado`. La fila 106 sí multiplica por la recuperación | O es metal contenido y la etiqueta engaña, o falta la recuperación | | | `refineria.py` |
| 020 | `InputsProd`, filas 90 a 93 | El concentrado que San Rafael y B2 entregan a Pisco viene de un libro externo y es el mismo en las 48 bandas, mientras sus bloques de mina de esta hoja calculan su propia producción de concentrado | Dos fuentes para el mismo dato, que el libro no cuadra entre sí | | | |
| 021 | `Supuestos!H62` | El cargo de refinacion del cobre esta escrito como `0,02 x 2204,62` | Dos centavos de dolar por libra, convertidos a tonelada dentro de la formula. Constante incrustada. **La tarifa pasa a ser dato de la plantilla y la conversion vive en el motor** | | | `ventas.py` |
| 022 | `Supuestos!H63` | El cargo de refinacion de la plata es `ley pagable x 0,6 / 31,1035` | Sesenta centavos por onza troy, tambien incrustado. Ademas **no es un dato: se deriva de la ley pagable**, que a su vez sale de la produccion. Se calcula por unidad y se corrobora | | | `ventas.py` |
| 023 | `Supuestos!H57` y `H58` | La ley pagable es `max(0, min(ley x 100 - deduccion minima, ley x factor pagable))` | Se calcula desde la ley del concentrado, la deduccion minima y el factor pagable. El `x 100` es de la escala del libro y desaparece al convertir en la frontera. **La de plata queda fuera**: ver la regla `045` | | | `ventas.py` |
| 024 | `Supuestos!H123` y `H124` | OEFA va 0,07 %, 0,07 %, 0,06 % y despues constante; OSINERGMIN 0,12 %, 0,11 %, 0,10 % | **Son series por ano y decrecientes, no tasas fijas.** MINSUR confirmo el 01/09/2026 que es deliberado: los supuestos pueden variar los primeros ejercicios porque hay mejor informacion sobre ellos. Los valores del servicio (OEFA 0,10 %, Osinergmin 0,14 %) son la tasa de referencia, y el caso la sobrescribe | MINSUR | 01/09/2026 | `corrida.py` |
| 025 | `Supuestos!H120` | La capacidad maxima de la refineria es un solo valor, no una serie por ano | Refina la regla `002`: el libro la declara una vez y la repite incrustada en las formulas de `InputsProd` | | | `refineria.py` |
| 026 | `InputsOpex`, filas 131, 142, 155 y 166 | `Planilla = total del cash cost de la unidad x Supuestos!H111` | La planilla no es un dato: se deriva del costo. La plataforma la calcula y no la pide | Derivada del libro | 02/09/2026 | `cash_cost.py` |
| 027 | `InputsOpex`, filas 134, 146, 158 y 170 | `Gestion Social Deducible` es una copia de `Gestion Social`, afectada por `x 0,85` en dos escenarios y por nada en el resto | La parte deducible es una fraccion declarada por unidad y por escenario. Sin declarar, el gasto es deducible entero | | | `cash_cost.py` |
| 028 | `InputsOpex`, fila 132, leida por `Depreciacion` | San Rafael y San Rafael Potencial traen una fila `Estudios` que alimenta la depreciacion; Nazareth y Santo Domingo la parten en `Estudios Pre Factibilidad (Gasto)` y `Estudios Factibilidad (Capitalizable)` | Un `Estudios` sin calificar es capitalizable. **La eleccion cambia la base imponible**, no solo el vocabulario. Se hace lo que hace el modelo | Project Manager | 02/09/2026 | `opex.py` |
| 029 | `InputsOpex`, columna de total de siete de los nueve escenarios | La columna `Total` suma desde el segundo ano del bloque y excluye el primero. Dos escenarios si lo incluyen | Arrastre al construir los bloques. La columna es de presentacion y no alimenta el flujo | | | |
| 030 | `InputsOpex`, filas 108 y 119 | La fila rotulada `Reclasif COVID` calcula sobre `Relavera`, y el `Cash Cost Santo Domingo /tmf` de dos escenarios divide por la fila del titulo del bloque en vez de por su total | Referencias arrastradas en filas de presentacion. Ninguna de las dos alimenta el flujo | | | |
| 031 | `InputsCapex`, filas 7 a 11 frente a 15 a 69 | La etapa no se carga: `Cierre Mina` es el codigo `NOD` de todas las unidades, `Capex Inicial` es la unidad en sus primeros anos productivos y el resto es `Sostenimiento` | La clasificacion contable es el unico dato del capital y la etapa sale de ella | Derivada del libro | 02/09/2026 | `capex.py` |
| 032 | `InputsCapex`, fila 10 | La cuarta etapa esta rotulada `xxx`, no tiene formula en ninguna columna de ano y vale cero siempre. `Depreciacion` la arrastra rotulada `Otros` | Ranura reservada y nunca usada, como las ocho del comite de precios | Derivada del libro | 02/09/2026 | `capex.py` |
| 033 | `Depreciacion`, filas 7 a 10 | Cada fila de capex entra a la depreciacion multiplicada por `(1 + Supuestos!H114)`, con rango declarado `-35, +50` y valor cero hoy | Banda de precision del estimado que afecta al capital entero, no solo a la depreciacion | | | `corrida.py` |
| 034 | `Depreciacion`, escudo de cierre | `No Depreciable` entra con tasa 1, es decir se deduce entero en su ano | El nombre engana: no es que no se deprecie, es que no se reparte. Es el escudo del capital de cierre | Project Manager | 02/09/2026 | `depreciacion.py` |
| 035 | `Depreciacion`, filas 781 y siguientes | La via financiera no deprecia lineal todo el capital: la maquinaria si, y las instalaciones, las edificaciones y los equipos de computo se agotan con tasa `MIN(extraido / reservas, 100 %)` sobre un saldo unico | Metodo de unidades de produccion, y solo para tres de los cinco componentes | Derivada del libro | 02/09/2026 | `depreciacion.py` |
| 036 | `Depreciacion` frente a `InputsCapex` | `Equipos de Cómputo` lleva el codigo `MAQ` y se deprecia con la maquinaria en la via tributaria, pero la financiera lo excluye de ella: la fila que agota resta solo la fila de maquinaria y deja el computo dentro de lo que se agota | **La tasa no es una eleccion: es la de su clase.** La exclusion en la via financiera es un arrastre de la formula, que al restar solo la fila de maquinaria trata como de otra clase un componente que lleva su mismo codigo. **La plataforma no la reproduce**: el computo se deprecia como maquinaria en las dos vias, y se informa como componente propio. Pendiente del acta que lo registre como desviacion | Project Manager | 02/09/2026 | `depreciacion.py` |
| 037 | `Depreciacion`, columna de tasas | La tasa declarada para `Estudios` es 0,05 | **Cierra la consulta que abrio la regla `028`**: el estudio capitalizable se deprecia como una edificacion, en las dos vias, y llega por los gastos y no por el capital | Project Manager | 02/09/2026 | `depreciacion.py` |
| 038 | `Depreciacion`, filas de reservas 872, 935, 1121, 1260 y 1399 | Dos unidades leen sus reservas de un libro externo y tres las derivan de la produccion, sumando toda la fila del horizonte. Nazareth suma el mineral **tratado** y las otras dos el **extraido** | Las reservas de una unidad en operacion son dato de su plan de vida de mina; las de un proyecto salen de su propio plan. La plataforma lo resuelve dejando que se declaren: **declararlas las convierte en dato y dejarlas vacias en calculo** | Project Manager | 02/09/2026 | `corrida.py` |
| 039 | `Depreciacion`, fila 941 | La tasa de agotamiento de una de las seis unidades no lleva el tope `MIN(..., 100 %)` que llevan las otras cinco | Omision del libro. Sin el tope, una extraccion mayor que el saldo deprecia mas capital del que queda. **La plataforma aplica el tope en todas las unidades, presentes y futuras**: la evaluacion de un proyecto X, Y o Z usa los mismos conceptos y las mismas reglas que las unidades actuales, y una excepcion que vive en la formula de una unidad concreta no tiene donde alojarse. Pendiente del acta que lo registre como desviacion | Project Manager | 02/09/2026 | `depreciacion.py` |
| 040 | `Supuestos`, filas 69 a 79 | Dos bloques de `Proyeccion SAP`, uno por via, con un valor por unidad en `k$` | Depreciacion ya contabilizada de los activos que existen antes del primer ano del caso. La via tributaria la consume agregada y la financiera por unidad; la plataforma la lleva por unidad en las dos, que es lo que pide `D-04` | Derivada del libro | 02/09/2026 | `depreciacion.py` |
| 041 | `Depreciacion`, filas 786 y 787 frente a la regla `013` | El total de la depreciacion financiera de cada unidad se multiplica por `Ano con produccion`, una bandera de ese ejercicio, mientras la tributaria acumula con `IF(SUM(produccion hasta el ano)=0,...)` | **Las dos vias miran la produccion de forma distinta.** Un ano de parada a mitad de vida no difiere la cuota financiera: la pierde. La tributaria sigue depreciando | Derivada del libro | 02/09/2026 | `depreciacion.py` |
| 042 | `Ventas`, filas 25 y 26 | Las dos unicas celdas tecleadas de la hoja: `Ajustes finales` y una fila rotulada `xxx`. Todo lo demas es formula | El ajuste es un dato del caso y se pide. La segunda es una ranura reservada y sin nombre, como la cuarta etapa del capex: **no se reproduce** | | | `supuestos.py` |
| 043 | `Ventas`, filas 23 y 24 | El precio unitario del concentrado es `IFERROR(valor neto / toneladas, 0)` y la venta lo vuelve a multiplicar por esas toneladas | El rodeo se cancela y el resultado es el valor neto. La unica diferencia observable seria un embarque nulo, y ahi el `IFERROR` devuelve cero, que es lo mismo que dejar el termino fuera | Derivada del libro | 02/09/2026 | `ventas.py` |
| 044 | `Ventas`, fila 61 | La fila de penalidades copia `Supuestos!H66` —la tarifa de la plata, en dolares por tonelada— sin multiplicarla por el embarque, y la de cobre (`Supuestos!H65`) no se referencia en ninguna parte | Arrastre: una tarifa colocada en una columna de totales. Su efecto esta acotado por la regla `010`, que deja las penalidades fuera de la venta. **La plataforma las lleva por metal y multiplicadas por lo embarcado**, que es lo que la tarifa dice cobrar | | | `ventas.py` |
| 045 | `Supuestos!H58`, refina la `023` | La ley pagable de la plata aplica `ley x 100 - deduccion minima` sobre una ley que viene en onzas troy por tonelada, mientras su deduccion va en gramos por tonelada | Mezcla de unidades: el factor entre onzas troy y gramos es 31,1035, no 100. Corregirlo seria corregir el modelo y reproducirlo seria propagar un error dimensional. **La fila se carga como dato, se usa tal cual y no se corrobora** hasta la respuesta | | | |
| 046 | `Otros!61` y `!62` | La tasa de IGV esta escrita dentro de la formula y no se declara en ninguna celda del libro | Constante incrustada, de la familia de las reglas 018, 021 y 022. **Pasa a ser dato de la plantilla de supuestos** | | | `capital_trabajo.py` |
| 047 | `Otros`, filas 64, 65, 66, 71, 78, 87 y 88 | Siete filas llevan constante tecleada en el primer ano y una copia de esa celda en los treinta y cinco restantes | No son series: son un valor unico que rige todo el horizonte. La plantilla les deja **una sola celda**, como ya hace con la capacidad de la refineria (regla 025) y las tasas de depreciacion | Derivada del libro | 02/09/2026 | `supuestos.py` |
| 048 | `Otros!40` | Rotulada `xxx`, tecleada, cero en las 36 columnas de ano | **Tercera ranura reservada** del libro, tras `InputsCapex!10` (regla 032) y `Ventas!26` (regla 042). No se pide y no se reproduce | Derivada del libro | 02/09/2026 | |
| 049 | `Otros`, filas 32, 49, 82 y 83 | Cuatro filas son constante tecleada en las 36 columnas: `Otros`, `Otros Egresos`, `CxC otros` y `CxP otros` | Son dato del caso y no calculo. Cada una llega solo a su bloque; en particular **`Otros Egresos` afecta a la bolsa de egresos —y con ella a las cuentas por pagar y al IGV de compras— y a ninguna linea de caja** | Derivada del libro | 02/09/2026 | `supuestos.py` |
| 050 | `Otros!84` | Las filas 82 y 83 son **saldos** y se suman en la misma formula junto a dos **variaciones**, las filas 73 y 80 | O es un ajuste puntual deliberado o es un arrastre. Se reproduce tal cual, con el signo con que el libro las escribe | | | `capital_trabajo.py` |
| 051 | `Otros!59` frente a la 87 | La base del IGV de ventas es `Ventas x % Ventas de Exportacion`, mientras la fila del bloque se rotula `IGV Ventas Locales` | El rotulo y el uso no concuerdan: la exportacion no esta gravada. Puede ser una fila de devolucion al exportador o un cruce de rotulos. Se reproduce el calculo y se reporta el rotulo | | | `capital_trabajo.py` |
| 052 | `Otros`, filas 76 y 79 frente a 43-55 | `Total Adiciones` es la `Bolsa Egresos` completa: opex, administrativos, fletes, gasto de ventas, donaciones, servidumbre, estudios, planilla, **capex**, exploraciones y otros egresos | La base de las cuentas por pagar no es el costo operativo. La plataforma adopta la base del libro: dejar fuera el capital mueve la variacion por encima de la tolerancia de N1 en el ano de mayor desembolso | Derivada del libro | 02/09/2026 | `corrida.py` |
| 053 | `Otros`, filas 73 y 80 frente a la 90 | La variacion de cada cuenta se decide con `Ano con produccion` y **la fila entera va multiplicada por la bandera del ejercicio** | Tres comportamientos: un ano productivo seguido de otro mueve la diferencia de saldos, el ultimo de una racha suma ademas el saldo entero, y un ano sin produccion no mueve nada. Sin el tercero, una parada intermedia recupera el saldo dos veces | Derivada del libro | 02/09/2026 | `capital_trabajo.py` |
| 054 | `Otros!16` y `!23` | `Gasto de Ventas Sn Refinado LOM` y `Fletes Concentrado LOM` vienen de una hoja `Detalle` de otro libro; 72 formulas de la hoja son enlaces externos | El libro importa las lineas de las unidades en marcha y calcula las de los proyectos con una tarifa por tonelada. No se puede enlazar un libro ajeno y calcularlas cambiaria la cifra de las unidades en marcha: **se piden como dato** | Project Manager | 02/09/2026 | `supuestos.py` |
| 055 | `Otros!30` frente a la 93 | `Servidumbre` esta en el bloque de gastos operativos y `Compra de Predios` en el de flujo de caja: son dos lineas separadas que la plataforma fusionaba en una sola de inversion | **Resuelta por la 059 el 02/09/2026**: la lectura de `Impuestos!16` confirmo que la servidumbre rebaja la base imponible, y las dos lineas se separan. Los predios se quedan en el flujo de inversiones -`Otros!93`- y la servidumbre va a la base, a la bolsa de egresos y al flujo operativo, donde el libro la sujeta a la bandera `Periodo con gastos`. `Donaciones`, del mismo bloque, no existia en el catalogo de OPEX y se agrega | Project Manager | 02/09/2026 | `corrida.py`, `opex.py` |
| 056 | `Otros`, filas 73 y 80 | Un saldo que abre en un ejercicio **sin produccion** no entra al flujo, porque la fila se multiplica por la bandera, y su reduccion posterior si entra | Consecuencia de la regla 053 sobre el capital del primer ejercicio: la deuda que abre el capex antes de producir nunca se registra como origen de caja. Se reproduce y se reporta | | | `capital_trabajo.py` |
| 057 | `Impuestos!8` y `!30` | Las dos filas que abren las bases, rotuladas `Ventas Totales` y `Ventas Netas`, apuntan a la misma celda: `Ventas!27` | Etiqueta que engana, del mismo tipo que la 016. No existe una venta neta que el libro calcule aparte, y deducirla de la etiqueta lleva a inventar una linea | Derivada del libro | 02/09/2026 | `impuestos.py` |
| 058 | `Impuestos!D87` y `!D108` | El limite del ultimo tramo de las dos escalas es un texto, `>80%` y `>85%`, no un numero. La comparacion `margen > texto` es siempre falsa en Excel, de modo que la formula cae en su segunda rama | Es como el libro escribe un tramo abierto por arriba, y funciona. De paso muestra que el `IFERROR` de la tabla de regalias es defensivo: la tabla de IEM no lo lleva y se comporta igual | Derivada del libro | 02/09/2026 | `impuestos.py` |
| 059 | `Impuestos!16` y `!38` | La fila `Otros Gastos / Ingresos` de las dos bases es `-Otros!49-Otros!50`: `Otros Egresos` mas la `Servidumbre` **entera**, no la fraccion del bloque de gastos | **Confirma lo que la 055 temia**: la servidumbre rebaja la base imponible en el libro. Eran cinco conceptos que no coincidian, porque la plataforma alimentaba esa fila con `Otros!32`, la planilla y las donaciones, que el libro no trae a esta hoja. **La plataforma se alinea al modelo**: la fila pasa a ser los otros egresos mas la servidumbre entera, y los otros tres dejan de rebajar la base. Arrastra separar la servidumbre de los predios, que es lo que la 055 dejaba pendiente | Project Manager | 02/09/2026 | `corrida.py`, `impuestos.py` |

## Detalle de las que no caben en una fila

### 002 — El tope de 90 000

Dos fórmulas complementarias, 324 y 272 celdas, sobre la misma suma de cinco términos: una devuelve
el exceso sobre 90 000 y la otra lo descuenta del total. Es un límite de capacidad expresado dentro
de la fórmula, no un dato de entrada.

Importa por dos razones. Reproducirlo mal desplaza toda la línea de mineral tratado, y con ella el
cash cost y las ventas. Y si el límite corresponde a una planta concreta, un proyecto nuevo con otra
capacidad necesita otro número.

**Resuelto el 01/09/2026.** Finanzas confirma que es la capacidad de planta y que el usuario debe
poder cambiarla. Deja de ser una constante del motor y pasa al catálogo como *capacidad máxima de
tratamiento*, un input por unidad productiva y por año. El valor de 90 000 sobrevive únicamente
como el que traen los casos históricos al contrastarse.

### 001 — El redondeo estaba mal ubicado

Al implementar `depreciacion.py` se localizaron las 105 celdas: están en la hoja `Depreciacion`,
pero en su bloque de **reservas** —filas 877, 940 y 1265, etiquetadas `Reservas Finales`— y no en el
cálculo de depreciación. La fórmula redondea a entero el saldo de reservas después de descontar lo
extraído y sumar las adiciones, así que **redondea toneladas, no dólares**, y pertenece a
`produccion.py`.

El registro original decía «`ROUND(..., 0)` sobre el saldo depreciable», y con esa descripción
Finanzas confirmó el 01/09/2026 que el redondeo era intencional y exclusivo de la depreciación. La
confirmación se dio sobre una descripción equivocada, así que **no vale como confirmada**: hay que
volver a preguntar, ahora sobre lo que la fórmula hace de verdad. En el bloque de depreciación no
hay ningún redondeo.

### 015 — El NPV y la TIR no cubren el mismo rango

En la hoja de escenarios, el NPV suma los flujos descontados desde la primera columna del horizonte
y la TIR se calcula sobre la serie que empieza una columna después. Sobre la misma serie, los dos
indicadores describen proyectos distintos: uno incluye un ejercicio que el otro ignora.

En `FC NZ`, la hoja del caso, ambos cubren el mismo rango. La asimetría aparece solo en la hoja de
escenarios, lo que sugiere un arrastre al armarla más que una decisión. El motor calcula ambos
indicadores sobre la misma serie, que es lo que hace `FC NZ`, y la diferencia con la hoja de
escenarios queda reportada.

### 010 — Las penalidades no llegan a la venta

El libro liquida el concentrado en dos totales distintos. Uno, `Total Concentrado Cu`, suma
maquila, refinación **y penalidades**. Otro, `Valor neto`, suma solo el valor pagable menos maquila
y refinación. El que alimenta la línea de venta es el segundo, así que las penalidades se calculan y
no afectan al ingreso.

Puede ser deliberado —una penalidad que se liquida por fuera del contrato principal— o un arrastre
de una versión anterior. El motor reproduce el comportamiento y expone los dos totales por separado,
de modo que la respuesta de Finanzas se implemente cambiando qué total consume el flujo, sin tocar
la liquidación.

### 004 — Los tramos tributarios

La estructura observada aplica una tasa al exceso sobre un umbral cuando la base lo supera, cero
cuando queda por debajo de un segundo umbral, y una tasa distinta en el tramo intermedio. Coincide
con lo que `DM-STD-PE-27` §6.3 describe para la regalía minera y el impuesto especial a la
minería, y es la razón por la que el estándar exige calcular los tributos en términos nominales.

El `IFERROR` que la envuelve devuelve **vacío**, no cero. En Excel ambas cosas se comportan igual en
una suma, pero no en una comparación ni en un promedio. El motor tiene que decidir cuál de las dos
reproduce, y la decisión se documenta.

### 005 — El descuento a fin de año

El factor es `1/(1+Control!$G$14)^t` con la fila de exponentes en 0, 1, 2, 3. El estándar
corporativo pide descontar desde la mitad de cada año para negocios no estacionales, y cita
explícitamente la minería.

La diferencia entre ambas convenciones supera con holgura la tolerancia propuesta para N3, así que
no es un matiz de redondeo. **Manda el modelo**: el motor descuenta a fin de año y la discrepancia
con el estándar queda reportada.

Confirmado por Finanzas el 01/09/2026: se reproduce el descuento a fin de año. La discrepancia con
`DM-STD-PE-27` §5.1 queda registrada como hallazgo, sin corrección.

### 006 — La circularidad

El lazo lo cierra el **fondo de jubilación minera**: es gasto deducible de la utilidad operativa que
sirve de base para calcularlo. La participación de trabajadores y el impuesto a la renta cuelgan del
final de la cadena y no realimentan, contra lo que se supuso al abrir esta regla. El libro resuelve
el ciclo con el cálculo iterativo de Excel, cuyo criterio de parada es configuración de la
aplicación, no del modelo.

El motor no puede heredar esa indefinición: necesita un criterio explícito, porque fija el último
decimal de todos los indicadores.

Finanzas delegó la decisión en INVA el 01/09/2026, pidiendo «el más fiable y preciso». La respuesta
está en [ADR 0009](../adr/0009-resolucion-de-la-circularidad-tributaria.md): el sistema es afín a
trozos y tiene solución cerrada, así que no se itera salvo como verificación. Implementado y
verificado contra un punto fijo independiente en `impuestos.py`.

La afinidad no era evidente. La tasa efectiva de regalía sale de una escala de tramos sobre el
margen —`SUM(tramos) / margen`— y después se multiplica por la utilidad operativa, lo que parece
cuadrático. No lo es: el margen se cancela contra sí mismo y queda `regalía = ventas × C + t ×
utilidad`. Esa cancelación es lo que sostiene la decisión del ADR.

## Clasificación de discrepancias (protocolo del Plan de Trabajo)

1. **Defecto de implementación de INVA** — se corrige en el motor y se vuelve a contrastar.
   No genera cambio de alcance.
2. **Regla no documentada** — se registra aquí, Finanzas confirma su vigencia y se incorpora al
   motor como regla explícita y trazable.
3. **Inconsistencia del modelo de referencia** — se reporta a Finanzas. INVA **no corrige** el
   modelo corporativo; reproduce la lógica vigente y deja constancia del hallazgo.
4. **Precisión numérica** — se evalúa contra la tolerancia acordada y se documenta como aceptable
   sin corrección si queda dentro del umbral.

Las cuarenta y una del registro son de tipo 2, salvo la 005, la 007, la 010, la 015 y nueve de las
que salieron el 01/09/2026 de leer el bloque de Pisco y la hoja de supuestos —016 a 023 y 025—,
que son de tipo 3: se reproducen y se reportan. Las dos que salieron el 02/09/2026 de leer
`InputsOpex` —029 y 030— tambien son de tipo 3, y ninguna de las dos alimenta el flujo: viven en
columnas y filas de presentacion. De las siete que salieron el 02/09/2026 de leer `InputsCapex`, la
031, la 032 y la 033 son de tipo 2 y estan implementadas; la 036 es una
inconsistencia del modelo que se reproduce sin fusionar el componente, y la 037 cierra la consulta
que abrio la 028. La 035, la 038 y
la 040 salieron de leer la hoja de depreciacion el mismo dia y estan implementadas; la 039 es una
omision del libro que la plataforma **no reproduce**, por decision expresa. La 024 nacio como tipo 3 y MINSUR la confirmo el
mismo dia como deliberada, de modo que paso a tipo 2. La 015 es la única donde el motor **no** reproduce el libro, porque las dos
hojas del libro se contradicen entre sí: sigue a `FC NZ`, que es la hoja del caso. Seis quedaron confirmadas por Finanzas el 01/09/2026; siguen abiertas la 003 (unidades de
medida), la 004 (tramos tributarios), la 007 (valores guardados sin recalcular), la 027 (fraccion
deducible de la gestion social), la 033 (el rango del ajuste de capex), la 044 (la penalidad sin
multiplicar), la 045 (la ley pagable de la plata), la 050 (saldos sumados con variaciones), la 051
(el rotulo del IGV de ventas) y la 056 (el saldo que abre antes de producir). Las tres que salieron
el 02/09/2026 de leer la hoja `Impuestos` -la 057, la 058 y la 059- son de tipo 2 y estan
implementadas.

**La 059 cerro tambien la 055**, que llevaba abierta desde la lectura de la hoja `Otros`. Aquella
anoto la sospecha -la servidumbre y los predios son dos lineas que la plataforma fusionaba- y no la
movio porque cambiaba la base imponible. La lectura de `Impuestos!16` mostro que el libro si la
descuenta, y el Project Manager decidio el 02/09/2026 **alinearse al modelo**: es la regla de
fidelidad, y una diferencia con el libro que no cite una desviacion acordada es un fallo, tambien
cuando la diferencia nos parezca la mas prudente. La deducibilidad de las donaciones sigue siendo
materia de la norma tributaria; lo que el motor reproduce es el libro, y el libro no las trae a
esta hoja. La 028 queda contestada por
la 037, y la 028, la 034, la 036 y la 037 se resolvieron el 02/09/2026 por decision del Project
Manager: **se hace lo que hace el libro, sin fusionar los componentes**. Ninguna de las cuatro sigue
consultada.

**Dos reglas dejaron de reproducir el modelo, y las dos por el mismo criterio**: la plataforma
evalua un proyecto que hoy no existe con los mismos conceptos y las mismas reglas que las unidades
actuales, de modo que una excepcion alojada en la formula de una unidad concreta no tiene donde
vivir. Son la 036 -el computo se deprecia como maquinaria tambien en la via financiera- y la 039
-el tope de agotamiento se aplica en todas las unidades-. La 041 salio de revisar si el bloque
quedaba cerrado, y es de tipo 2: la via financiera cierra la puerta ano a ano y no acumulando. Las dos esperan el acta que las registre
como desviaciones acordadas; hasta entonces, la linea que difiera del modelo por su causa se
sustenta en este registro.

**Once reglas mas salieron de leer la hoja `Otros` fila a fila el 02/09/2026**, y estan en
[brechas-plantilla-otros.md](brechas-plantilla-otros.md). Siete son derivables de la formula y se
implementan citandolas —la tasa incrustada, las semillas de primer ano, la ranura reservada, las
cuatro filas de dato, la bolsa de egresos como base de las cuentas por pagar, la bandera de ano con
produccion y las dos filas de otro libro—. Las otras cuatro, la `050`, la `051`, la `055` y la
`056`, se reproducen y se consultan.

**Cuatro reglas mas salieron de leer la hoja `Ventas` fila a fila el 02/09/2026**, y estan en
[brechas-plantilla-ventas.md](brechas-plantilla-ventas.md). La `042` y la `043` son de tipo 2 y
quedan resueltas —una ranura reservada que no se reproduce y un rodeo aritmetico que se cancela—.
La `044` y la `045` son de tipo 3 y siguen consultadas: la primera describe una tarifa copiada a
una columna de totales sin multiplicar, y la segunda, una formula dimensionalmente incorrecta que
**no se reproduce ni se corrige**, de modo que la ley pagable de la plata se carga como dato y no
se corrobora.

## La regla de oro de la refineria: nada se agrupa

El libro agrupa las recuperaciones de la refinería: lleva una `Recuperación Sn
SR + B2` y otra `Recuperación Sn NZ + SRP`, y con ellas calcula un único
`Producción Sn Refinado` para toda la refineria. La plataforma **no reproduce ese
agrupamiento**. Es la excepción decidida por el Project Manager el 01/09/2026, y
tiene dos motivos concretos:

**Un proyecto nuevo no cabe en ningún grupo.** Añadir un proyecto X obligaría a
decidir a cuál de los dos se parece, que es una decisión sin criterio escrito. La
regla `016` muestra además que los grupos del libro ni siquiera coinciden con sus
propias etiquetas: San Rafael Potencial figura en `NZ + SRP` y usa la
recuperación de `SR + B2`.

**Un total agregado no se puede atribuir.** Si el refinado de la refineria difiere
del modelo, con el cálculo agrupado solo se sabe que algo no cuadra. Calculando
componente a componente, la diferencia señala la unidad.

El efecto es medible y no es un matiz: con 600 t al 40 % recuperando 90 % y 400 t
al 30 % recuperando 70 %, el cálculo independiente da 300 tmf y el agrupado sobre
la recuperación media da 288. Está fijado en
`packages/engine/tests/test_refineria.py::TestReglaDeOro`.

Reproducir el agrupamiento sigue siendo posible sin tocar el motor: basta con dar
el mismo valor de recuperación a las unidades de un grupo.

