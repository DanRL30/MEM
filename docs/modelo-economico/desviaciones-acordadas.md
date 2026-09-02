# Desviaciones acordadas respecto del modelo de referencia

La regla de fidelidad manda reproducir la logica del modelo economico corporativo **incluidos sus
redondeos y sus valores incrustados**. Un error metodologico se documenta y se reporta; no se
corrige. Esa regla es la que hace del contraste N0-N3 un criterio de aceptacion.

Este documento registra los puntos donde **MINSUR ha pedido expresamente que la plataforma se aparte
del modelo**. No son defectos ni interpretaciones de INVA: son acuerdos con el cliente, y cada uno
cita la reunion que lo origino.

Importa registrarlos por una razon concreta: en las lineas afectadas **el motor no va a coincidir
con el modelo, y no debe coincidir**. Sin este registro, el contraste las reporta como fallos y la
certificacion de fidelidad tropieza justo donde el cliente pidio apartarse.

## Como se tratan en el contraste

Una desviacion acordada no se contrasta contra el modelo. Se contrasta contra el **valor esperado
que define el acuerdo**, y la prueba correspondiente declara la desviacion que aplica.

Tres tratamientos posibles, segun lo que pida el acuerdo:

| Tratamiento | Cuando aplica | Efecto en el contraste |
|---|---|---|
| `EXCLUIDA` | El acuerdo elimina un elemento del modelo | La linea no participa del contraste |
| `RECALCULADA` | El acuerdo obliga a calcular lo que el modelo trae fijo | Se contrasta contra el valor del acuerdo, no contra la celda |
| `DESAGREGADA` | El acuerdo separa lo que el modelo consolida | La suma de las partes se contrasta contra el consolidado del modelo |

`DESAGREGADA` conserva una comprobacion util: el modelo no dice cuanto vale cada parte, pero si
cuanto valen juntas, y esa identidad debe cumplirse.

## Estado de la validacion

**Las cuatro primeras estan acordadas en minuta firmada, pero su tratamiento en el contraste es
propuesta de INVA y no esta confirmado por Finanzas.** La quinta la decidio el Project Manager el
01/09/2026 y esta pendiente de llevar a Finanzas. Hasta que lo este, las pruebas de fidelidad
las marcan como pendientes y no como aprobadas. La consulta corresponde emitirla junto con las de
`estandar-dm-std-pe-27.md`.

---

## D-01. Prevalencia del LOM en los tres primeros anos

- **Origen:** minuta de Finanzas del 27/08/2026, acuerdo 1. Daniel Robles y Nicolas Garcia.
- **Tratamiento propuesto:** `RECALCULADA`

Los tres primeros anos del LOM traen un nivel de detalle mayor que el de los inputs calculados, y el
acuerdo establece que la plataforma debe ser flexible y **priorizar los datos del LOM sobre los
valores calculados en ese periodo inicial**.

En esos tres anos el motor deja de reproducir el calculo del libro. El contraste de esas lineas se
hace contra el LOM.

Queda por precisar: si los tres anos se cuentan desde el inicio del horizonte o desde el inicio de
produccion, y si la prevalencia aplica a todas las lineas del bloque o solo a produccion.

## D-02. Filas intermedias de estano en Nazareth

- **Origen:** minuta de Finanzas del 27/08/2026, acuerdo 2.
- **Tratamiento propuesto:** `RECALCULADA`

En el modelo, todos los valores de Nazareth figuran como datos fijos y **faltan las filas intermedias
de calculo de estano**. El acuerdo obliga a incorporarlas y calcularlas en la plataforma.

Es el caso mas claro de apartarse del modelo: se calcula lo que el libro trae incrustado. El
resultado final deberia coincidir con el dato fijo del modelo, y esa coincidencia es precisamente la
comprobacion que da valor a la desviacion. Si no coincide, o el calculo esta mal o el dato fijo del
modelo lo estaba.

Queda por precisar: si se admite diferencia entre el calculado y el fijo, y con que tolerancia.

## D-03. Exclusion de la variable Frd en Relavera B2

- **Origen:** minuta de Finanzas del 27/08/2026, acuerdo 3.
- **Tratamiento propuesto:** `EXCLUIDA`

Se identifico la variable `Frd` en la seccion de Relavera B2 y se acordo descartarla, **ya que no se
calcula ni afecta los resultados**.

No entra a la plataforma y no participa del contraste N0. Al leer los inputs, N0 debe ignorarla de
forma explicita y declarada, no por omision: una variable que desaparece sin dejar rastro es
indistinguible de una que se olvido leer.

## D-04. Depreciacion separada por mina

- **Origen:** minuta de Finanzas del 27/08/2026, acuerdo 8. Con Hugo Diaz.
- **Tratamiento propuesto:** `DESAGREGADA`

Santo Domingo presentaba depreciacion tributaria y financiera separadas, mientras que Nazareth
estaba consolidada con San Rafael. El acuerdo determina que **la plataforma procese ambas
depreciaciones por separado en todos los casos**.

De ahi se sigue el requisito funcional que el propio acuerdo enuncia: la plataforma debe permitir
**crear y configurar minas de manera independiente**. Es la desviacion con mas alcance de las
cuatro, porque no cambia una linea sino el modelo de datos.

En el contraste, la suma de las depreciaciones de Nazareth y San Rafael debe reproducir el
consolidado del modelo. El reparto entre ambas no tiene contraparte en el libro.

Queda por precisar: como se reparte entre las dos minas la base depreciable que el modelo consolida.

## D-05. El recorte por capacidad se reparte por merito

- **Origen:** decision del Project Manager, 01/09/2026, sobre el hallazgo de la regla `017`.
- **Tratamiento propuesto:** `RECALCULADA`

Cuando las minas entregan mas concentrado del que el complejo puede tratar, una parte no se refina
y se vende como concentrado. **Quien se queda fuera cambia el resultado**, porque cada unidad
entrega concentrado de distinta ley y se refina con distinta recuperacion.

El modelo se lo resta **entero a la ultima unidad en entrar**: en la banda del caso con Santo
Domingo, la formula del refinado hace entrar a esa unidad con `(alimentado - excedente)` mientras
las otras cuatro entran completas. Esa asimetria no se puede generalizar a un proyecto nuevo sin
decidir arbitrariamente a quien le toca.

La plataforma reparte **por merito: va a spot primero el concentrado de menor ley**, de modo que se
refina el mejor y se vende el peor. Es lo que haria cualquier operador, y no depende de en que orden
se declararon las unidades.

El efecto es material y no un matiz de redondeo. Sobre las cinco unidades del modelo con un
excedente de 6 800 t, el refinado del ano va de 32 524 tmf a prorrata a 33 506 por merito, pasando
por 32 759 con el criterio del libro.

**Arrastra una segunda consecuencia, y es de coherencia.** El libro valoriza el excedente a la ley
promedio del conjunto. Con reparto por merito lo que sale es el concentrado de menor ley, asi que
usar el promedio sobrestimaria el metal contenido en lo que se vende: la plataforma usa la ley de
lo que efectivamente fue a spot. No se puede decir que sale el peor concentrado y despues cobrarlo
como si fuera del promedio.

El contraste de esta linea se hace contra el valor que define el acuerdo, no contra la celda del
modelo. El motor expone las dos: `refinado` con el tope aplicado y `refinado_sin_restriccion` sin
el, que es la linea que el libro rotula asi.

**El analisis es de cada ano y solo de ese ano.** El orden se decide con las leyes de ese ejercicio y
el excedente de ese ejercicio; nada se arrastra del anterior, y un ano sin saturacion no deja deuda
al siguiente. Una unidad que no produce ese ano no cede nada, aunque haya sido la de menor ley en
otros: B2 tiene cinco anos con dato sobre un horizonte de treinta y siete, y en los demas el recorte
lo absorbe quien corresponda entre las que si estan produciendo. Esa es la razon de que la ley de lo
que va a spot cambie de un ano a otro.

Queda por precisar: si el criterio de merito es la ley del concentrado o el margen por tonelada, que
tambien depende del cargo de tratamiento de cada origen.

---

## Lo que no es una desviacion

Los otros seis acuerdos de la misma minuta son **requisitos de producto**, no apartamientos del
modelo, y no se registran aqui:

- Supuestos con variables planas y con proyecciones ano a ano (acuerdo 4).
- Gastos sociales y otros gastos operativos como inputs editables (acuerdo 5).
- OPEX extensible con filas adicionales que solo afectan al total (acuerdo 6).
- Carga y edicion flexibles de la pestana de otros gastos (acuerdo 7).
- Reservas editables en proyectos LOM y calculadas en greenfield (acuerdo 9).
- Sesion de trabajo para estandarizar las plantillas de inputs (acuerdo 10).

Tampoco lo es el **recalculo interno de validacion** que pide el avance 02 del 28/08/2026: los
inputs entran como datos fijos y el sistema recalcula para verificar consistencia y emitir alertas
de calidad. Es funcionalidad nueva, no una desviacion del modelo, y su alcance esta sin acordar.

## Como se registra una desviacion nueva

1. Debe existir un acuerdo escrito con MINSUR que la pida. Sin acuerdo no hay desviacion: hay un
   defecto de implementacion o una regla no documentada, y esas viven en
   [reglas-no-documentadas.md](reglas-no-documentadas.md).
2. Se le asigna un identificador correlativo `D-xx` y se describe que hace el modelo, que debe hacer
   la plataforma y por que difieren.
3. Se elige tratamiento entre `EXCLUIDA`, `RECALCULADA` y `DESAGREGADA`.
4. La prueba de fidelidad correspondiente cita el identificador. Una linea que difiere del modelo
   sin citar una desviacion es un fallo, y debe seguir siendolo.
