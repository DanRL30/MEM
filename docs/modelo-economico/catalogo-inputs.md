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
unidades — el concentrado de las minas alimenta a la refineria y el sobrante se vende — de modo que
una unidad no se describe sola. Y las unidades de refineria anaden toneladas alimentadas mas
escoria, metal contenido en el concentrado y produccion de metal refinado.

**La capacidad maxima de tratamiento es un input, y es de la refineria.** La lectura de las formulas
mostro que el tope de la regla 002 no acota una planta concentradora: acota la **refineria**, sobre
la suma del concentrado que le entregan las cinco unidades. Finanzas confirmo el 01/09/2026 que el
usuario debe poder cambiarlo, asi que entra como serie por ano de la unidad de refineria. Lo tratado
es el minimo entre lo alimentado y esa capacidad; el resto es concentrado excedente.

**La ley agregada se pondera por tonelaje.** El libro la calcula como `SUMPRODUCT(tonelaje, ley) /
SUM(tonelaje)`, no como media de las leyes anuales, y la ley del concentrado se pondera por la
produccion de concentrado y no por el mineral tratado. Es un detalle facil de perder y su efecto
supera la tolerancia de N1.

### 4.2 Costo operativo y gastos — por unidad productiva y ano

**Son dos bloques y no uno.** La primera version de esta seccion los mezclaba, y la auditoria fila
a fila de `InputsOpex` del 02/09/2026 mostro que el libro los separa: el cash cost por un lado y los
gastos por otro, con destinos distintos en el flujo. Ver
[brechas-plantilla-opex.md](brechas-plantilla-opex.md).

**Cash cost.** Exploraciones · Geologia · Mina · Planta de preconcentracion · Planta concentradora ·
Mantenimiento · Energia · Apoyo · Estudios y optimizaciones · Relavera · Linea de transmision ·
Peajes y mantenimiento · Agua potable · STA · Fundicion · Refineria · Planta de subproductos ·
Mantenimiento de fundicion y refineria.

Los cuatro ultimos son de la refineria, y van en la misma estructura que los demas: una mina los
deja en cero, igual que la unidad sin preconcentracion deja en cero esa fila. `Peajes y
mantenimiento` y `STA` son de Santo Domingo y ninguna otra unidad los tiene; `STA` es una
abreviatura que ningun documento traduce, asi que se conserva literal y esta consultada.

**Tres conceptos del libro quedan deliberadamente fuera**, por decision del 02/09/2026. Dos son de
Santo Domingo —`Servicios Mina`, que solo esa unidad distingue de `Mina`, y `Preconcentrado Blue
Sky`, que lleva el nombre de un tercero— y el tercero es `Planillas`, que no es un dato sino la
planilla derivada del cash cost. Los dos primeros se cargan por la cola de conceptos propios, que
para eso existe; el tercero no vuelve por ningun camino.

**Gastos.** Gastos administrativos · Gestion Social · Predios · Servidumbres y usufructos ·
Estudios Pre Factibilidad (Gasto) · Estudios Factibilidad (Capitalizable) · Exploraciones.

Los tres restantes del bloque del libro —`Ano con operacion`, `Planilla` y `Gestion Social
Deducible`— **no son inputs**: el libro los deriva del cash cost de la unidad y de la propia gestion
social. La plataforma los calcula (reglas `026` y `027`) y no los pide.

Todos los conceptos de los dos bloques van en la misma dimension unidad x ano. El libro los escribe
en miles de dolares, rotulados `$k`, y la ingesta los convierte: es la regla `003`.

El acuerdo 6 de la minuta del 27/08/2026 exige que la lista de cash cost sea **extensible**: el
usuario puede anadir conceptos que solo afecten al total. La plantilla lo resuelve con una cola de
longitud fija al cierre del bloque, en `minsur_ingest.opex`. Ahi entran las reclasificaciones de
covid de los casos historicos, que son de un caso concreto y no del catalogo.

### 4.3 Capital — por unidad productiva y ano

**Se pide una sola clasificacion, la contable, y son cinco conceptos**, en `$k` y con la dimension
unidad x ano:

No depreciable · Equipos de computo · Maquinaria, equipos y vehiculos · Instalaciones y equipos
diversos y de comunicaciones · Edificaciones y construcciones.

Los dos del medio comparten el codigo `MAQ` del libro y se consolidan al leer, que es lo que hace
la via tributaria. Se piden separados porque asi llega el dato y porque los equipos de computo
suelen depreciarse mas rapido: si Finanzas confirma una tasa propia, se le da sin volver a pedir
los datos.

**La etapa —inicial, sostenimiento, cierre— no es dato: se deriva.** La auditoria del 02/09/2026
mostro que la primera version de esta seccion la daba por entrada y describia una doble
clasificacion cargada que el libro no tiene. Las tres reglas de la derivacion, la clasificacion de
cada bloque de la hoja y las cuatro consultas que abrio estan en
[brechas-plantilla-capex.md](brechas-plantilla-capex.md).

La naturaleza contable es la que gobierna la depreciacion, y por eso `Depreciacion` repite el mismo
bloque por unidad. La desviacion acordada `D-04` obliga a que ese calculo sea **separado por mina**
en todos los casos.

**Las tasas de depreciacion son dato maestro y la plantilla las admite igual.** Las mantiene MINSUR
(`R-32`) y una corrida registra con que version se calculo; lo que el caso declare sobrescribe
**solo ese componente** para ese caso, como ya ocurre con los aportes reguladores. Son cinco
—maquinaria, instalaciones, edificaciones, estudios y no depreciable— y se escriben **una sola vez**:
no cambian de ano a ano. Los equipos de computo no llevan la suya porque su clasificacion contable es
la de la maquinaria.

**Dos inputs mas por unidad, y los dos viven en la plantilla de supuestos.** Las **reservas de
apertura**, en `kt`, que la via financiera agota: declararlas las convierte en dato y dejarlas
vacias en calculo, que es la distincion que hace el libro entre una unidad en operacion y un
proyecto. Y la **`Proyeccion SAP`**, en `k$` y una por via, que es la depreciacion ya contabilizada
de los activos anteriores al caso.

**Una clase de unidad mas: la relavera de deposito.** Recibe relave, no extrae mineral, y de ella
solo hay capital y depreciacion; su costo operativo se carga en la linea `Relavera` de la mina a la
que sirve. No lleva pestana en el libro de produccion, si en los de opex y capex.

### 4.4 Comercial y precios — por metal y ano

Precios de Sn, Cu y Ag, en varios juegos alternativos que el libro selecciona con un segundo
control (`Control!$G$8`): proyectos, recursos de una fecha dada, precios base de proyectos, precios
de presupuesto y largo plazo. Es la dimension de escenario de precios que el estandar corporativo
exige tratar como base, optimista y pesimista. En la plataforma son el **comite de precios**, dato
maestro que sube Finanzas y que la corrida registra en su terna.

Los terminos comerciales son del caso y viven en la pestana comun de la plantilla de supuestos:

| Concepto | Unidad | Dato o calculo | Campo del motor |
|---|---|---|---|
| Precio Sn, Cu | `$/t` | dato maestro | `MetalDelConcentrado.precio`, `TerminosComerciales.precio_*` |
| Precio Ag | `$/oz` | dato maestro | `MetalDelConcentrado.precio` |
| Premio Sn | `$/t` | dato | `TerminosComerciales.premio_metal_refinado` |
| Pagable sobre concentrado de Sn | `%` | dato | `TerminosComerciales.factor_metal_pagable` |
| Merma | `%` | dato | `TerminosDelConcentrado.merma` |
| Deduccion Minima Cu | `%` | dato | `MetalDelConcentrado.deduccion_minima` |
| Deduccion Minima Ag | `g/t` | dato | `MetalDelConcentrado.deduccion_minima` |
| Factor Metal Pagable Cu, Ag | `%` | dato | `MetalDelConcentrado.factor_pagable` |
| Maquila | `$/t` | dato | `TerminosDelConcentrado.maquila_por_tonelada` |
| Tarifa de Refinacion Cu | `$/lb` | dato | `MetalDelConcentrado.tarifa_de_refinacion` |
| Tarifa de Refinacion Ag | `$/oz` | dato | `MetalDelConcentrado.tarifa_de_refinacion` |
| Refinacion Cu | `$/t` | **calculo**, regla 021 | `MetalDelConcentrado.cargo_de_refinacion` |
| Penalidades Cu, Ag | `$/t` | dato | `MetalDelConcentrado.penalidades_por_tonelada` |
| Ajustes de Venta | `$` | dato | `TerminosComerciales.ajustes` |

Y tres van en la pestana de cada unidad, porque se derivan de la ley del concentrado de esa unidad:

| Concepto | Unidad | Dato o calculo | Campo del motor |
|---|---|---|---|
| Ley Pagable Cu | `%` | **calculo**, regla 023 | `UnidadProductiva.ley_pagable_declarada` |
| Ley Pagable Ag | `g/t` | dato; su formula esta consultada (regla 045) | `UnidadProductiva.ley_pagable_declarada` |
| Refinacion Ag | `$/t` | **calculo**, regla 022 | `UnidadProductiva.refinacion_declarada` |

Lo marcado como calculo se pide igual y se corrobora: **declararlo lo convierte en dato** y dejarlo
vacio deja que el motor lo calcule, que es la misma distincion que hace el libro con las reservas.

Siguen fuera del motor los gastos de venta por metal, el costo de fundicion y los fletes: su
clasificacion entre costo operativo y deduccion del ingreso es la nota 1 de
[mapa-n1.md](mapa-n1.md), sin respuesta de Finanzas. La lectura fila a fila de la hoja esta en
[brechas-plantilla-ventas.md](brechas-plantilla-ventas.md).

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
