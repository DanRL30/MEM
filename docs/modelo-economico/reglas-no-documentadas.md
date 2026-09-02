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
| 016 | `InputsProd`, filas 104 a 106 | La fila se rotula `Recuperación Sn NZ + SRP`, pero en la fórmula del refinado San Rafael Potencial usa la recuperación de `SR + B2`. Solo Nazareth usa la segunda | La etiqueta está mal: en `Supuestos` la misma fila se llama `Recuperación Nazareth`. Los grupos reales son Nazareth por un lado y el resto por otro | | | |
| 017 | `InputsProd`, fila 106 | Santo Domingo entra al refinado como `(alimentado − excedente)`: **el recorte por capacidad se le resta entero a esa unidad**, no se prorratea | Puede ser un orden de despacho deliberado —la última unidad en entrar absorbe el recorte— o un arrastre | | | |
| 018 | `InputsProd`, filas 100 y 109 frente a `Supuestos!H120` | La capacidad de 90 000 está escrita dentro de la fórmula aunque `Supuestos` declara `Capacidad Máxima de Pisco` con ese mismo valor. La fórmula no lee esa celda | Dato duplicado en dos sitios que pueden divergir. Refina la regla `002` | | | `produccion.py` |
| 019 | `InputsProd`, fila 111 | La venta spot del excedente vale `excedente × ley`, sin factor de recuperación, pese a llamarse `Producción Sn Refinado`. La fila 106 sí multiplica por la recuperación | O es metal contenido y la etiqueta engaña, o falta la recuperación | | | |
| 020 | `InputsProd`, filas 90 a 93 | El concentrado que San Rafael y B2 entregan a Pisco viene de un libro externo y es el mismo en las 48 bandas, mientras sus bloques de mina de esta hoja calculan su propia producción de concentrado | Dos fuentes para el mismo dato, que el libro no cuadra entre sí | | | |

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

Las veinte del registro son de tipo 2, salvo la 005, la 007, la 010, la 015 y las cinco que salieron
el 01/09/2026 de leer el bloque de Pisco —016 a 020—, que son de tipo 3: se reproducen y se
reportan. La 015 es la única donde el motor **no** reproduce el libro, porque las dos
hojas del libro se contradicen entre sí: sigue a `FC NZ`, que es la hoja del caso. Seis quedaron confirmadas por Finanzas el 01/09/2026; siguen abiertas la 003 (unidades de
medida), la 004 (tramos tributarios) y la 007 (valores guardados sin recalcular).

Ver la bitácora de discrepancias abiertas en `bitacora-discrepancias.md`.
