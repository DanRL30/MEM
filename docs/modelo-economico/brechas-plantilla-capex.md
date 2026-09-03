# Brechas de la plantilla de CAPEX

Auditoria fila a fila de la hoja `InputsCapex` contra lo que emitia
`generar_plantilla_inputs.py` y lo que reconocia `plantilla.py`. Repite el metodo de
[brechas-plantilla-opex.md](brechas-plantilla-opex.md).

Fecha de la lectura: 02/09/2026. Las formulas y las cifras estan en el informe de diseccion, en
`00-gestion/03-insumos-minsur/`; aqui van la estructura y el vocabulario.

## 1. Las cifras

| Medida | Valor |
|---|---|
| Filas con etiqueta en `InputsCapex` | 122 |
| Celdas numericas sin formula en toda la hoja | **0** |
| Bloques de clasificacion contable, uno por unidad | 7 |
| Conceptos por bloque | 5 |
| Conceptos distintos que la plantilla pide ahora | 5 |
| Filas que emitia la plantilla anterior, por unidad | 16 |

La ultima merece el contraste: la plantilla vieja pedia cuatro etapas por cuatro naturalezas, y de
esas dieciseis celdas quince eran una invencion nuestra. El libro pide cinco.

## 2. La forma real de la hoja

`InputsCapex` no es una tabla de 125 por 1 871: es una rejilla de veintinueve ranuras de escenario
de treinta y ocho columnas, de las que solo nueve estan pobladas.

| Filas | Bloque | Clasificacion |
|---|---|---|
| 15-69 | `Clasificación <unidad>`, siete bloques de cinco conceptos | **Dato** |
| 7-11 | Etapa: inicial, sostenimiento, cierre, `xxx`, total | Calculo |
| 13 | `Tipo vs Detalle`, con su `check` | Calculo de control |
| 72-114 | `Capex por Naturaleza`, cruce etapa por naturaleza | Calculo, con `SUMIF` sobre los codigos |
| 117-124 | Consolidado y su segundo `check` | Calculo |

**El criterio que separa dato de calculo es el acordado el 01/09/2026**: una celda es input si no
tiene formula o si su formula solo referencia libros externos. Aplicado aqui da un resultado aun
mas tajante que en opex: **en toda el area numerica de la hoja no hay una sola constante tecleada**.
El dato entra por enlace a cuatro libros externos, y el propio libro lo declara: de las 125 filas,
la unica marcada como input con el color que su hoja `Control` define es una, y es justamente donde
se superpone un origen sobre otro.

El codigo de tres letras de la columna A —`NOD`, `MAQ`, `MAQ`, `INS`, `EDI`— no es decorativo: es la
clave de union de los `SUMIF` que construyen todo lo derivado. Que dos filas compartan `MAQ` es
deliberado.

## 3. Las tres reglas con que se deriva la etapa

1. **`Cierre Mina` es exactamente el codigo `NOD`.** La fila de cierre se construye sumando lo no
   depreciable de todas las unidades, y ninguna otra naturaleza entra ahi.
2. **`Capex Inicial` es la unidad de proyecto en sus primeros anos productivos**, decidido por un
   contador que vive en dos filas rotuladas como si fueran cabeceras. La regla distingue dos clases
   de unidad y **no es una puerta por produccion aplicada a todas por igual**: una unidad base -San
   Rafael, B2, la refineria, el deposito, San Rafael Potencial- no tiene bloque de capital inicial y
   su capital depreciable es sostenimiento siempre, produzca o no. Un proyecto es inicial mientras
   su cuenta de ejercicios con produccion no pase un umbral propio: uno en Nazareth, dos en Santo
   Domingo, sin justificacion escrita. Contrastado contra las bandas de los casos 1 y 7 el
   02/09/2026, **las tres etapas coinciden ejercicio a ejercicio**.
3. **El resto es `Sostenimiento`.** La cuarta etapa, `xxx`, no tiene formula en ninguna columna de
   ano: vale cero siempre, y la hoja `Depreciacion` la arrastra rotulada `Otros`.

El rotulo «cinco naturalezas por tres etapas» del bloque derivado es aparente: `NOD` esta vacio en
inicial y en sostenimiento, y `MAQ`, `INS` y `EDI` lo estan en cierre.

## 4. Las brechas, en cuatro clases

**Clase 1 — estructural.** La plantilla pedia una clasificacion que el libro no carga. No es un
concepto mal escrito: es haber pedido como dato algo que el modelo deriva, y con ello haber hecho
tautologico el `Check` que se decia verificar.

**Clase 2 — conceptos ausentes.** `Equipos de Cómputo` no estaba en ninguna parte del catalogo, y es
una de las cinco filas que el libro carga en las siete unidades.

**Clase 3 — una clase de unidad ausente.** `B4` aparece en `InputsCapex` y en `Depreciacion` y en
ninguna otra hoja de entrada. Es una relavera de deposito: recibe relave, no extrae mineral, y su
costo operativo se carga en la linea `Relavera` de la mina a la que sirve. El modelo de datos solo
tenia minas y refineria.

**Clase 4 — vocabulario.** El libro escribe `Instalaciones / Equipos **diveros** y de
comunicaciones`, con el error repetido en veintiuna filas. La plantilla lo escribe bien.

## 5. Lo que se leia y se tiraba

`_armar_capital` sumaba el mismo importe a la etapa y a la naturaleza en el mismo bucle, de modo que
**el `Check` no podia fallar por esa via**: se presentaba como verificacion y era una identidad.

Y arrastraba el mismo fallo silencioso que produccion y opex ya cerraron: una fila cuya etapa o
naturaleza no reconociera se descartaba con un `continue`, **con sus importes dentro**. El capital
desaparecia del flujo y de la depreciacion sin que nada lo acusara. La asociacion, ademas, era por
prefijo del nombre de la seccion: dos unidades cuyo nombre empezara igual se mezclaban.

## 6. Lo que ningun documento dice, y es consulta

1. **Si `Equipos de Cómputo` tiene tasa propia.** La via tributaria lo fusiona con maquinaria por su
   codigo; la financiera lo excluye de maquinaria y lo deja en el capex de unidades de produccion.
   El mismo dinero con dos tratamientos.
2. **Por que los umbrales que deciden cuando una unidad deja de ser inicial son distintos entre
   unidades.** Una usa uno y otra otro, sin nota que lo explique.
3. **Si `No Depreciable` se deduce entero.** La via tributaria lo lleva al escudo de cierre con tasa
   uno, y el motor asume cero. Mueve la base imponible del ano de cierre.
4. **Como se reparte entre dos minas la base depreciable que el modelo consolida** (`D-04`). La
   plantilla lo cierra de hecho, porque cada unidad declara su capital, pero el acuerdo con Finanzas
   sigue pendiente de escribirse. El libro consolida el deposito con su mina en la via financiera.

## 7. Donde se corrige cada brecha

| Brecha | Se corrige en |
|---|---|
| Pedir como dato una clasificacion derivada | `minsur_engine/capex.py`, con `clasificar_por_etapa` |
| Estructura por unidad en una hoja apilada | `scripts/generar_plantilla_inputs.py` |
| El `continue` silencioso y la asociacion por prefijo | `minsur_ingest/capex.py`, leyendo por secuencia |
| `Equipos de Cómputo` sin concepto | `minsur_ingest/capex.py` y el catalogo |
| La relavera de deposito sin clase | `minsur_engine/caso.py`, tipo `deposito` |
| El ajuste de capex que se leia y no se aplicaba | `minsur_engine/corrida.py` |

## 8. Estado

Cerrado el 02/09/2026: la plantilla por unidad con los cinco conceptos, la derivacion de la etapa,
el tipo de unidad `deposito`, el ajuste de capex cableado y el desglose de la depreciacion por
unidad, que ya existia.

**No se implemento, por depender de una respuesta:** la tasa propia de los equipos de computo, el
tratamiento de lo no depreciable como deduccion entera, y el metodo de la depreciacion financiera,
que en el libro es por unidades de produccion sobre reservas y en el motor es lineal. Los tres estan
en `reglas-no-documentadas.md`.

## 9. Lo que la plantilla no pide, y no es un olvido

- **La etapa**, que se deriva.
- **Los totales**, por unidad y del caso, que se calculan.
- **El cruce etapa por naturaleza**, que se calcula.
- **Los dos `check`**, que con una sola clasificacion cargada se cumplen por construccion.
- **La cuarta etapa**, que el libro dejo sin rotular y sin formula.
