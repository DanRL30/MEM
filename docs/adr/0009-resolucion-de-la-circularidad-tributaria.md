# 0009. Resolución de la circularidad tributaria por solución cerrada

- Estado: aceptada
- Fecha: 01/09/2026
- Decide: INVA, por delegación expresa de Finanzas MINSUR el 01/09/2026
- Restricción relacionada: regla 002 y 006 de
  [reglas-no-documentadas.md](../modelo-economico/reglas-no-documentadas.md)

## Contexto

El libro corporativo tiene el cálculo iterativo de Excel activado (`iterate=1`). No es un descuido:
la hoja `Impuestos` referencia `FC NZ` 359 veces y la dependencia se cierra sobre sí misma.

> **Corrección del 01/09/2026, posterior a la aceptación.** Al derivar la hoja para implementar
> `tributos.py` se comprobó que el lazo lo cierra el **fondo de jubilación minera**, que es gasto
> deducible de la utilidad operativa que sirve de base para calcularlo; la participación de
> trabajadores y el impuesto a la renta no realimentan. Este ADR describía el ciclo al revés. La
> decisión no cambia —el sistema sigue siendo afín a trozos y con solución cerrada— y por eso se
> corrige el contexto en lugar de superseder la decisión.

Excel resuelve ese ciclo repitiendo el cálculo hasta que el cambio entre pasadas cae por debajo de
un umbral. Ese umbral y el número máximo de repeticiones son **configuración de la aplicación, no
del modelo**: viajan con la instalación de Excel, no con el archivo. Dos analistas con ajustes
distintos obtienen resultados distintos del mismo libro, y ninguno de los dos es reproducible a
cinco años, que es lo que exige el congelamiento de corridas.

Consultado el punto, Finanzas respondió el 01/09/2026 que fijemos nosotros el criterio y que sea
«el más fiable y preciso». Esta decisión responde a ese encargo.

## Decisión

**El motor no itera para resolver la circularidad: la resuelve en forma cerrada.**

El subsistema circular es afín — cada ecuación es lineal en las incógnitas dentro de un tramo
tributario dado — y por tanto tiene solución única y exacta. El motor la obtiene resolviendo el
sistema lineal, no aproximándose a él.

Los tributos por tramos hacen que el sistema sea afín **a trozos**. El procedimiento es:

1. Para cada combinación de tramos candidata, resolver el sistema lineal correspondiente.
2. Aceptar la solución solo si es consistente: si los valores resultantes caen efectivamente dentro
   de los tramos que se supusieron.
3. Si ninguna combinación es consistente, o si hay más de una, el motor **falla con un error
   explícito**. No devuelve un resultado aproximado.

Como red de seguridad se conserva un solucionador de punto fijo con amortiguación, que **no
participa del cálculo** y solo se usa en las pruebas: si la solución cerrada y el punto fijo
difieren más allá de la precisión de coma flotante, hay un error de derivación y la prueba falla.

## Alternativas consideradas

**Punto fijo con tolerancia, imitando a Excel.** Es lo primero que se piensa, porque reproduce el
mecanismo del libro. Se descartó por tres razones. La tolerancia sería un número inventado por
nosotros que afecta al último decimal de todos los indicadores. La convergencia no está garantizada
para cualquier combinación de parámetros. Y ante un contraste con discrepancia, obligaría a
distinguir si la diferencia viene de la lógica o del criterio de parada, que es exactamente el tipo
de ambigüedad que el contraste N0-N3 existe para eliminar.

**Newton-Raphson sobre el residuo.** Converge más rápido que el punto fijo y sigue siendo una
aproximación a algo que tiene solución exacta. Añade complejidad — derivadas, tolerancias, criterios
de divergencia — sin comprar precisión. Se conserva la idea solo como verificación cruzada.

**Replicar la configuración de Excel del analista.** Descartada de plano: haría que el resultado de
una evaluación dependiera de la máquina donde se calculó, que es incompatible con el sellado y con
la reproducción a cinco años.

## Consecuencias

**Se vuelve fácil** reproducir una corrida: dos ejecuciones con la misma terna de versiones dan
exactamente el mismo número, sin depender de un criterio de parada. Y se vuelve fácil diagnosticar
una discrepancia con el modelo, porque la única fuente posible es la lógica.

**Se vuelve difícil** cambiar la estructura tributaria: añadir un tributo que introduzca una
no linealidad real — un término cuadrático, un tope que dependa de una función no lineal — rompe el
supuesto afín y obliga a revisar esta decisión con un ADR nuevo. Es una rigidez deliberada: obliga a
que un cambio así se piense, en lugar de absorberse subiendo el número de iteraciones.

**Quedaba condicionado** el módulo `tributos.py`, y la condición se cumplió el 01/09/2026. La
derivación confirmó la afinidad, aunque no fuera evidente: la tasa efectiva de regalía se obtiene
como `SUM(tramos) / margen` y luego se multiplica por la utilidad operativa, de modo que el margen
se cancela contra sí mismo y queda `regalía = ventas × C + t × utilidad`. Sin esa cancelación el
sistema habría sido cuadrático y este ADR se habría supersedido en lugar de forzarse.

**Nota sobre el contraste.** El modelo de referencia resuelve el ciclo por aproximación, así que sus
valores traen el error residual de la iteración de Excel. La diferencia es de orden numérico y cae
muy por debajo de cualquier tolerancia de N1 a N3, pero conviene registrarla al certificar: el motor
no es menos exacto que el libro, es más.
