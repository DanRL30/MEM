# Brechas de la plantilla de OPEX

Auditoria fila a fila de la hoja `InputsOpex` del libro corporativo contra lo que emitia
`generar_plantilla_inputs.py` y lo que reconocia `plantilla.py`. Repite el metodo de
[brechas-plantilla-produccion.md](brechas-plantilla-produccion.md), que es el que dejo ver que 63
de las 94 filas de `InputsProd` no tenian concepto en la plantilla.

Fecha de la lectura: 02/09/2026. Las formulas y las cifras del libro estan en el informe de
diseccion, en `00-gestion/03-insumos-minsur/`; aqui va la estructura y el vocabulario, que es lo que
el codigo necesita.

## 1. Las cinco cifras

| Medida | Valor |
|---|---|
| Filas con etiqueta en `InputsOpex` | 143 |
| Filas de concepto de cash cost, sumadas las seis unidades | 54 |
| Conceptos distintos de cash cost en el libro, ya traducidos | 21 |
| Conceptos que emitia la plantilla anterior | 18 |
| Conceptos del libro que la plantilla no sabia nombrar | 7 |
| Conceptos de la plantilla ubicados en el bloque equivocado | 3 |
| Conceptos que el catalogo recoge, tras la revision del 02/09/2026 | 14 |

Los 7 sin nombrar no son 7 conceptos olvidados: cinco son de Santo Domingo y del complejo y dos son
abreviaturas del libro sobre conceptos que la plantilla ya tenia. Esa distincion cambia el trabajo,
igual que en produccion.

Del libro al catalogo no hay correspondencia uno a uno, y tampoco la pretende: **siete conceptos se
dejaron fuera a proposito** en la revision del 02/09/2026. Ver la seccion 9.

## 2. La forma real de la hoja

Cuatro zonas, y solo la primera y la cuarta son plantilla.

| Filas | Bloque | Clasificacion |
|---|---|---|
| 7-15, 20, 24-33, 37-46, 50-63, 67-75 | Cash cost por concepto, seis unidades | **Dato** |
| 17, 21, 34, 47, 64, 76, 86, 88 | Totales por unidad y total general | Calculo |
| 79-84 | Costo por tonelada del complejo, su recuperacion y sus subtotales | Calculo |
| 91-97 | Produccion de cada unidad | Calculo, desde `InputsProd` |
| 99-123 | Cash cost unitario, `$/tt` y `$/tmf` | Calculo, regla `008` |
| 126-134, 137-146, 150-158, 161-170 | Gastos, cuatro unidades | **Dato**, salvo tres filas |
| 173-182 | Total de gastos | Calculo |

Las seis unidades del bloque de cash cost tienen conceptos distintos: San Rafael diez, B2 uno,
Nazareth diez, San Rafael Potencial diez, Santo Domingo catorce y el complejo nueve.

**El criterio que separa dato de calculo es el acordado el 01/09/2026**: una celda es input si no
tiene formula o si su formula solo referencia libros externos. Aplicado aqui da un resultado que
conviene decir en voz alta: **en `InputsOpex` casi no hay constantes tecleadas.** El dato entra
como formula de enlace externo a otros cuatro libros, y las unicas constantes son ceros. Leer la
hoja buscando valores literales la habria dado por vacia.

## 3. Las brechas, en cuatro clases

Cada clase se cierra en un archivo distinto, y por eso se separan.

**Clase 1 — posicional.** La etiqueta `Exploraciones` aparece dos veces en la misma pestana, una en
el cash cost y otra en los gastos, y `Mantenimiento` tres veces con calificativos distintos. Ninguna
tabla de sinonimos las distingue: solo la posicion. Se cierra leyendo por secuencia, que es lo que
hace `minsur_ingest/opex.py`.

**Clase 2 — sinonimos sobre conceptos que ya existen.** El libro abrevia: `LT`, `Pta Subproductos`,
`Mantenimiento F&R`, `Peajes / Mantenimiento`. Se cierra en `sinonimos.py`, y solo para los que el
catalogo conserva.

**Clase 3 — alias de unidad dentro del concepto.** `Tratamiento de Relaves B2` y `Preconcentrado
Blue Sky` llevan el nombre propio de una unidad pegado al concepto, y no se pueden generalizar
quitando un sufijo. El primero se cierra en `sinonimos.py`, con la entrada literal, y el catalogo se
queda con el concepto generico: un proyecto nuevo no tiene una relavera llamada B2. El segundo salio
del catalogo en la revision del 02/09/2026.

**Clase 4 — conceptos genuinamente ausentes.** `STA` y el bloque de gastos entero. Los gastos son
los que exigieron cambiar el modelo de datos, no la traduccion: no cabian en `UnidadProductiva`, que
solo tenia `costos`.

## 4. Lo que la plantilla emitia y el libro no tiene ahi

Tres conceptos estaban en el bloque equivocado:

- `Planilla` no es cash cost ni es dato: el libro la deriva del cash cost de la unidad por la tasa
  de `Supuestos`. Es la regla `026`.
- `Gestion social` y `Predios, servidumbres y usufructos` son del bloque de gastos, no del cash
  cost, y el libro separa los predios de las servidumbres en dos filas.

El catalogo de inputs los llevaba a los tres como costo operativo. Corregido en su seccion 4.2.

## 5. Lo que se leia y se tiraba

La plantilla anterior escribia **una sola hoja `Opex` con las unidades apiladas** y filtraba las
filas por etapa: una unidad sin preconcentracion no recibia esa fila. La estructura dependia asi de
la unidad, que es exactamente lo contrario de lo que produccion resolvio en septiembre. La lectura
emparejaba fila con unidad por el prefijo de la seccion, de modo que dos unidades cuyo nombre
empezara igual se mezclaban sin aviso.

Un fallo silencioso mas, y del mismo tipo que el `continue` de produccion: **una fila de la cola con
importes y sin concepto se saltaba entera**. El costo desaparecia del total y nada lo acusaba. Hoy
se reporta con su celda.

## 6. Lo que ningun documento dice, y es consulta

1. **Que es `STA`.** Ninguna fuente del arbol lo traduce. Se conserva literal en el catalogo.
2. **Si un `Estudios` sin calificar es capitalizable.** El libro lo trata asi —la hoja
   `Depreciacion` lee esa fila de San Rafael— mientras Nazareth y Santo Domingo la parten en gasto y
   capitalizable. La eleccion cambia la base imponible. Regla `028`.
3. **Que fraccion de la gestion social es deducible.** El libro copia la fila entera salvo en dos
   escenarios, donde la afecta por 0,85 sin explicar por que. Regla `027`.
4. **A que tasa se deprecia el estudio capitalizable.** El libro lo manda a `Depreciacion` sin
   asignarle naturaleza contable. Hasta saberlo, la plataforma lo trata como salida de caja y no lo
   deduce, y su depreciacion queda pendiente. Va con la plantilla de CAPEX.

## 7. Donde se corrige cada brecha

| Brecha | Se corrige en |
|---|---|
| Estructura distinta por unidad | `scripts/generar_plantilla_inputs.py`, con una estructura unica |
| Etiquetas repetidas en la misma pestana | `minsur_ingest/opex.py`, leyendo por secuencia |
| Abreviaturas y alias de unidad | `minsur_ingest/sinonimos.py` |
| Conceptos ausentes | `minsur_ingest/opex.py` y el catalogo |
| Gastos sin sitio en el modelo de datos | `minsur_engine/caso.py`, campo `gastos` de la unidad |
| Filas derivadas pedidas como dato | `minsur_engine/cash_cost.py` |
| Miles de dolares rotulados `$k` | `minsur_ingest/plantilla.py`, tabla de escalas |

La ultima merece una nota. La tabla de escalas reconocia `k$`, que es como lo escribe la hoja de
depreciacion, y no `$k`, que es como lo escribe `InputsOpex`. Una plantilla de opex leida con esa
tabla entraba mil veces mas pequena **sin una sola incidencia**. Lo detecto la primera prueba de ida
y vuelta del bloque, y es la regla `003` cobrandose su tercera victima.

## 8. Estado

Cerrado el 02/09/2026: la estructura unica, la cola extensible del acuerdo 6, el bloque de gastos
con su reparto por destino, las dos filas derivadas y el desglose del cash cost por unidad.

**No se implemento, por depender de una respuesta:** la depreciacion del estudio capitalizable
(punto 4 de la seccion 6) y el costo del complejo derivado del costo por tonelada. Lo segundo es
como el libro rellena lo que no carga, y desde la revision del 02/09/2026 vuelve a estar sobre la
mesa: el complejo ya no tiene en la plantilla sus cuatro lineas propias. Se decide con Finanzas
junto con la plantilla, en la sesion del acuerdo 10.

## 9. Los siete conceptos que quedan fuera a proposito

Revision del 02/09/2026, decidida por el Project Manager sobre la primera version de la plantilla.
No son omisiones: el libro los tiene y el catalogo no.

| Concepto del libro | Por que sale |
|---|---|
| `Fundicion` | Linea propia del complejo |
| `Refineria` | Linea propia del complejo |
| `Pta Subproductos` | Linea propia del complejo |
| `Mantenimiento F&R` | Linea propia del complejo |
| `Servicios Mina` | Solo Santo Domingo lo distingue de `Mina` |
| `Preconcentrado Blue Sky` | Lleva el nombre de un tercero, y solo Santo Domingo lo tiene |
| `Planillas` | **No es un dato**: es la planilla, que se deriva del cash cost de la unidad |

Las seis primeras siguen siendo cargables: van por la cola de conceptos propios, que existe
precisamente para lo que una unidad tiene y el catalogo no recoge. La septima no vuelve por ningun
camino, porque pedirla como dato es lo que la regla `026` prohibe.

**El complejo queda con los conceptos genericos.** Su pestana sigue existiendo —su costo es dato,
no resultado— pero lo que carga son mantenimiento, energia, apoyo y estudios, mas lo que su cola
recoja. Si Finanzas prefiere derivar su costo del costo por tonelada, como hace el libro para las
unidades sin bloque, la pestana deja de tener sentido y se retira; hasta entonces se mantiene, que
es lo unico que no pierde informacion.
