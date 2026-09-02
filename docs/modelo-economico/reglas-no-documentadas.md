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
| 004 | `Impuestos`, 576 celdas | Tributo por tramos: tasa aplicada al exceso sobre un umbral, con dos ramas y un tercer caso nulo | Escalas progresivas de regalía e IEM sobre el margen operativo, derivadas y reproducidas | Derivada del libro | 01/09/2026 | `tributos.py` |
| 005 | `FC escenarios!I43` | Descuento `1/(1+r)^t` con `t` entero desde 0 | Se reproduce el descuento a fin de año. La discrepancia con `DM-STD-PE-27` §5.1 queda reportada | Finanzas | 01/09/2026 | `indicadores.py` |
| 006 | Configuración del libro | Cálculo iterativo activado (`iterate=1`) | Circularidad deliberada. Finanzas delega el criterio en INVA y pide el más fiable y preciso: ver [ADR 0009](../adr/0009-resolucion-de-la-circularidad-tributaria.md) | Finanzas | 01/09/2026 | `tributos.py` |
| 007 | Configuración del libro | `calcOnSave=0` | Los valores guardados pueden no corresponder a las fórmulas guardadas | | | |
| 008 | `InputsOpex`, 5 661 celdas | `IFERROR(x/y*10^3, 0)` | **Cero es el resultado esperado.** Una indeterminación como 0/0 no detiene el cálculo | Finanzas | 01/09/2026 | `cash_cost.py` |
| 009 | `InputsCapex` | Ninguna fórmula propia: 5 394 enlaces externos y el resto valores | El capital entra al modelo ya calculado desde otros libros | | | |
| 010 | `Ventas`, filas 61 a 66 | Las penalidades del concentrado se calculan y se suman al total de cargos, pero el valor neto que alimenta la venta no las incluye | Puede ser deliberado —penalidad liquidada aparte— o un arrastre. Se reproduce | | | `ventas.py` |
| 012 | `Depreciacion`, filas 132 y siguientes | `IF(base - acumulado > base * tasa, base * tasa, base - acumulado)` | Depreciación lineal sobre el valor original, con la última cuota ajustada al saldo pendiente | Derivada del libro | 01/09/2026 | `depreciacion.py` |
| 013 | `Depreciacion`, fila 168 | `IF(SUM(produccion hasta el ano) = 0, 0, ...)` | La depreciación no corre en los años previos al primero con producción acumulada | Derivada del libro | 01/09/2026 | `depreciacion.py` |
| 014 | `Otros`, filas 58 y 66 | La variación de IGV se calcula entera y se lleva al flujo multiplicada por cero: `-(credito - credito anterior) * 0` | El IGV no se considera en el capital de trabajo, como anota la hoja oculta `Inputs`. El bloque queda calculado y desconectado | | | `capital_trabajo.py` |
| 015 | `FC escenarios`, filas 44 a 46 | El NPV suma desde la primera columna del horizonte y la TIR arranca una columna después | Asimetría entre dos indicadores de la misma serie. En `FC NZ` ambos cubren el mismo rango | | | `indicadores.py` |
| 011 | `Ventas`, filas 55 a 60 | El contenido pagable se valoriza sobre las toneladas vendidas y los cargos se cobran sobre las netas de merma | Asimetría deliberada de la liquidación comercial | | | `ventas.py` |
| 016 | `InputsProd`, filas 104 a 106 | La fila se rotula `Recuperación Sn NZ + SRP`, pero en la fórmula del refinado San Rafael Potencial usa la recuperación de `SR + B2`. Solo Nazareth usa la segunda | La etiqueta está mal: en `Supuestos` la misma fila se llama `Recuperación Nazareth`. **Resuelta el 01/09/2026 sin reproducir el agrupamiento**: la plataforma calcula por componente, ver abajo | Project Manager | 01/09/2026 | `refineria.py` |
| 017 | `InputsProd`, fila 106 | Santo Domingo entra al refinado como `(alimentado − excedente)`: **el recorte por capacidad se le resta entero a esa unidad**, no se prorratea | Puede ser un orden de despacho deliberado —la última unidad en entrar absorbe el recorte— o un arrastre | | | |
| 018 | `InputsProd`, filas 100 y 109 frente a `Supuestos!H120` | La capacidad de 90 000 está escrita dentro de la fórmula aunque `Supuestos` declara `Capacidad Máxima de Pisco` con ese mismo valor. La fórmula no lee esa celda | Dato duplicado en dos sitios que pueden divergir. Refina la regla `002` | | | `produccion.py` |
| 019 | `InputsProd`, fila 111 | La venta spot del excedente vale `excedente × ley`, sin factor de recuperación, pese a llamarse `Producción Sn Refinado`. La fila 106 sí multiplica por la recuperación | O es metal contenido y la etiqueta engaña, o falta la recuperación | | | |
| 020 | `InputsProd`, filas 90 a 93 | El concentrado que San Rafael y B2 entregan a Pisco viene de un libro externo y es el mismo en las 48 bandas, mientras sus bloques de mina de esta hoja calculan su propia producción de concentrado | Dos fuentes para el mismo dato, que el libro no cuadra entre sí | | | |
| 021 | `Supuestos!H62` | El cargo de refinacion del cobre esta escrito como `0,02 x 2204,62` | Dos centavos de dolar por libra, convertidos a tonelada dentro de la formula. Constante incrustada | | | |
| 022 | `Supuestos!H63` | El cargo de refinacion de la plata es `ley pagable x 0,6 / 31,1035` | Sesenta centavos por onza troy, tambien incrustado. Ademas **no es un dato: se deriva de la ley pagable**, que a su vez sale de la produccion | | | |
| 023 | `Supuestos!H57` y `H58` | La ley pagable es `max(0, min(ley x 100 - deduccion minima, ley x factor pagable))` | Se calcula desde la ley del concentrado, la deduccion minima y el factor pagable. La de plata repite la formula del cobre, con un `x 100` que solo tiene sentido sobre un porcentaje mientras la plata va en onzas por tonelada | | | |
| 024 | `Supuestos!H123` y `H124` | OEFA va 0,07 %, 0,07 %, 0,06 % y despues constante; OSINERGMIN 0,12 %, 0,11 %, 0,10 % | **Son series por ano y decrecientes, no tasas fijas.** MINSUR confirmo el 01/09/2026 que es deliberado: los supuestos pueden variar los primeros ejercicios porque hay mejor informacion sobre ellos. Los valores del servicio (OEFA 0,10 %, Osinergmin 0,14 %) son la tasa de referencia, y el caso la sobrescribe | MINSUR | 01/09/2026 | `corrida.py` |
| 025 | `Supuestos!H120` | La capacidad maxima de la refineria es un solo valor, no una serie por ano | Refina la regla `002`: el libro la declara una vez y la repite incrustada en las formulas de `InputsProd` | | | `refineria.py` |
| 026 | `InputsOpex`, filas 131, 142, 155 y 166 | `Planilla = total del cash cost de la unidad x Supuestos!H111` | La planilla no es un dato: se deriva del costo. La plataforma la calcula y no la pide | Derivada del libro | 02/09/2026 | `cash_cost.py` |
| 027 | `InputsOpex`, filas 134, 146, 158 y 170 | `Gestion Social Deducible` es una copia de `Gestion Social`, afectada por `x 0,85` en dos escenarios y por nada en el resto | La parte deducible es una fraccion declarada por unidad y por escenario. Sin declarar, el gasto es deducible entero | | | `cash_cost.py` |
| 028 | `InputsOpex`, fila 132, leida por `Depreciacion` | San Rafael y San Rafael Potencial traen una fila `Estudios` que alimenta la depreciacion; Nazareth y Santo Domingo la parten en `Estudios Pre Factibilidad (Gasto)` y `Estudios Factibilidad (Capitalizable)` | Un `Estudios` sin calificar es capitalizable. **La eleccion cambia la base imponible**, no solo el vocabulario | | | `opex.py` |
| 029 | `InputsOpex`, columna de total de siete de los nueve escenarios | La columna `Total` suma desde el segundo ano del bloque y excluye el primero. Dos escenarios si lo incluyen | Arrastre al construir los bloques. La columna es de presentacion y no alimenta el flujo | | | |
| 030 | `InputsOpex`, filas 108 y 119 | La fila rotulada `Reclasif COVID` calcula sobre `Relavera`, y el `Cash Cost Santo Domingo /tmf` de dos escenarios divide por la fila del titulo del bloque en vez de por su total | Referencias arrastradas en filas de presentacion. Ninguna de las dos alimenta el flujo | | | |
| 031 | `InputsCapex`, filas 7 a 11 frente a 15 a 69 | La etapa no se carga: `Cierre Mina` es el codigo `NOD` de todas las unidades, `Capex Inicial` es la unidad en sus primeros anos productivos y el resto es `Sostenimiento` | La clasificacion contable es el unico dato del capital y la etapa sale de ella | Derivada del libro | 02/09/2026 | `capex.py` |
| 032 | `InputsCapex`, fila 10 | La cuarta etapa esta rotulada `xxx`, no tiene formula en ninguna columna de ano y vale cero siempre. `Depreciacion` la arrastra rotulada `Otros` | Ranura reservada y nunca usada, como las ocho del comite de precios | Derivada del libro | 02/09/2026 | `capex.py` |
| 033 | `Depreciacion`, filas 7 a 10 | Cada fila de capex entra a la depreciacion multiplicada por `(1 + Supuestos!H114)`, con rango declarado `-35, +50` y valor cero hoy | Banda de precision del estimado que afecta al capital entero, no solo a la depreciacion | | | `corrida.py` |
| 034 | `Depreciacion`, escudo de cierre | `No Depreciable` entra con tasa 1, es decir se deduce entero en su ano | El motor lo trata como tasa cero por definicion. **Mueve la base imponible del ano de cierre y no se implementa hasta que Finanzas confirme** | | | |
| 035 | `Depreciacion`, filas 781 y siguientes | La depreciacion financiera no es lineal: la tasa es `MIN(produccion / reservas, 100 %)` | Metodo de unidades de produccion. El motor la calcula lineal con otra tasa | | | |
| 036 | `Depreciacion` frente a `InputsCapex` | `Equipos de Cómputo` se fusiona con maquinaria en la via tributaria, por su codigo, y se excluye de maquinaria en la financiera | El mismo importe con dos naturalezas segun el motor que lo mire | | | |
| 037 | `Depreciacion`, columna de tasas | La tasa declarada para `Estudios` es 0,05 | **Cierra la consulta que abrio la regla `028`**: el estudio capitalizable se deprecia como una edificacion | | | |

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
verificado contra un punto fijo independiente en `tributos.py`.

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

Las treinta y siete del registro son de tipo 2, salvo la 005, la 007, la 010, la 015 y nueve de las
que salieron el 01/09/2026 de leer el bloque de Pisco y la hoja de supuestos —016 a 023 y 025—,
que son de tipo 3: se reproducen y se reportan. Las dos que salieron el 02/09/2026 de leer
`InputsOpex` —029 y 030— tambien son de tipo 3, y ninguna de las dos alimenta el flujo: viven en
columnas y filas de presentacion. De las siete que salieron el 02/09/2026 de leer `InputsCapex`, la
031, la 032 y la 033 son de tipo 2 y estan implementadas; la 034, la 035 y la 036 son
inconsistencias del modelo que se reportan, y la 037 cierra una consulta abierta. La 024 nacio como tipo 3 y MINSUR la confirmo el
mismo dia como deliberada, de modo que paso a tipo 2. La 015 es la única donde el motor **no** reproduce el libro, porque las dos
hojas del libro se contradicen entre sí: sigue a `FC NZ`, que es la hoja del caso. Seis quedaron confirmadas por Finanzas el 01/09/2026; siguen abiertas la 003 (unidades de
medida), la 004 (tramos tributarios), la 007 (valores guardados sin recalcular), la 027 (fraccion
deducible de la gestion social), la 033 (el rango del ajuste de capex) y la 034 (la deduccion entera
de lo no depreciable). La 028 queda contestada por la 037.

Ver la bitácora de discrepancias abiertas en `bitacora-discrepancias.md`.

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

