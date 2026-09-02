# Mapa N1 — correspondencia bloque de contraste a modulo del motor

El contraste de nivel N1 verifica los bloques intermedios ano a ano. Cada bloque tiene **un solo**
modulo responsable, de modo que una discrepancia se localiza en un archivo.

| Bloque del contraste N1 | Modulo | Prueba |
|---|---|---|
| Produccion y toneladas finas | `produccion.py` | `test_n1_bloques.py::test_produccion` |
| Metal pagable y deducciones | `ventas.py` | `test_n0_a_n3.py::TestN1::test_metal_pagable` |
| Ventas por metal | `ventas.py` | `test_n0_a_n3.py::TestN1::test_ventas_del_concentrado` |
| Cash cost | `cash_cost.py` | `::test_cash_cost` |
| Reservas | `produccion.py` | `::test_reservas` |
| EBITDA ajustado | `flujos.py` | `::test_ebitda` |
| Depreciacion tributaria y financiera, por mina | `depreciacion.py` | `::test_depreciacion` |
| EBIT | `flujos.py` | `::test_ebit` |
| Base imponible | `tributos.py` | `::test_base_imponible` |
| Impuestos | `tributos.py` | `::test_impuestos` |
| Regalias y aportes | `tributos.py` | `::test_regalias_aportes` |
| Utilidad neta | `flujos.py` | `::test_utilidad_neta` |
| CAPEX inicial por clasificacion | `capex.py` | `::test_capex_inicial` |
| CAPEX diferido y de sostenimiento | `capex.py` | `::test_capex_diferido` |
| Costos de cierre | `capex.py` | `::test_costos_cierre` |
| Valor residual | **No aplica.** Ver la nota 3 | |
| Capital de trabajo | `capital_trabajo.py` | `::test_working_capital` |

Las dos filas de ventas citan las pruebas que existen. Las trece restantes apuntan a un
`test_n1_bloques.py` que nunca se escribio: el contraste vive hoy en
`tests/fidelidad/niveles/test_n0_a_n3.py`. Queda registrado y se corrige al cerrar cada bloque.

Tolerancia N1: diferencia relativa hasta 0,1 % o absoluta hasta US$ 10 000 por linea y ano.
Valor provisional hasta que Finanzas cierre `R-31`. El estandar `DM-STD-PE-27` no fija tolerancias:
ver `estandar-dm-std-pe-27.md`.

**Cuatro lineas no se contrastan contra el modelo**, porque MINSUR pidio apartarse de el en esos
puntos. Estan en [desviaciones-acordadas.md](desviaciones-acordadas.md) con su tratamiento. Una
linea que difiera del modelo sin citar una desviacion sigue siendo un fallo.

---

## Contraste contra la hoja resumen de DM-STD-PE-27

Las secciones 5.1 y 5.2 del estandar corporativo especifican la hoja resumen que consolida el
analisis financiero. Es la unica descripcion escrita que MINSUR ha entregado de la salida esperada,
asi que el mapa de arriba se contrasta linea por linea contra ella.

| Linea de la hoja resumen | Bloque N1 | Modulo |
|---|---|---|
| Concentrate production | Produccion y toneladas finas | `produccion.py` |
| Payable Tin | Metal pagable y deducciones | `ventas.py` |
| Tin Price | Dato maestro, no linea calculada | `parametros.py` |
| Gross revenue, Total gross revenue | Ventas por metal | `ventas.py` |
| Net revenue | Metal pagable y deducciones | `ventas.py` |
| Mine, Plant, Tailings, Power Substation, G&A | Cash cost | `cash_cost.py` |
| Treatment and Refining Charges | **Ver nota 1** | `cash_cost.py` o `ventas.py` |
| Freight, port and insurance | **Ver nota 1** | `cash_cost.py` o `ventas.py` |
| Total operating cost | Cash cost | `cash_cost.py` |
| EBITDA | EBITDA ajustado | `flujos.py` |
| Depreciation | Depreciacion tributaria y financiera | `depreciacion.py` |
| EBIT | EBIT | `flujos.py` |
| Total Taxes | Impuestos | `tributos.py` |
| Net income | Utilidad neta | `flujos.py` |
| Sub total Directs, Indirects, Owners Cost, Contingency | CAPEX inicial por clasificacion | `capex.py` |
| Total initial capital cost | CAPEX inicial por clasificacion | `capex.py` |
| Total deferred capital cost | CAPEX diferido y de sostenimiento | `capex.py` |
| Sustaining capital | CAPEX diferido y de sostenimiento | `capex.py` |
| Closure costs | Costos de cierre | `capex.py` |
| Change in working capital | Capital de trabajo | `capital_trabajo.py` |
| Residual Value | **No aplica.** Ver la nota 3 | |
| Total capital cost | Suma de los anteriores | `capex.py` |
| CFO, CFI, CFF, Net Cash Flow | **Nivel N2**, no N1 | `flujos.py` |
| NPV of Net Cash Flow, IRR | **Nivel N3**, no N1 | `indicadores.py` |
| Financial Transaction Tax | Impuestos. **Ver nota 2** | `tributos.py` |
| Osinergmin Fee, OEFA Fee | Regalias y aportes | `tributos.py` |
| Miners' Retirement Fund | Regalias y aportes | `tributos.py` |
| Modified Mining Royalty and Special Mining Tax | Regalias y aportes. **Ver nota 2** | `tributos.py` |
| Workers Profit Share | Impuestos | `tributos.py` |
| Income tax | Impuestos | `tributos.py` |

### Que cambio en el mapa tras el contraste

Seis bloques del mapa anterior no existian y se agregaron: EBIT, utilidad neta, CAPEX inicial,
CAPEX diferido y de sostenimiento, costos de cierre y valor residual.

El caso de CAPEX merece atencion: `capex.py` estaba declarado como modulo del motor con
clasificacion triple por etapa, agrupacion y naturaleza, **pero no tenia ninguna linea en el
contraste N1**. Un modulo sin linea de contraste es un modulo cuyas discrepancias aparecen recien
en el flujo de inversiones (N2), donde ya se han sumado con otras y dejan de localizarse en un
archivo. Eso es exactamente lo que el nivel N1 existe para evitar.

### Nota 1 — clasificacion de cargos de tratamiento y fletes

El estandar clasifica *Treatment and Refining Charges* y *Freight, port and insurance* dentro de
**operating costs**. La descomposicion de modulos de este repositorio asigna las deducciones a
`ventas.py`, que calcula el ingreso neto restandolas del bruto.

Las dos clasificaciones producen el mismo flujo de caja, pero **reparten el valor entre dos lineas
de contraste distintas**: con una, el cash cost incluye TC/RC y fletes y el ingreso es bruto; con la
otra, el cash cost los excluye y el ingreso es neto. Contrastadas contra el modelo de referencia,
una de las dos dara diferencia en dos lineas de N1 que se compensan en N2.

Se resuelve observando que hace el modelo de referencia, no eligiendo. Pendiente de `R-02`.

### Nota 3 — el valor residual no existe en el modelo

Este mapa le asignaba una linea de contraste a `capex.py`, y `capex.py` nunca lo implemento. La
busqueda del 02/09/2026 sobre el libro —`InputsCapex`, `Otros`, `FC NZ` y `Resumen`— no encontro
ninguna fila que lo calcule.

Es una linea que la hoja resumen del estandar `DM-STD-PE-27` pide y que el modelo de referencia no
tiene. Manda el modelo: no se implementa, y la diferencia se reporta como discrepancia entre el
estandar y el modelo, con las demas de
[estandar-dm-std-pe-27.md](estandar-dm-std-pe-27.md).

### Nota 2 — lineas tributarias sin parametro registrado

*Financial Transaction Tax* y *Special Mining Tax* aparecen en la hoja resumen del estandar y no
tienen parametro en la capa de datos maestros. La regalia minera figura registrada, pero el estandar
la nombra junto al impuesto especial en una sola linea, y son dos tributos distintos con bases
distintas.

Sin confirmacion de Finanzas sobre cuales aplican al alcance de la plataforma (`R-32`), estas lineas
no se implementan. Ver `estandar-dm-std-pe-27.md`, punto 3.

---

## Lo que anade la minuta de Finanzas del 27/08/2026

Tres acuerdos cambian la estructura del contraste, no solo su contenido.

**Depreciacion por mina (acuerdo 8).** La linea deja de ser unica: el motor calcula depreciacion
tributaria y financiera separadas para cada mina, y el contraste verifica que la suma reproduzca el
consolidado del modelo. Ver `D-04`.

**OPEX extensible (acuerdo 6).** Santo Domingo tiene conceptos operativos que otros proyectos no
tienen. El bloque de cash cost admite filas adicionales definidas por el usuario, con una condicion
que lo mantiene contrastable: **solo impactan el total de OPEX y no alteran las formulas de otras
pestanas**. El contraste se hace sobre el total, no sobre la lista de conceptos.

**Reservas con doble logica (acuerdo 9).** En proyectos del LOM las reservas son un dato de entrada
editable, para permitir la conversion de recursos. En greenfield son un calculo derivado de hojas
previas. La linea de contraste es la misma; lo que cambia es si N0 la lee como input o N1 la
verifica como calculo, y eso depende del tipo de proyecto.
