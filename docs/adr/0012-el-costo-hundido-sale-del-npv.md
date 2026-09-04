# 0012. El costo hundido sale del NPV y lo declara el caso

- Estado: aceptada
- Fecha: 04/09/2026
- Decide: Project Manager de INVA
- Restricción relacionada: reglas `062`, `063`, `090` y `093` de
  [reglas-no-documentadas.md](../modelo-economico/reglas-no-documentadas.md), y
  `DM-STD-PE-27` §5

## Contexto

El modelo vigente escribe un **cero tecleado** en el factor de descuento de su primer ejercicio y
suma el NPV desde la segunda columna. Hasta el 04/09/2026 el motor no lo reproducía: descontaba el
horizonte entero con factor uno en el primer ejercicio, y esa era la **única línea del contraste N3
que no cerraba**. En el caso 7 la diferencia son 835 966,93 `$k` —el flujo económico de 2025 sin
descontar—, un 13 % sobre el indicador con el que se decide invertir.

El cero no está donde está por descuido. La lectura del 04/09/2026 encontró tres cosas que lo
explican:

- **El eje de exponentes es un input.** La celda que lleva el cero del contador de años tiene el
  relleno con que el libro marca lo que se teclea a mano.
- **El libro usa ese control dos veces.** Su bloque de valoración oculto pone el cero once columnas
  más a la derecha y encadena el eje hacia los dos lados, capitalizando los ejercicios anteriores.
  Es la regla `063`.
- **Y `Resumen` lleva una línea `Costo Hundido (2017-25)`**, que nombra el mismo periodo que el
  factor anula.

`DM-STD-PE-27` §5 pide exactamente eso: la evaluación se fecha *«when the project is sanctioned at
tollgate 3»* y *«previous negative cash flows should be considered sunk cost and should not be
considered as part of the Discounted Cash Flow»*.

El [ADR 0010](0010-convencion-de-descuento.md) fijó la convención de descuento —fin de año, con `t`
entero desde el primer ejercicio— y dejó esto expresamente fuera: *«No resuelve la regla `062`…
Es una consulta abierta con Finanzas porque cambia el NPV de cabecera, y esta decisión no la
toca.»* Esta decisión la toca.

## Decisión

**El caso declara su último ejercicio hundido, y los ejercicios hundidos llevan factor de descuento
cero.** El campo es `DatosComunes.ultimo_ano_hundido`, se pide en la hoja `Caso` de la plantilla de
inputs y viaja con los inputs de la corrida.

```
factor(t) = 0                      si t <= ultimo ejercicio hundido
          = 1 / (1 + r)^t          en otro caso, con t desde el primer ejercicio
```

Tres cosas que la fórmula dice y conviene leer despacio:

**La curva no se desplaza.** El exponente sigue contando desde el primer ejercicio del horizonte.
Hundir un ejercicio y fechar el NPV en otro año son operaciones distintas: la segunda mueve toda la
curva y capitaliza los ejercicios previos con factores mayores que uno. El modelo vigente usa la
primera en la hoja que publica y la segunda en el bloque que lleva oculto; **se reproduce la que
publica**.

**Hundido es fuera del descuento, no fuera del modelo.** El flujo del ejercicio se calcula entero:
alimenta el capital de trabajo del siguiente, arrastra pérdidas tributarias y mueve las cuentas por
pagar. Lo único que cambia es su factor. Es lo que hace el libro, cuya fila de flujo económico trae
la cifra completa del ejercicio anulado.

**Vacío significa que no hay ninguno**, y ese es el valor por defecto: un proyecto que abre con su
primera inversión no tiene nada anterior a la decisión. Ningún caso existente cambia de resultado.

### El año es del caso, no del calendario

`ultimo_ano_hundido` **no se deriva de la fecha de ejecución**. Un proyecto sancionado en un año se
sigue evaluando contra ese año cuando se recalcula tres años después, por dos motivos que apuntan al
mismo sitio: el estándar fecha la evaluación en el tollgate y no en el momento de abrir la hoja, y
una corrida congelada tiene que dar el mismo número a cinco años vista. Si la base siguiera al reloj
del sistema, dos corridas de la misma terna dejarían de ser comparables y el sellado no sostendría
nada.

### Los otros tres indicadores

- **El payback descontado hereda el corte**, porque sale del mismo flujo descontado que el NPV.
- **El payback simple no lo hereda**: se mide sin descontar y el modelo de referencia no dice qué
  hacer con él, porque no publica payback en ninguno de sus casos.
- **La TIR tampoco**, y aquí la decisión es deliberada. El libro calcula su `IRR` sobre el horizonte
  entero mientras su NPV empieza un ejercicio después: dos criterios de horizonte en dos filas
  adyacentes de la misma hoja. Es una inconsistencia del modelo —la regla `093`— y se reproduce y se
  reporta, no se corrige. Corregirla aquí haría que el motor entregara una TIR que el libro no
  entrega.

## Alternativas descartadas

**Fechar el NPV en el año de evaluación, desplazando la curva.** Es lo que pide leer el rótulo
`NPV 2026` de la hoja de resumen, y es lo que se indicó verbalmente al preguntar por la fecha. Da un
número un 9,1 % mayor —7 038 482,3 `$k` en el caso 7 frente a los 6 398 620,3 que el libro publica—
y **la plataforma dejaría de reproducir la cifra que el cliente reconoce**. La jerarquía del
servicio pone el modelo por encima de la lectura del rótulo: se reproduce lo que el modelo calcula y
la diferencia se reporta. Es la misma decisión que se tomó con la convención de mitad de año.

**Dejar el corte como parámetro corporativo.** El último ejercicio hundido depende del tollgate de
cada proyecto, no de la política de la empresa. Un parámetro maestro obligaría a publicar una
versión de datos maestros por proyecto.

**Derivarlo del primer ejercicio con producción, o del primero con inversión.** Las dos reglas
aciertan en el caso 7 por casualidad y fallan en cuanto un proyecto se sanciona a mitad de su
horizonte. Y ninguna de las dos es lo que el estándar dice: la fecha es la del sancionamiento, que
es un hecho de gobierno y no una propiedad de las series.

## Consecuencias

**El contraste N3 cierra.** Con `ultimo_ano_hundido = 2025`, el motor da 6 398 620,25 `$k` y la fila
41 del libro dice 6 398 620,25: brecha 0,00. Era el único indicador que difería, y con él cierran
las cuatro líneas del flujo, las veintidós de impuestos y las diez de ventas.

**Queda una discrepancia declarada, y hay que llevarla por escrito a H6.** Se indicó verbalmente que
la fecha de valoración es el cierre de 2026; la aritmética del modelo la fecha un año antes. La
plataforma reproduce el modelo, de modo que **publica un 9,1 % por debajo de la fecha que se
indicó**. Tiene que aparecer en la certificación de fidelidad junto a la discrepancia de §5.1, y la
consulta 1 del `CON` Rev. A debe reemitirse como constancia en vez de como pregunta.

**Reabrirlo es aditivo.** Fechar el NPV en otro año solo necesita un segundo campo y cambiar el
exponente; el corte de hundido ya está aislado en `factores_de_descuento()`, que es la única función
que decide el factor de un ejercicio.

**Y la pantalla tiene que decir qué se está dejando fuera.** Declarar `2025` sin más esconde que se
descartan 835 966,93 `$k` de flujo económico real. Con la cifra delante, la elección es consciente;
sin ella, el corte parece un detalle de configuración.
