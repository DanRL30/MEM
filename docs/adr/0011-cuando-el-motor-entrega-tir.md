# 0011. La TIR se entrega solo con desembolso inicial y raíz no negativa

- Estado: aceptada
- Fecha: 03/09/2026
- Decide: Project Manager de INVA
- Restricción relacionada: reglas `064` y `075` de
  [reglas-no-documentadas.md](../modelo-economico/reglas-no-documentadas.md)

## Contexto

Seis hojas de flujo contrastadas contra el motor se reparten en dos grupos limpios.

Las tres del modelo vigente describen **operaciones en marcha**: el flujo abre en positivo y solo
baja de cero en los ejercicios de cierre. Tienen un único cambio de signo y su única raíz del NPV
queda entre el −49 % y el −58 %. El libro no publica TIR en ninguna: su `IRR` no converge desde la
semilla de Excel y el `IFERROR` escribe un guion.

Las tres de las evaluaciones históricas describen **inversiones**: abren con desembolso, tienen dos
o tres cambios de signo y una raíz no negativa —una de ellas con una segunda raíz en el −72 %—. El
libro sí publica la TIR de las tres, y el motor la reproduce hasta el décimo decimal.

Hasta el 03/09/2026 el motor entregaba la raíz que encontrara, incluida la profundamente negativa
de las tres primeras. Una tasa del −49 % no es una rentabilidad: es el punto donde una serie sin
inversión cruza el eje por construcción, y presentarla en el tablero como «TIR del caso» induce a
error sobre un caso que el modelo declara sin TIR.

## Decisión

`tir()` entrega la tasa **solo si el primer ejercicio con movimiento es un desembolso y existe al
menos una raíz no negativa**; entre varias, la menor, que es la primera tasa a la que el caso deja
de crear valor. En cualquier otro supuesto declara que el caso no tiene TIR, y quien la pida recibe
el motivo en lugar de un número.

## Alternativas consideradas

- **Entregar la raíz aunque sea negativa**, que era el comportamiento anterior. Descartada: no
  describe una rentabilidad y contradice lo que el propio modelo reporta.
- **Reproducir la semilla de Excel y entregar lo que converja.** Descartada por el mismo criterio
  del [ADR 0009](0009-resolucion-de-la-circularidad-tributaria.md): el resultado dependería de la
  configuración de la aplicación y no sería reproducible a cinco años.
- **Acotar la búsqueda a tasas no negativas.** Equivalente en el resultado, pero pierde la
  información de que la raíz existe y está fuera del rango razonable, que es lo que permite explicar
  el vacío en vez de solo declararlo.

## Consecuencias

- Las seis hojas contrastadas coinciden con el libro: tres entregan la misma tasa y tres coinciden
  en no entregar ninguna.
- **Un caso con desembolso cuya única raíz es negativa —una inversión que no se recupera— pasa a
  informarse como «sin TIR».** Es el único supuesto en que la plataforma calla un número que Excel
  daría, y el NPV es el que declara la pérdida. Si Finanzas pide verlo, la excepción entra por la
  misma puerta y con su regla escrita.
- La API y la interfaz deben mostrar el vacío **con su motivo**, no como un cero ni como un guion
  sin explicación. `Indicadores.tir` es opcional justamente para eso.
