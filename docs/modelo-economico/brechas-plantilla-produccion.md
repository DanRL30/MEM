# Brechas de la plantilla de produccion frente al modelo de referencia

Auditoria fila a fila de la hoja `InputsProd` contra lo que emite
[generar_plantilla_inputs.py](../../scripts/generar_plantilla_inputs.py) y lo que reconoce
[plantilla.py](../../packages/ingest/src/minsur_ingest/plantilla.py). Es el sustento del rediseno
de la plantilla como formato estandar, capaz de recibir un proyecto que hoy no existe en el libro.

Cifras del cruce, medidas y no estimadas:

| Medida | Valor |
|---|---|
| Filas de concepto en `InputsProd` | 94 |
| Conceptos distintos que emite la plantilla | 19 |
| Conceptos que el lector lleva al motor | 5 |
| Filas del libro que la plantilla no sabe nombrar | 63 |
| Filas con concepto que el motor no consume | 26 |

Las 63 no son 63 conceptos ausentes. La mayoria son fallos de emparejamiento sobre conceptos que
la plantilla ya tiene, y esa distincion cambia el trabajo: unos se cierran con una entrada en la
tabla de sinonimos y otros exigen cambiar el modelo de datos.

## 1. La forma real del libro: `Mina` y `Planta`

Cada unidad de `InputsProd` se describe con dos sub-bloques rotulados en la columna C, al mismo
nivel que el nombre de la unidad:

| Unidad | Fila | `Mina` | `Planta` |
|---|---|---|---|
| San Rafael | 7 | 8 | 11 |
| B2 | 26 | 27 | 30 |
| Nazareth | 38 | 39 | 42 |
| San Rafael Potencial | 49 | 50 | 53 |
| Santo Domingo | 69 | 70 | 73 |
| Pisco | 89 | — | — |
| Venta Sn Spot | 108 | — | — |

`Mina` describe de donde sale el mineral; `Planta`, por que proceso pasa. Ninguna de las dos
aparece en el catalogo ni en el modelo estandar, y son la estructura que la plantilla debe
reproducir para que Finanzas la reconozca al revisarla.

Dos consecuencias inmediatas:

**La relavera es un origen, no una etapa.** B2 tiene su sub-bloque `Mina` con `Mineral extraído` y
`Ley Sn`, exactamente igual que San Rafael: se extrae mineral de un deposito de relaves ya cerrado
y desde ahi sigue la cadena normal. Su planta es de una sola etapa, y la fila que la describe es
`Mineral Tratado Planta B2` colgando de `Planta`. Hoy el generador la modela dos veces mal: como
tipo de unidad hermano de `mina`, y como etapa que emite una fila `Mineral tratado de relaves` que
el libro no tiene.

**Pisco no es un proyecto, es el bloque del complejo.** No tiene sub-bloques porque no extrae ni
trata mineral: recibe concentrado. Sus filas son calculo interno sobre las minas y relaveras que
le entregan.

## 2. Las cuatro clases de brecha

### Clase 1. La ley es posicional, y ninguna tabla de sinonimos la resuelve

El libro repite la etiqueta `Ley Sn`, `Ley de Sn`, `Ley Cu` o `Ley Ag` para cada corriente de
tonelaje. Al canonizar, las cuatro colapsan al mismo concepto `ley` con su metal:

| Etiqueta del libro | Concepto que produce `canonizar` | Metal |
|---|---|---|
| `Ley Sn` | `ley` | Sn |
| `Ley de Sn` | `ley` | Sn |
| `Ley Cu` | `ley` | Cu |
| `Ley Ag` | `ley` | Ag |

Lo que distingue una de otra es **la fila inmediatamente anterior**: cada ley describe el tonelaje
que la precede. En el bloque de San Rafael hay seis pares:

| Tonelaje | Fila | Su ley | Fila |
|---|---|---|---|
| `Mineral extraído` | 9 | `Ley Sn` | 10 |
| `Mineral Tratado en Pre Concentración` | 12 | `Ley de Sn (entrada)` | 13 |
| `Mineral Pre-Concentrado a Concentradora` | 14 | `Ley Sn` | 15 |
| `Mineral Directo a Planta Concentradora` | 16 | `Ley de Sn` | 17 |
| `Mineral Tratado Total en Concentradora` | 18 | `Ley Sn` | 19 |
| `Mineral Tratado Total (Cash Cost)` | 20 | `Ley Sn` | 21 |

La plantilla emite dos leyes por metal, `Ley de cabeza` y `Ley de entrada a preconcentracion`, y
no tiene nombre para las otras cuatro. La solucion no es adivinar la posicion al leer: es que **la
plantilla nombre cada ley por la corriente que describe**, y que la tabla de sinonimos resuelva la
etiqueta del libro por su vecina de arriba cuando se lea un libro al estilo antiguo.

### Clase 2. Fallos de sinonimo sobre conceptos que ya existen

Siete conceptos estan en la plantilla con otro nombre. Se cierran anadiendo entradas a
[sinonimos.py](../../packages/ingest/src/minsur_ingest/sinonimos.py):

| Etiqueta del libro | Normalizada | Concepto de la plantilla |
|---|---|---|
| `Mineral Tratado en Pre Concentración` | `mineral tratado en pre concentracion` | Mineral tratado en preconcentracion |
| `Mineral Pre-Concentrado a Concentradora` | `mineral pre concentrado a concentradora` | Mineral preconcentrado a concentradora |
| `Ley de Sn (entrada)` | `ley de sn entrada` | Ley de entrada a preconcentracion |
| `Ley Sn Concentrado` | `ley sn concentrado` | Ley del concentrado |
| `Producción Concentrado` | `produccion concentrado` | Produccion de concentrado |
| `Concentrado Producido Sn` | `concentrado producido` | Produccion de concentrado |
| `Ley de Sn en Concentrado` | `ley de sn en concentrado` | Ley del concentrado |

Un espacio de mas en `Pre Concentración` y un guion en `Pre-Concentrado` bastan para que la fila se
pierda. Es el modo de fallo contra el que existe la tabla, reaparecido en las filas que nadie
habia cruzado todavia.

### Clase 3. Los alias de unidad corrompen la etiqueta

El libro abrevia las unidades en el bloque de Pisco: `SR`, `SR Potencial`, `NZ`, `SRP`. La funcion
`sin_nombre_de_unidad` solo borra los nombres declarados, de modo que:

- `Concentrado Alimentado B2` empareja, porque `B2` es un nombre declarado.
- `Concentrado Alimentado SR` no empareja, porque `SR` no lo es.

Y hay un caso peor, que no falla sino que **corrompe en silencio**:

```
Recuperación Sn SR + B2   ->   recuperacion sn sr
```

El borrado de `B2` se lleva por delante la mitad de la etiqueta y deja un concepto que no significa
nada. Una unidad debe declarar sus alias junto a su nombre, y el borrado debe exigir que el nombre
quede aislado, no incrustado.

### Clase 4. Conceptos genuinamente ausentes

Ocho grupos de filas no tienen ningun concepto equivalente. Son los que exigen cambiar el modelo de
datos, no la tabla de traduccion:

| Fila | Etiqueta | Que falta |
|---|---|---|
| 90-99 | `Concentrado Alimentado <unidad>` y su ley | Un par por unidad de origen. La plantilla tiene una sola fila generica |
| 103 | `Ley Promedio de Alimentación` | La ley agregada del complejo |
| 104-105 | `Recuperación Sn SR + B2`, `Recuperación Sn NZ + SRP` | **Dos recuperaciones por grupo de origen**, no una sola |
| 106 | `Producción Sn Refinado (Sin Restricción Pisco)` | El refinado antes de aplicar el tope de capacidad |
| 110-111 | `Ley Promedio de Alimentación` y `Producción Sn Refinado` del bloque `Venta Sn Spot` | **El excedente se refina y se vende**, no se descarta |
| 112 | `Check` | La identidad tratado mas excedente igual a alimentado |
| 113-118 | `Año con producción <unidad>` | Bandera derivada de tener valores |
| 120 | `Años Sin Proyecto` | Bandera derivada |

Las dos ultimas son salida calculada, no entrada: `corrida.unidades_activas()` ya las deriva de
`mineral_tratado`, conforme al criterio que fijo Finanzas el 01/09/2026.

## 3. Lo que la plantilla emite y el libro no tiene

Dos conceptos, y por motivos distintos:

- **`Mineral tratado de relaves`.** No existe en el libro. Es consecuencia de modelar la relavera
  como etapa de tratamiento en vez de como origen del mineral. Desaparece con la correccion.
- **`Capacidad maxima de tratamiento`.** Tampoco existe como fila, y esta bien que no exista: el
  libro la llevaba incrustada en la formula, y la regla `002` la convirtio en input editable por
  unidad y ano tras la confirmacion de Finanzas del 01/09/2026.

## 4. Lo que se lee y se tira

Veintiseis filas tienen concepto reconocido y aun asi no llegan al motor, porque
`PRODUCCION_AL_MOTOR` solo mapea cinco campos. `_armar_unidades` las descarta con un `continue`
**sin emitir incidencia**: quien llene esas filas no recibe aviso de que su dato no se uso.

Entre las descartadas estan `Mineral extraído`, `Toneladas finas`, `Recuperación Sn`,
`Mineral Tratado Total en Concentradora`, `Concentrado Alimentado` y `Concentrado Excedente`, es
decir, casi toda la cadena metalurgica.

Es el mismo modo de fallo silencioso de la clase 2, por otra via. La regla debe invertirse: **lo
que la ingesta no sepa consumir se reporta como incidencia**, nunca se descarta.

## 5. La dimension metal se pierde al leer

`canonizar` devuelve el metal y `_Fila` lo guarda, pero `_armar_unidades` acumula por concepto sin
incluirlo en la clave. En una unidad polimetalica como Nazareth, `Concentrado Producido Sn` y
`Concentrado Producido Cu` caen en la misma entrada y **gana la ultima fila de la hoja**.

Es un fallo de perdida de datos sin sintoma: el caso se lee, es valido y calcula, con la produccion
de un metal sobrescrita por la del otro.

## 6. Que unidad es polimetalica no esta escrito en ningun sitio

El catalogo dice que "las unidades polimetalicas repiten ley, recuperacion y produccion por cada
metal" sin nombrar cual lo es. Ningun documento del arbol lo registra, y es un dato que cambia la
plantilla de dos unidades.

En el libro:

- **Nazareth** (filas 38-48) es el bloque con `Concentrado Producido Cu`, `Ley Cu` y `Ley Ag`, y es
  el unico con los tres metales.
- **Santo Domingo** (filas 69-87) es Sn puro, con la cadena completa identica a la de San Rafael.

Dos cosas respaldan la lectura. El bloque de Nazareth **no tiene ley de cabeza, ni recuperacion, ni
toneladas finas**: salta de `Mineral Tratado` a `Concentrado Producido Sn`, que es exactamente lo
que la desviacion `D-02` describe como filas intermedias de calculo de estano ausentes. Y lo que si
es propio de Santo Domingo es el **opex extendido** en `InputsOpex` —`Servicios Mina`, `LT`,
`Peajes / Mantenimiento`, `Agua Potable`, `STA`, `Preconcentrado Blue Sky`—, que ninguna otra unidad
tiene y que es el origen del acuerdo 6 sobre opex extensible.

Ademas, `Ley Ag` cuelga del concentrado de cobre y no de uno propio: **la plata no tiene concentrado
propio, viaja dentro del de cobre**. La plantilla lo declara como `Ag@Cu` y no pide una produccion
de concentrado de plata, que seria un dato inexistente.

Queda como consulta a Finanzas antes de fijarlo en el catalogo.

## 7. Resumen de lo que hay que cambiar

| Brecha | Donde se corrige |
|---|---|
| Sub-bloques `Mina` y `Planta` | Generador |
| Una ley por corriente de tonelaje | Generador, catalogo, motor |
| Relavera como origen y no como etapa | Generador, motor |
| Par de alimentacion por unidad de origen | Generador, motor |
| Recuperacion por grupo de origen | Generador, motor |
| Refinado y venta del excedente | Motor |
| Siete sinonimos y los alias de unidad | `sinonimos.py` |
| Metal en la clave de acumulacion | `plantilla.py` |
| Incidencia ante concepto no consumido | `plantilla.py` |
| Banderas de ano con produccion como salida | Motor |

## 8. Estado

Cerradas el 01/09/2026 con el rediseno de la plantilla de produccion: los sub-bloques `Mina` y
`Planta`, una ley por corriente, la relavera como origen, el par de alimentacion por unidad de
origen, el metal en la clave de acumulacion, la incidencia ante un concepto no reconocido, el origen
y las etapas en la hoja `Caso`, y la pestana por proyecto. Se corrigio tambien el sinonimo que
mandaba `Tratamiento de Relaves B2` —una linea de `InputsOpex`— a un concepto de produccion.

Sigue abierto, y **por depender de una respuesta de Finanzas no se implementa**:

- **Que criterio agrupa las recuperaciones del complejo.** La plantilla pide una por unidad de
  origen, que es mas general y reproduce el libro dando el mismo valor a las de un grupo. El motor
  guarda el dato y todavia no lo usa para calcular el refinado.
- **Si el concentrado excedente se refina y se vende spot**, y con que recuperacion. El bloque
  `Venta Sn Spot` del libro dice que si; el motor calcula el excedente y aun no lo convierte en
  venta.
- **La tolerancia de corroboracion.** `TOLERANCIA_POR_DEFECTO` es 0,5 % y es propuesta de INVA.
- **Que unidad es polimetalica**, segun la seccion 6.

## 9. La plantilla no identifica el caso

Corregido el 01/09/2026 sobre el rediseno, a peticion del Project Manager:

- **El libro de produccion no lleva hoja `Caso`.** El usuario lo sube desde un caso que la
  plataforma ya tiene abierto. Repetir la identificacion en el archivo solo abre la puerta a que
  contradiga a la del caso.
- **Las pestanas se asocian por orden, no por nombre.** La primera es la primera unidad del caso.
  El nombre de la pestana es una pista para quien carga; el nombre final lo elige en un selector,
  que por ahora ofrece `SR`, `B2`, `NZ`, `SRP` y `SD`. Es lo que acordo el avance 02 del
  28/08/2026, y **no incluye Pisco**: el complejo no se carga, se calcula a partir del concentrado
  que le entregan las minas.
- **El horizonte se deduce de la fila de anos.** Nada fija el numero de ejercicios de antemano, de
  modo que un proyecto de vida larga no exige tocar el lector. Una fila con saltos se reporta,
  porque un salto desplaza todas las series a partir de ahi sin dejar rastro en el resultado.
- **`Concentrado entregado al complejo` solo aparece en unidades polimetalicas.** Con un solo metal
  la respuesta es su propio concentrado, y preguntarla seria pedir el mismo dato dos veces.

