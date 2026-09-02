# Catalogo canonico de inputs

Que datos necesita una evaluacion, con que forma y de donde salen. Es la pieza que permite que la
plataforma evalue un proyecto que hoy no existe: mientras el libro corporativo precablea sus casos
en bandas de columnas, este catalogo describe **el conjunto de datos de un caso cualquiera**.

Deriva de los tres arquetipos acordados el 01/09/2026, tomados del control de supuestos del propio
libro y localizados en su catalogo de casos `Control!N7:Q54`:

| Arquetipo | Caso en el libro | Que representa |
|---|---|---|
| Operacion consolidada | 1, `Sin Proyecto (SR+B2+Pot)` | Varias unidades en marcha, sin proyecto nuevo |
| Proyecto nuevo | 3, `Nazareth 2038` | Un proyecto greenfield sobre una operacion existente |
| Combinado | 7, `Nazareth 2038R + Santo Domingo` | Dos proyectos evaluados juntos |

**Sin cifras.** Aqui van conceptos, unidades y formas. Los valores estan en el libro y en el
informe de diseccion, ambos en `00-gestion/03-insumos-minsur/`.

---

## 1. La regla que separa entrada de calculo

Acordada el 01/09/2026, cuando se decidio que lo que hoy viene de otro libro sera dato que el
usuario cargue en la plataforma:

> Una celda es **input** si no tiene formula, o si su formula solo referencia libros externos. Es
> **calculada** si su formula referencia celdas internas del libro.

Esta regla resuelve un problema que el libro no resuelve solo. Su propia convencion — "celdas
amarillas = Input", declarada en `Control` — no es fiable: hay 351 celdas amarillas y 349 tienen
formula. La procedencia de la formula si es un criterio objetivo y comprobable.

## 2. El hallazgo que hace posible el proyecto X, Y o Z

Las hojas de entrada no son listas planas de datos: **repiten el mismo bloque de conceptos por
unidad productiva**. En `InputsProd`, San Rafael, B2, Nazareth y Santo Domingo tienen exactamente
las mismas filas, en el mismo orden, desplazadas. En `InputsOpex` ocurre lo mismo, y en
`Depreciacion` el bloque contable se repite por unidad.

```
Bloque de unidad productiva  (se instancia una vez por mina o planta)
  Produccion     mineral extraido, leyes, mineral tratado por etapa,
                 toneladas finas, recuperacion, produccion de concentrado
  Opex           exploraciones, geologia, mina, planta de preconcentracion,
                 planta concentradora, mantenimiento, energia, apoyo,
                 estudios y optimizaciones, relavera
  Capex          inicial, sostenimiento, cierre de mina, otros
  Depreciacion   no depreciable, maquinaria y equipos, instalaciones,
                 edificaciones y construcciones
```

De ahi sale la forma del estandar: **un caso es una lista de unidades productivas, cada una con su
bloque, mas un conjunto de datos comunes al caso**. Anadir el proyecto X no es abrir columnas
nuevas: es instanciar el bloque una vez mas.

Que el bloque sea idéntico entre unidades no es una suposicion nuestra; es como esta escrito el
libro hoy, en los tres arquetipos.

## 3. El mismo concepto cambia de procedencia, no de naturaleza

La clasificacion arroja un patron que conviene entender antes de disenar nada:

| Hoja y filas | Operacion consolidada | Proyecto nuevo | Combinado |
|---|---|---|---|
| `InputsProd`, bloque de San Rafael | calculada | input | input |
| `InputsOpex`, bloque de Nazareth | input | calculada | calculada |

El mismo concepto — mineral tratado, costo de mina — es un valor cargado en un caso y una
derivacion en otro, segun de donde viniera la informacion cuando se armo ese caso. La lectura
correcta no es que haya dos conceptos distintos, sino que **el concepto es siempre el mismo y lo
que cambia es su procedencia**.

En la plataforma, la procedencia es un atributo del dato en un caso concreto (cargado, derivado o
heredado del LOM), no una propiedad del concepto. Sin esa distincion, el catalogo se duplicaria por
cada forma de obtener el mismo numero.

## 4. Dominios y conceptos

Nombres tomados del vocabulario del libro y del control de supuestos de Finanzas, no inventados.

### 4.1 Produccion — por unidad productiva y ano

| Concepto | Unidad | Dimension |
|---|---|---|
| Mineral extraido | t | unidad x ano |
| Ley de Sn de cabeza | % | unidad x ano |
| Mineral tratado en preconcentracion | t | unidad x ano |
| Ley de Sn de entrada a preconcentracion | % | unidad x ano |
| Mineral preconcentrado a concentradora | t | unidad x ano |
| Mineral directo a planta concentradora | t | unidad x ano |
| Mineral tratado total en concentradora | t | unidad x ano |
| Mineral tratado total para cash cost | t | unidad x ano |
| Toneladas finas | tmf | unidad x ano |
| Ley de Sn del concentrado | % | unidad x ano |
| Recuperacion de Sn | % | unidad x ano |
| Produccion de concentrado | t | unidad x ano |

Las unidades polimetalicas repiten ley, recuperacion y produccion por cada metal, pero **no todos los
metales tienen concentrado propio**: en el libro la plata va dentro del concentrado de cobre y lo
unico que se declara de ella es su ley en ese concentrado. Pedirle a un proyecto la produccion de un
concentrado de plata seria pedir un dato que no existe.

**Cada corriente de tonelaje lleva su propia ley.** El libro escribe pares contiguos —el tonelaje y,
debajo, su ley— y rotula todas las leyes igual, `Ley Sn`: lo unico que las distingue es esa vecindad.
En el bloque de una mina con preconcentracion hay seis pares, no dos. El detalle y las brechas que
abrio estan en [brechas-plantilla-produccion.md](brechas-plantilla-produccion.md).

**Cada unidad se describe con dos sub-bloques, `Mina` y `Planta`**: de donde sale el mineral y por
que proceso pasa. Es la estructura del libro y la que reproduce la plantilla.

Dos conceptos mas que la verificacion de cobertura obligo a incorporar, y que cambian el modelo de
datos: **concentrado alimentado desde otra unidad** y **concentrado excedente**. El libro encadena
unidades — el concentrado de las minas alimenta a la fundicion y el sobrante se vende — de modo que
una unidad no se describe sola. Y las unidades de fundicion anaden toneladas alimentadas mas
escoria, metal contenido en el concentrado y produccion de metal refinado.

**La capacidad maxima de tratamiento es un input, y es del complejo.** La lectura de las formulas
mostro que el tope de la regla 002 no acota una planta concentradora: acota la **fundicion**, sobre
la suma del concentrado que le entregan las cinco unidades. Finanzas confirmo el 01/09/2026 que el
usuario debe poder cambiarlo, asi que entra como serie por ano de la unidad de fundicion. Lo tratado
es el minimo entre lo alimentado y esa capacidad; el resto es concentrado excedente.

**La ley agregada se pondera por tonelaje.** El libro la calcula como `SUMPRODUCT(tonelaje, ley) /
SUM(tonelaje)`, no como media de las leyes anuales, y la ley del concentrado se pondera por la
produccion de concentrado y no por el mineral tratado. Es un detalle facil de perder y su efecto
supera la tolerancia de N1.

### 4.2 Costo operativo — por unidad productiva y ano

Exploraciones · Geologia · Mina · Planta de preconcentracion · Planta concentradora · Fundicion ·
Refineria · Planta de subproductos · Mantenimiento · Energia · Linea de transmision · Agua potable ·
Planilla · Apoyo · Gestion social · Predios, servidumbres y usufructos · Estudios y optimizaciones ·
Relavera. Todos en US$ por ano y con la misma dimension unidad x ano.

Los diez primeros salieron de la lectura de los tres arquetipos; los ocho restantes los anadio la
verificacion de cobertura de la seccion 6, que encontro conceptos usados por el libro y ausentes de
la primera version de este catalogo.

El acuerdo 6 de la minuta del 27/08/2026 exige que esta lista sea **extensible**: el usuario puede
anadir conceptos que solo afecten al total. Por eso el catalogo fija los diez conceptos base como
estructura y admite conceptos adicionales sin obligar a cambiar el motor.

### 4.3 Capital — por unidad productiva, ano y doble clasificacion

`InputsCapex` es el caso mas limpio del libro: **no tiene ni una formula propia**. Sus 5 394
formulas son enlaces a otro libro y el resto son valores. Todo el capital entra como input.

Se clasifica dos veces, y las dos clasificaciones son independientes:

| Clasificacion | Valores |
|---|---|
| Por etapa | Capex inicial · Sostenimiento · Cierre de mina · Otros |
| Por naturaleza contable | No depreciable · Maquinaria, equipos y vehiculos · Instalaciones y equipos diversos y de comunicaciones · Edificaciones y construcciones |

La segunda es la que gobierna la depreciacion, y por eso `Depreciacion` repite el mismo bloque
contable por unidad. La desviacion acordada `D-04` obliga a que ese calculo sea **separado por
mina** en todos los casos.

### 4.4 Comercial y precios — por metal y ano

Precios de Sn, Cu y Ag, en varios juegos alternativos que el libro selecciona con un segundo
control (`Control!$G$8`): proyectos, recursos de una fecha dada, precios base de proyectos, precios
de presupuesto y largo plazo. Es la dimension de escenario de precios que el estandar corporativo
exige tratar como base, optimista y pesimista.

Ademas: terminos comerciales de Sn y de Cu, gastos de venta por metal, fletes, y las deducciones
del ingreso cuya clasificacion sigue pendiente (nota 1 de [mapa-n1.md](mapa-n1.md)).

### 4.5 Datos comunes al caso

Horizonte y primer ano · dias de working capital · tratamiento del IGV en working capital ·
perdidas tributarias arrastradas · costos hundidos · inversion social · gastos administrativos ·
otros gastos operativos · servidumbres y usufructos · estudios · exploraciones.

Los siete parametros corporativos — tasa de descuento, participacion de trabajadores, impuesto a la
renta, regalia sobre ventas, Osinergmin, OEFA y fondo de jubilacion minera — **no son inputs del
caso**: son dato maestro versionado, y en el libro viven en `Control`. Ver
[modelo-estandar.md](modelo-estandar.md).

## 5. Matriz de variabilidad

Es la clasificacion que decide donde vive cada cosa en la plataforma.

| Clase | Definicion | Ejemplos | Donde vive |
|---|---|---|---|
| **Estructural** | Identico en los tres arquetipos | El bloque de produccion, la doble clasificacion de capex, el bloque contable de depreciacion | En el motor. No se pregunta al usuario |
| **Particular** | Existe siempre, con valores propios de cada caso | Series de produccion, costos, capex, precios, horizonte | En la plantilla de inputs |
| **Opcional** | Presente solo en algunos arquetipos | Preconcentracion, relavera, segundo y tercer metal, tratamiento de relaves de terceros | En el esquema, condicionado por el tipo de unidad |
| **Excluido** | Presente en el libro y descartado por acuerdo | La variable `Frd` de Relavera B2, confirmada en la fila 37 de `InputsProd` (`D-03`) | En ningun sitio, y declarado asi en N0 |

La prueba de que la clasificacion es correcta la da el arquetipo de operacion consolidada: su
bloque de Nazareth esta vacio y el modelo sigue calculando. Lo opcional es opcional de verdad.

## 6. Verificacion de cobertura

El catalogo sirve si cubre lo que el libro pide de verdad. La comprobacion recorre las bandas de los
tres arquetipos, toma cada fila clasificada como input y busca su concepto:

| Resultado | Filas | Lectura |
|---|---|---|
| Cubiertas por un concepto | 138 | El catalogo las describe |
| Derivadas o de control | 25 | Totales, cash cost por tmf, banderas de ano con produccion. **No son inputs**: la plataforma las calcula |
| Variantes por metal | 32 | Ley y produccion repetidas por Sn, Cu y Ag sobre conceptos ya cubiertos |
| Sin concepto | 12 | Ver abajo |

De las doce sin concepto, una es `Frd`, que la desviacion `D-03` manda excluir. Dos son gastos
extraordinarios de un caso concreto — reclasificaciones de covid — que entran por las filas
adicionales que permite el acuerdo 6. Las nueve restantes **no son huecos del catalogo sino del
vocabulario**: el libro abrevia (`LT`, `Pta Subproductos`) y pega el nombre de la unidad a la
etiqueta (`Mineral Tratado Planta B2`, `Tratamiento de Relaves B2`).

Ese hallazgo tiene consecuencia de diseno: **la ingesta necesita una tabla de sinonimos** que
traduzca las etiquetas del libro a los conceptos del catalogo. Sin ella, leer una plantilla llenada
a la manera del libro deja fuera una de cada veinte lineas, en silencio.

La comprobacion se repite cada vez que cambie el catalogo. Es lo que impide que crezca por un lado
y se quede corto por el otro.

## 7. Lo que este catalogo aun no fija

1. **Unidades de medida exactas por concepto.** El libro no las declara en una capa propia; se
   infieren del contexto y de las etiquetas. Se confirman con Finanzas junto con la plantilla.
2. **El tercer arquetipo del control de supuestos.** La hoja oculta `Inputs` documenta tres
   columnas — `SR+B2+Pisco`, `NZ` y `SRP` — y el catalogo de casos no tiene un caso que se
   corresponda con `SRP`. Se tomo el caso 7 como tercer arquetipo por ser el combinado vigente.
   Pendiente de aclarar cual era la intencion.
3. **La lista de conceptos adicionales de opex** que cada proyecto ha ido anadiendo. Por diseno es
   abierta; interesa saber cuales son frecuentes para ofrecerlos como sugerencia.
