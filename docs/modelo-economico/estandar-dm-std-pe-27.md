# Estandar DM-STD-PE-27 — implicaciones para el motor

`DM-STD-PE-27` Rev. 0 (15/12/2016), *Project Standard for Economic Evaluation*, Division Minera,
proceso de Proyectos de Expansion. Recibido de MINSUR el 26/08/2026. Ejemplar en
`00-gestion/03-insumos-minsur/estandar-evaluacion-inversion/`.

Es el marco metodologico corporativo de evaluacion de inversiones. **No sustituye al modelo de
referencia**: el modelo es la implementacion vigente y es lo que el motor reproduce. El estandar
dice como deberia calcularse. Donde los dos difieran, gana el modelo y la diferencia se registra
como discrepancia, conforme a la regla de fidelidad.

Este documento recoge lo que el estandar exige y que hoy no esta especificado en nuestro arbol.
Cada punto indica el modulo afectado y si esta confirmado contra el modelo de referencia.

Ningun punto marcado como pendiente de confirmacion se implementa hasta que Finanzas responda.
Las consultas estan en `00-gestion/03-insumos-minsur/estandar-evaluacion-inversion/`.

## 1. Descuento a mitad de ano

> *"the cash flows during each year of the forecast should be discounted back from the mid year to
> time zero for non seasonal business such as mining business"* (seccion 5.1)

El factor de descuento es `(1 + r) ** -(t - 0,5)`, no `(1 + r) ** -t`.

Sobre un perfil de flujos tipico la diferencia entre ambas convenciones supera holgadamente la
tolerancia de 0,1 % que se propone para N3. No es un matiz de redondeo: es una convencion distinta.

- Modulo: `indicadores.py`
- Estado: **contrastado y resuelto el 03/09/2026.** El modelo vigente no aplica mitad de ano: usa
  `t` entero desde el primer ejercicio, que es la regla `005`, confirmada por Finanzas el
  01/09/2026. Dos evaluaciones historicas -`Nazareth Dic_24` y `Santo Domingo 17.12`- si la aplican,
  y ademas contra una fecha base posterior. El motor reproduce la cosecha vigente por el
  [ADR 0010](../adr/0010-convencion-de-descuento.md) y **la discrepancia con la seccion 5.1 queda
  reportada**, no corregida: tiene que aparecer en la certificacion de H6.

## 2. Fecha de valuacion y costos hundidos

> *"For Minsur projects it shall be when the project is sanctioned at tollgate 3. Previous negative
> cash flows (expenses/ investments) should be considered sunk cost and should not be considered as
> part of the Discounted Cash Flow."* (seccion 5)

La fecha de valuacion es la sancion en tollgate 3. Todo flujo negativo anterior queda fuera del DCF,
con tres excepciones explicitas: pre-compromisos, adquisicion de terrenos y gastos de reasentamiento.

- Modulo: `horizonte.py`
- Estado: pendiente de confirmar como determina el modelo el ano de valuacion.

## 3. Lineas tributarias ausentes en la capa de parametros

La hoja resumen del estandar lista siete lineas tributarias. Tres no figuran en la capa de
parametros maestros ni en `CLAUDE.md`:

| Linea del estandar | Situacion |
|---|---|
| Financial Transaction Tax (ITF) | Ausente |
| Special Mining Tax (IEM) | Ausente. Solo se registra la regalia minera |
| Withholding tax sobre dividendos al exterior | Ausente. Aplica al nivel Shareholder Value |
| Modified Mining Royalty | Registrada como regalia minima 1 % |
| Workers Profit Share | Registrada, 8 % |
| Income tax | Registrado, 29,5 % |
| Osinergmin, OEFA, Fondo de jubilacion minera | Registrados |

- Modulo: `impuestos.py`, `parametros.py`
- Estado: pendiente de que Finanzas confirme cuales aplican al alcance de la plataforma (`R-32`).

## 4. Los tributos se calculan en terminos nominales

> *"tax calculations must be fixed in nominal terms. If the calculations are in constant terms, the
> tax calculations will be underestimated because some taxes such as Mining royalties and the
> extraordinary tax for Mining activities are calculated using rates that apply to different
> segments of the operating margin rate, so constant money valuations overestimate NPV value"*
> (seccion 6.3)

El motivo es que la regalia y el IEM aplican tasas por tramos del margen operativo. Calcularlos en
moneda constante subestima el impuesto y **sobreestima el NPV**.

El estandar separa tres registros que hoy el motor no distingue:

- Los calculos tributarios se hacen en terminos nominales.
- Regalias y depreciacion son calculos nominales que despues se deflactan a terminos reales.
- El reporte se presenta en US$ reales, que es donde el lector detecta anomalias de precio, costo
  unitario y margen.

Esto obliga a llevar dos escalas en paralelo dentro del calculo, no a convertir al final.

- Modulos: `impuestos.py`, `depreciacion.py`, `flujos.py`
- Estado: pendiente de confirmar si el modelo de referencia opera asi.

## 5. Tres niveles de valor

| Nivel | Definicion del estandar |
|---|---|
| Asset Value | Valor total de los activos del proyecto. **Es el caso base de la evaluacion** |
| Minsur Local Value | Asset Value menos el valor atribuible a socios y deuda pendiente, ajustado por management fees |
| Minsur Shareholder Value | Minsur Local Value ajustado por withholding taxes, ITF sobre dividendos, impuesto corporativo offshore y management fees |

El alcance actual de la plataforma asume un unico nivel. El caso base del estandar es Asset Value,
que es el que corresponde a una evaluacion preliminar de proyecto.

- Estado: no requiere accion inmediata. Se documenta para que el alcance no se amplie por inercia.

## 6. Escenarios de precio: tres son el minimo

> *"The minimum requirement is to consider three price scenarios: Base Case Scenario, Upside
> Scenario, and Downside Scenario."* (seccion 5.1)

Los tres escenarios no son una funcionalidad opcional del modulo de riesgo: son requisito del
entregable de evaluacion en todas las fases del proyecto.

- Modulo: `risk/`
- Estado: afecta el alcance de PT5. Confirmar con el Product Owner.

## 7. Definiciones que fijan los indicadores

- **Payback.** *"can be calculated either in real or (preferably) discounted terms"*. El estandar
  prefiere el descontado. `CLAUDE.md` y `mapa-n1.md` fijan una tolerancia de 0,1 ano sin decir cual
  de los dos se contrasta.
- **Capital Intensity.** Capex inicial total dividido entre las ventas del proyecto.
- **TIR.** *"IRR calculations cannot be relied on for any estimated cash flows which contain more
  than one change in sign"*. Con mas de un cambio de signo hay que evaluar si usar TIR multiple o
  MIRR. El motor debe detectar la condicion y declararla, no devolver un numero como si fuera unico.

- Modulo: `indicadores.py`

## 8. Especificacion del analisis de riesgo

El estandar define el contenido de PT5, que hasta ahora estaba descrito solo por el Plan de Trabajo:

- **Determinista (seccion 7.1).** Tres casos: peor, mejor y mas probable. En el peor todos los
  costos toman su valor mas alto y los ingresos su proyeccion mas baja; en el mejor, a la inversa.
- **Sensibilidad (seccion 7.2).** Diagramas de tornado y de arana son **requeridos**. El metodo es
  variar una variable dentro de su rango con las demas fijas en su valor base, con rangos de
  variacion definidos como porcentaje y con valores bajo, base y alto.
- **Montecarlo (seccion 7.3).** Distribuciones normal, lognormal, uniforme, triangular, PERT y
  discreta, con correlaciones entre variables. Variables sensibles citadas: precio del metal,
  recuperacion metalurgica, costo de capital y costo operativo.
- **Metricas de salida (seccion 7.3).** Probabilidad del punto de equilibrio, media del NPV, y
  probabilidad de alcanzar el NPV base sin riesgo. Los percentiles 5 % extremos se descartan al
  definir el rango esperado.

- Modulo: `risk/`

## Defecto detectado en el documento fuente

El glosario define el escenario **Upside** como *"The lowest long term metal price approved in the
document endorsement of financial parameters is considered"*, texto identico al de **Downside**.
Por definicion el escenario alcista debe tomar el precio mas alto aprobado.

Es un error de copia en el estandar de MINSUR, no una regla. Conforme a la regla de fidelidad se
documenta y se reporta; no se corrige por cuenta propia. La consulta esta emitida.

## Lo que el estandar no resuelve

**No fija tolerancias de contraste ni criterios de aceptacion numericos.** No contiene ningun umbral
de diferencia aceptable entre una implementacion y el modelo. Los umbrales de `mapa-n1.md` siguen
siendo propuesta de INVA y `R-31` sigue abierta.

Tampoco fija el formato de la plantilla de inputs (`R-07`) ni la estructura del libro corporativo:
describe la hoja resumen de salida, no las hojas de calculo intermedias.
