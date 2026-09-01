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
| 001 | `Depreciacion`, 105 celdas | `ROUND(..., 0)` sobre el saldo depreciable | Redondeo intencional y exclusivo de depreciación | Finanzas | 01/09/2026 | `depreciacion.py` |
| 002 | `InputsProd`, 596 celdas | Tope de 90 000 incrustado en el mineral tratado, con fórmula complementaria que reparte el exceso | Capacidad máxima de planta. **Pasa a ser input del caso**, editable por unidad | Finanzas | 01/09/2026 | `produccion.py` |
| 003 | Todo el libro | Factores `10^3` y `/1000` al cruzar de hoja | Convivencia de US$ y miles de US$ sin declaración de unidades | | | |
| 004 | `Impuestos`, 576 celdas | Tributo por tramos: tasa aplicada al exceso sobre un umbral, con dos ramas y un tercer caso nulo | Regalía minera e impuesto especial por tramos del margen operativo | | | `tributos.py` |
| 005 | `FC escenarios!I43` | Descuento `1/(1+r)^t` con `t` entero desde 0 | Se reproduce el descuento a fin de año. La discrepancia con `DM-STD-PE-27` §5.1 queda reportada | Finanzas | 01/09/2026 | `indicadores.py` |
| 006 | Configuración del libro | Cálculo iterativo activado (`iterate=1`) | Circularidad deliberada. Finanzas delega el criterio en INVA y pide el más fiable y preciso: ver [ADR 0009](../adr/0009-resolucion-de-la-circularidad-tributaria.md) | Finanzas | 01/09/2026 | `tributos.py` |
| 007 | Configuración del libro | `calcOnSave=0` | Los valores guardados pueden no corresponder a las fórmulas guardadas | | | |
| 008 | `InputsOpex`, 5 661 celdas | `IFERROR(x/y*10^3, 0)` | **Cero es el resultado esperado.** Una indeterminación como 0/0 no detiene el cálculo | Finanzas | 01/09/2026 | `cash_cost.py` |
| 009 | `InputsCapex` | Ninguna fórmula propia: 5 394 enlaces externos y el resto valores | El capital entra al modelo ya calculado desde otros libros | | | |

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

La participación de trabajadores se calcula sobre una utilidad que ya descuenta la participación, y
el impuesto a la renta hace lo propio. El libro lo resuelve con el cálculo iterativo de Excel, cuyo
criterio de parada es una configuración de la aplicación, no del modelo.

El motor no puede heredar esa indefinición: necesita un criterio explícito, porque fija el último
decimal de todos los indicadores.

Finanzas delegó la decisión en INVA el 01/09/2026, pidiendo «el más fiable y preciso». La respuesta
está en [ADR 0009](../adr/0009-resolucion-de-la-circularidad-tributaria.md): el sistema es lineal y
tiene solución cerrada, así que no se itera salvo como verificación.

## Clasificación de discrepancias (protocolo del Plan de Trabajo)

1. **Defecto de implementación de INVA** — se corrige en el motor y se vuelve a contrastar.
   No genera cambio de alcance.
2. **Regla no documentada** — se registra aquí, Finanzas confirma su vigencia y se incorpora al
   motor como regla explícita y trazable.
3. **Inconsistencia del modelo de referencia** — se reporta a Finanzas. INVA **no corrige** el
   modelo corporativo; reproduce la lógica vigente y deja constancia del hallazgo.
4. **Precisión numérica** — se evalúa contra la tolerancia acordada y se documenta como aceptable
   sin corrección si queda dentro del umbral.

Las nueve del registro son de tipo 2, salvo la 005 y la 007, que son de tipo 3: se reproducen y se
reportan. Seis quedaron confirmadas por Finanzas el 01/09/2026; siguen abiertas la 003 (unidades de
medida), la 004 (tramos tributarios) y la 007 (valores guardados sin recalcular).

Ver la bitácora de discrepancias abiertas en `bitacora-discrepancias.md`.
