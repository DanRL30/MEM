# Modelo estandar de evaluacion

El modelo de dominio independiente del proyecto: que entidades tiene una evaluacion, que datos las
describen y como se declara un proyecto que hoy no existe. Es la especificacion que hace que la
plataforma sirva para el proyecto X, Y o Z sin tocar codigo.

Se apoya en dos documentos y no los repite: la
[anatomia del libro](anatomia-del-libro.md) explica como esta construido el modelo corporativo, y
el [catalogo de inputs](catalogo-inputs.md) enumera los conceptos y su forma.

---

## 1. El problema que resuelve

El libro corporativo evalua nueve casos con nombre. Puede evaluar hasta cuarenta y ocho porque
alguien preparo cuarenta y ocho bandas de treinta y ocho columnas y un `CHOOSE` que elige entre
ellas. Un proyecto nuevo es una banda mas: llenarla a mano en cuatro hojas, comprobar que las 342
reglas la referencian igual que a las demas y confiar en que nadie desplazo una columna.

Cuando se acaben las bandas, se acaba el modelo.

**La plataforma sustituye ese mecanismo por un caso con su propio conjunto de datos.** No hay
limite de casos, no hay bandas, y anadir un proyecto no toca la logica de calculo. La tesis del
documento cabe en una linea:

> Donde el libro precablea 48 casos en 1 870 columnas, la plataforma tiene un caso por proyecto con
> su terna de versiones.

## 2. Entidades

```
Caso
  identificacion         nombre, categoria, autor, fecha
  Horizonte              primer ano, numero de anos, ano de valuacion
  EscenarioDePrecios     juego de precios por metal y ano (base, alto, bajo)
  UnidadProductiva [1..n]
      tipo               mina, refineria, deposito
      origen             yacimiento, relave
      etapas             preconcentracion, concentradora
      entrega_a          unidad receptora, o vacio si vende directo
      metales [1..n]     Sn, Cu, Ag, con su rol
      Produccion         series por ano
      CostoOperativo     series por ano, con conceptos base y adicionales
      Capital            series por ano, con doble clasificacion
      Depreciacion       por naturaleza contable, calculada por unidad
  DatosComunes           working capital, perdidas tributarias, costos hundidos,
                         inversion social, gastos administrativos, otros gastos
```

Los tipos son dos, no cinco. **La preconcentracion y la concentradora son etapas de la planta de una
mina, no unidades**, y **la relavera es el origen de su mineral**: en el libro B2 tiene su sub-bloque
`Mina` con mineral extraido y ley igual que San Rafael, porque se extrae de un deposito de relaves ya
cerrado y desde ahi sigue la cadena normal. **Una relavera de deposito si es una unidad**, y de otra
clase: recibe relave, no extrae nada, y de ella solo hay capital y depreciacion. La refineria si es
una unidad, y hasta el 01/09/2026
faltaba en esta lista.

Los roles de metal salen del libro y no se declaran libres: **Sn** se refina y se vende con premio, y
tambien se vende en concentrado; **Cu** es el concentrado comercial con su maquila y su merma; **Ag**
es subproducto pagable **dentro del concentrado de Cu**, y no tiene concentrado propio. La plantilla
lo declara como `Ag@Cu`.

Fuera del caso, y por eso no aparece dentro de la caja:

- **Parametros maestros.** Tasa de descuento, participacion de trabajadores, impuesto a la renta,
  regalia, Osinergmin, OEFA y fondo de jubilacion minera. En el libro viven en `Control`; en la
  plataforma son dato maestro versionado que mantiene MINSUR (`R-32`). Una corrida registra que
  version uso, nunca "la vigente".
- **Version del motor** y **version de los inputs del caso**. Con la de datos maestros forman la
  terna que identifica una corrida, ya implementada en
  [versionado.py](../../packages/domain/src/minsur_domain/versionado.py).

## 3. Como se declara el proyecto X

1. Se crea un caso y se elige su categoria.
2. Se declaran sus unidades productivas: cuantas, de que tipo y con que metales. Aqui se decide
   toda la forma del caso, porque el bloque de conceptos de cada unidad es fijo.
3. Se carga la plantilla de inputs, que la plataforma genera **ya adaptada a esas unidades**.
4. Se elige la version de datos maestros y el escenario de precios.
5. Se calcula. La corrida queda con su terna de versiones y su bitacora.

Ningun paso toca el motor. Un proyecto con una sola mina y un metal usa las mismas 342 reglas que
uno con cuatro unidades y tres metales; lo que cambia es cuantas veces se instancia el bloque.

## 4. Lo estructural, lo particular y lo opcional

La [matriz de variabilidad](catalogo-inputs.md#5-matriz-de-variabilidad) del catalogo decide donde
vive cada cosa, y de ella salen tres reglas de diseno:

**Lo estructural no se pregunta.** El bloque de produccion, la doble clasificacion del capital y el
bloque contable de la depreciacion son identicos en los tres arquetipos. Van en el motor. Si un
proyecto futuro necesitara otro bloque, eso es un cambio del modelo corporativo, no una opcion de
configuracion.

**Lo particular se carga.** Series de produccion, costos, capital, precios y horizonte. Van en la
plantilla, una fila por concepto y una columna por ano.

**Lo opcional se declara.** Una unidad sin preconcentracion no muestra esas filas; un proyecto
monometalico no pregunta por leyes de cobre. La plantilla se genera a partir de las unidades
declaradas, de modo que el usuario nunca ve un campo que no aplica.

## 5. La procedencia es un atributo del dato, no del concepto

El mismo concepto aparece cargado a mano en un caso y derivado en otro, segun de donde viniera la
informacion cuando se armo el caso. Reproducir esa ambiguedad duplicaria el catalogo.

Cada dato de un caso lleva su procedencia declarada:

| Procedencia | Que significa |
|---|---|
| `CARGADO` | El usuario lo escribio en la plantilla |
| `DERIVADO` | La plataforma lo calculo desde otros datos del mismo caso |
| `HEREDADO` | Viene del LOM o de otra fuente que el usuario adjunta |

La procedencia no cambia el calculo: cambia la trazabilidad y lo que el contraste N0 verifica. Es
tambien donde encaja el acuerdo 9 de la minuta del 27/08/2026, que pide reservas editables en
proyectos LOM y calculadas en greenfield.

## 6. La participacion de una unidad se deriva de sus datos

Consultado como decide un caso que proyectos entran, Finanzas respondio el 01/09/2026 que se lee de
los propios inputs: **si una unidad tiene valores en ciertos anos, es que entra en el analisis de
ese caso y en esos anos**. No hay interruptor que la active.

Medido sobre las bandas de los nueve casos con nombre, el criterio se sostiene sin ambiguedad. El
indice es el desplazamiento del ano dentro del horizonte, y entre parentesis van los anos con dato:

| Caso | San Rafael | B2 | Nazareth | SR Potencial | Santo Domingo | Pisco |
|---|---|---|---|---|---|---|
| Sin Proyecto | 0-36 (11) | 0-36 (5) | **no entra** | 8-36 (11) | **no entra** | 0-36 (11) |
| Nazareth 2032 | 0-36 (11) | 0-36 (5) | 6-36 (12) | 8-36 (11) | no entra | 0-36 (11) |
| Nazareth 2038 | 0-36 (11) | 0-36 (5) | **12**-36 (12) | 8-36 (11) | no entra | 0-36 (11) |
| Nz 2032R + Santo Domingo | 0-36 (11) | 0-36 (5) | 6-36 (12) | 8-36 (11) | 16-36 (10) | 0-36 (11) |
| Nz 2038R + Santo Domingo | 0-36 (11) | 0-36 (5) | 12-36 (12) | 8-36 (11) | 4-36 (10) | 0-36 (11) |
| 2032 + SD sin Nz | 0-36 (11) | 0-36 (5) | no entra | 8-36 (11) | 16-36 (10) | 0-36 (11) |
| 2038 + SD sin Nz | 0-36 (11) | 0-36 (5) | no entra | 8-36 (11) | 4-36 (10) | 0-36 (11) |

Se lee sola. San Rafael, B2, San Rafael Potencial y Pisco son la operacion base y estan en los nueve
casos. Nazareth entra en seis y su ano de arranque separa las variantes 2032 de las 2038, con los
seis anos de diferencia que anuncia el nombre. Santo Domingo entra en los cuatro casos que lo citan.

**Consecuencia de diseno.** La plantilla no lleva un campo de unidad activa ni un ano de entrada:
seria un dato redundante que puede contradecir a las series. El motor deriva la ventana de
participacion de cada unidad de sus propios datos, y las filas del libro que hoy marcan "ano con
produccion" pasan a ser salida calculada, no entrada.

**Hallazgo para reportar, no para corregir.** Santo Domingo arranca en el desplazamiento 16 en los
casos 2032 y en el 4 en los casos 2038: entra doce anos antes en los escenarios mas largos. Puede
ser deliberado y puede ser un arrastre al armar las bandas. Se reporta a Finanzas y el motor
reproduce lo que diga el dato.

## 7. Correspondencia con el motor

Cada entidad de este documento tiene un modulo, y cada modulo una linea del contraste N1. La tabla
completa esta en [mapa-n1.md](mapa-n1.md); aqui va la correspondencia de arriba hacia abajo:

| Entidad | Modulo | Nota |
|---|---|---|
| Horizonte | `horizonte.py` | Ano de valuacion y costos hundidos |
| EscenarioDePrecios, parametros | `parametros.py` | Dato maestro versionado |
| Produccion | `produccion.py` | Por unidad y ano |
| Ventas y deducciones | `ventas.py` | Metal pagable, terminos comerciales |
| Costo operativo | `cash_cost.py` | Conceptos base y adicionales |
| Capital | `capex.py` | Inicial, diferido, sostenimiento, cierre, valor residual |
| Depreciacion | `depreciacion.py` | **Separada por mina** (`D-04`) |
| Tributos | `tributos.py` | Tramos, participacion, regalias y aportes |
| Flujos | `flujos.py` | EBITDA, EBIT, utilidad neta, flujo economico |
| Capital de trabajo | `capital_trabajo.py` | Dias y variacion |
| Indicadores | `indicadores.py` | NPV, TIR, payback, capital intensity |

El motor sigue siendo puro: recibe un caso validado y devuelve series. Nada de esto lee Excel; de
eso se encarga `minsur_ingest`.

## 8. Lo que este modelo deja fuera a proposito

- **La capa de presentacion del libro.** `Ppt`, `Informe`, `WF` y `Tornado` son salida, y la
  plataforma tiene la suya. Es tambien donde se concentran las 9 976 formulas rotas del libro.
- **El estado interno de @RISK.** PT5 reimplementa el metodo de simulacion, no traduce las
  formulas del complemento.
- **Los niveles de valor por encima de Asset Value.** El estandar corporativo define Minsur Local
  Value y Shareholder Value; el alcance de la plataforma es la evaluacion preliminar de proyecto,
  cuyo caso base es Asset Value. Se documenta para que el alcance no crezca por inercia.

## 9. Lo que falta para cerrarlo

| Punto | Bloqueado por |
|---|---|
| Unidades de medida por concepto | Confirmacion de Finanzas junto con la plantilla |
| Que representa el tope de 90 000 de `InputsProd` | Regla 002 de [reglas-no-documentadas.md](reglas-no-documentadas.md) |
| Algoritmo de punto fijo para la circularidad | ADR pendiente, regla 006 |
| Tolerancias del contraste | `R-31`, sin acordar |
| Tributos aplicables al alcance | `R-32`, tres lineas del estandar sin parametro |
