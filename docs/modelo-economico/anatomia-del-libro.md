# Anatomia del libro de referencia

Como esta construido el modelo economico corporativo: que hace cada hoja, como selecciona el caso a
evaluar, por donde circulan los datos y en que estado esta. Es el mapa que hay que tener en la
cabeza antes de escribir una linea del motor.

**Este documento no contiene cifras del modelo.** Describe estructura: hojas, formas, referencias y
recuentos. Las formulas y los valores viven en el informe de diseccion, que hereda la
clasificacion del modelo y se archiva en `00-gestion/03-insumos-minsur/`, fuera del repositorio.

Archivo analizado: `Modelo Nazareth Abr_26 + Santo Domingo 11.05 (MOD).xlsx`, recibido el
31/08/2026. Identidad y hash en
[fixtures/certificados/libro-corporativo/manifiesto.json](../../fixtures/certificados/libro-corporativo/manifiesto.json).
Finanzas confirmo su vigencia el 01/09/2026: el sufijo `(MOD)` corresponde a datos modificados por
confidencialidad y las formulas son las correctas. **De ahi se sigue algo que condiciona todo el
contraste: este archivo sirve para contrastar logica, no cifras.** El contraste numerico N1-N3 se
ejecuta contra los casos certificados dentro del tenant (`R-30`).

---

## 1. La cifra que dimensiona el trabajo

| Metrica | Valor |
|---|---|
| Hojas | 25, de las cuales 8 ocultas |
| Celdas con contenido | 232 613 |
| Celdas con formula | 216 223 |
| **Reglas unicas a reproducir** | **342** |
| Constantes incrustadas en formulas | 26 490 |
| Referencias a libros externos | 13 123 formulas hacia 13 libros |
| Macros VBA | ninguna |

Las 216 223 formulas son 342 reglas arrastradas sobre casos y anos. Una formula copiada sobre
treinta y seis columnas son treinta y seis celdas y una sola regla. **342 es el tamano real del
motor**; 216 223 es el tamano de la hoja de calculo, que es otra cosa.

## 2. Las 25 hojas por rol

| Rol | Hojas | Que hacen |
|---|---|---|
| Gobierno | `Control` | Selector de caso y de escenario de precios, parametros corporativos, catalogo de casos |
| Entrada por bandas | `InputsProd`, `InputsOpex`, `InputsCapex`, `Depreciacion` | Un bloque de columnas por caso; de ahi sale casi todo el volumen |
| Supuestos | `Supuestos`, `Inputs` (oculta) | Series de supuestos y el control de fuente y estado por proyecto |
| Calculo por ano | `Ventas`, `Otros`, `Impuestos`, `FC NZ`, `FC escenarios`, `Evolutivos` | Ancho de horizonte (43 a 45 columnas), una columna por ano |
| Salida | `Resumen`, `Resumen (2)` (oculta), `WF`, `WF (2)`, `WF Costos` (oculta), `Informe` (oculta), `Ppt` (oculta) | Consolidan y presentan; no alimentan el calculo |
| Riesgo | `Sensibilidad`, `Tornado` (oculta), `RiskSerializationData8` (oculta) | Analisis con @RISK de Palisade |
| Historico | `Resumen_Original`, `Revision` (ocultas) | Restos de versiones anteriores, sin formulas vivas |

La forma de cada hoja distingue su papel mejor que su nombre: **si mide unas 43 columnas, es
calculo por ano; si mide 1 870, es almacen de casos.**

| Hoja | Filas | Columnas | Formulas | Reglas unicas |
|---|---|---|---|---|
| `Depreciacion` | 1 433 | 1 870 | 58 767 | 55 |
| `InputsOpex` | 191 | 462 | 41 297 | 41 |
| `InputsProd` | 147 | 1 872 | 29 347 | 30 |
| `InputsCapex` | 125 | 1 871 | 23 560 | 33 |
| `FC escenarios` | 182 | 427 | 19 010 | 25 |
| `Ppt` | 94 | 1 832 | 22 947 | 43 |
| `Resumen` | 249 | 35 | 2 497 | 59 |
| `Impuestos` | 109 | 43 | 3 098 | 21 |
| `Ventas` | 218 | 44 | 1 614 | 20 |
| `FC NZ` | 55 | 43 | 1 178 | 22 |
| `Control` | 47 | 27 | 71 | 9 |

## 3. Como el libro elige que proyecto evalua

Este es el mecanismo central, y el que la plataforma tiene que sustituir.

```
Control!$G$7  (indice del caso, 1 a 48)
      |
      +--> CHOOSE(Control!$G$7, banda_1, banda_2, ..., banda_48)   10 933 veces
                     |
                     +--> cada banda: 38 columnas consecutivas de InputsProd,
                          InputsOpex, InputsCapex y Depreciacion
```

- Las bandas empiezan en la columna 46 y se repiten cada 38 columnas hasta la 1 832. Son
  **48 bandas exactas**, y por eso las hojas de entrada miden 1 870 columnas.
- El catalogo de casos vive en `Control!N7:Q54`: numero, nombre, abreviatura y categoria.
  **Hoy hay 9 casos con nombre**; los indices restantes estan numerados y vacios, reservados para
  casos futuros.
- `Control!I7` compone el nombre visible del caso con tres `VLOOKUP` sobre ese catalogo.
- Un segundo selector, `Control!$G$8`, elige el **escenario de precios** sobre `Control!Y7:Z14`.

Dos consecuencias que importan para el diseno:

1. **Agregar un proyecto nuevo hoy significa llenar a mano una banda de 38 columnas en cuatro
   hojas**, y confiar en que las 342 reglas la referencien igual que a las demas. El libro reserva
   39 bandas vacias precisamente porque anadir una fuera del molde no es viable.
2. **Los casos no son independientes entre si.** Comparten las mismas reglas y el mismo horizonte;
   lo unico que cambia es la banda de datos. Esa es la propiedad que la plataforma conserva cuando
   sustituye las bandas por un caso con su version de inputs.

## 4. Por donde circulan los datos

Aristas principales del grafo de dependencias, medidas en numero de referencias:

```
InputsCapex  --22032-->  Depreciacion
InputsProd   -- 3289-->  InputsOpex
Supuestos    -- 2576-->  Depreciacion
Control      -- 1404-->  FC escenarios
InputsProd   --  780-->  Evolutivos
Supuestos    --  682-->  InputsProd
Supuestos    --  612-->  Ventas
FC NZ        --  560-->  FC escenarios
FC NZ        --  359-->  Impuestos
InputsOpex   --  576-->  Otros
```

Dos lecturas:

- **`Depreciacion` es el nudo del libro.** Concentra 58 767 formulas y 22 032 referencias a
  `InputsCapex`. No es casualidad que la desviacion acordada con mas alcance sea la depreciacion
  separada por mina (`D-04`).
- **`Ppt` consume y no produce.** Sus 22 947 formulas leen de todas partes y nadie lee de ella.
  Junto con `Informe`, `WF*` y `Tornado` forma la capa de presentacion, que la plataforma
  reemplaza por sus propias vistas y **no** necesita reproducir formula a formula.

## 5. Calculo iterativo: la circularidad es deliberada

El libro tiene `iterate=1` en su configuracion de calculo. No es un accidente, y al derivar la hoja
`Impuestos` el 01/09/2026 se vio cual es el lazo exacto: **lo cierra el fondo de jubilacion
minera**, que es gasto deducible de la misma utilidad operativa que sirve de base para calcularlo.

    utilidad operativa --> margen --> regalia e IEM --> utilidad imponible
           ^                                                  |
           +------------- fondo de jubilacion minera ---------+

La participacion de trabajadores y el impuesto a la renta **no** realimentan: cuelgan del final de
la cadena y nadie los vuelve a leer. Conviene decirlo porque la suposicion contraria es natural y
lleva a buscar el ciclo donde no esta.

El motor no reproduce esa aproximacion. El subsistema es afin a trozos y tiene solucion exacta, asi
que se resuelve en forma cerrada y no se itera: lo decide
[ADR 0009](../adr/0009-resolucion-de-la-circularidad-tributaria.md), por delegacion expresa de
Finanzas el 01/09/2026. El criterio de parada de Excel viaja con la instalacion y no con el archivo,
de modo que heredarlo habria hecho que el ultimo decimal de cada indicador dependiera de la maquina
donde se calculo.

El libro tambien trae `calcOnSave=0`: los valores guardados pueden no corresponder a las formulas
guardadas. **Ningun contraste puede apoyarse en los valores almacenados sin recalcular primero.**

## 6. Estado de salud del libro

| Hallazgo | Cantidad | Donde se concentra | Lectura |
|---|---|---|---|
| Formulas rotas (`#REF!`) | 9 976 | 9 679 en `Ppt`, 290 en `Resumen (2)` | Restos de presentacion, no calculo vivo |
| Errores silenciados (`IFERROR`) | 8 712 | 5 661 en `InputsOpex`, 684 en `Impuestos` | Enmascaran fallos: hay que saber que ocultan |
| Constantes incrustadas | 26 490 | Reparto amplio, 7 383 en `FC escenarios` | La principal fuente de reglas no documentadas |
| Redondeos explicitos | 105 | **todos en `Depreciacion`** | El redondeo es local, no una convencion global |
| Referencias externas | 13 123 | `InputsOpex`, `InputsCapex`, `InputsProd` | Son los futuros inputs de la plataforma |

Los dos primeros cambian de gravedad al mirar donde caen. **Las hojas que alimentan el flujo estan
sanas**: solo 2 de las 9 976 formulas rotas viven fuera de la capa de presentacion. Un `#REF!` en
`Ppt` no afecta a un indicador; habria sido muy distinto encontrarlos en `Impuestos`.

Los 684 `IFERROR` de `Impuestos` si merecen revision individual: un error silenciado en una tasa
efectiva devuelve un tributo nulo sin avisar.

Que el redondeo aparezca solo en `Depreciacion` es una noticia buena y precisa: el motor reproduce
un redondeo en un modulo y trabaja en precision completa en los demas.

## 7. Que ignora el motor y que reproduce

| Hojas | Trato en el motor |
|---|---|
| `Control`, `Supuestos`, `Inputs*`, `Depreciacion`, `Ventas`, `Otros`, `Impuestos`, `FC NZ`, `FC escenarios`, `Evolutivos` | Se reproducen. Son las 342 reglas y las lineas del contraste N1 |
| `Resumen`, `Resumen (2)` | Se reproducen como salida, y sirven de referencia para N2 y N3 |
| `Ppt`, `Informe`, `WF`, `WF (2)`, `WF Costos`, `Tornado` | No se reproducen. Presentacion, sustituida por las vistas de la plataforma |
| `RiskSerializationData8` | No se reproduce. Es estado interno de @RISK |
| `Resumen_Original`, `Revision` | No se reproducen. Historico sin formulas vivas |

El analisis de riesgo es caso aparte: hoy lo resuelve **@RISK de Palisade**, un complemento
comercial. Los 77 nombres definidos del libro son todos configuracion de @RISK y **ninguno es un
nombre de negocio**. El libro no tiene capa semantica: cada regla se expresa en referencias de
celda. PT5 no traduce formulas, reimplementa el metodo.

## 8. Lo que queda por confirmar con Finanzas

1. **Los 39 casos reservados.** Si las bandas vacias responden a un plan de casos futuros que
   convenga conocer antes de fijar el modelo estandar.
2. **El escenario de precios `xxx`** del selector secundario, que no tiene nombre asignado.
3. **Santo Domingo entra doce anos antes en los casos 2038 que en los 2032.** Puede ser deliberado y
   puede ser un arrastre al armar las bandas. Ver la seccion 6 de
   [modelo-estandar.md](modelo-estandar.md).

Resueltas el 01/09/2026: la vigencia del archivo, los `IFERROR` de `Impuestos` — cero es el
resultado esperado y una indeterminacion no detiene el calculo —, el tope de capacidad, el redondeo
de depreciacion y el criterio de la circularidad. Ninguna de las tres abiertas bloquea el motor.
