# 0001. Python como lenguaje del motor y de los servicios

- Estado: aceptada
- Fecha: 24/08/2026
- Decide: Fernando Parodi Guerrero, Arquitectura y Desarrollo (ATI), MINSUR
- Restricción relacionada: `R-14`, constancia formal de la excepción tecnológica. Solicitada
  mediante `SOL-05`, con vencimiento el 28/08/2026.

## Contexto

El estándar tecnológico corporativo de MINSUR para desarrollo es .NET/C#. En la reunión de arranque
del 24/08/2026, Arquitectura y Desarrollo consultó por su uso en esta plataforma y confirmó Python
como excepción.

Lo que la plataforma tiene que hacer condiciona la elección. El motor reproduce con fidelidad la
lógica de un modelo económico corporativo y debe sostener un contraste en cuatro niveles, N0 a N3,
con tolerancias del orden de 0,1 % por línea y año. A eso se suman las simulaciones de sensibilidad,
escenarios y Montecarlo del frente de riesgo. Es cálculo numérico sobre series anuales, con
funciones financieras que deben coincidir cifra a cifra con las de un libro de Excel.

La decisión es previa a este registro y no lo espera: se tomó en el KOM y el desarrollo arrancó
sobre ella. Este ADR existe porque una excepción al estándar corporativo que solo consta en una
minuta es una excepción frágil.

## Decisión

El motor de cálculo y los servicios de aplicación se construyen en Python 3.12. La interfaz es
TypeScript, que no compite con el estándar porque este no cubre el frontend.

## Alternativas consideradas

**.NET/C#, el estándar corporativo.** Es la opción que no habría requerido excepción alguna, y por
eso mismo la que se consultó primero. Se descartó por la madurez del ecosistema numérico de Python
para cálculo financiero y simulación: NumPy, numpy-financial, pandas y SciPy cubren de fábrica las
funciones financieras, la aritmética sobre series y el muestreo, y son el terreno donde una
discrepancia con el modelo de referencia se diagnostica en horas y no en días. La equivalencia con
las funciones financieras de Excel es el criterio de aceptación del entregable, no una preferencia
de implementación.

Fue la única alternativa evaluada. La consulta del KOM planteó el estándar corporativo frente a
Python, y se resolvió ahí.

## Consecuencias

**La constancia de `R-14` es el punto abierto.** Mientras no exista por escrito, el registro de
riesgos del servicio mantiene abierta la posibilidad de que la decisión tecnológica se reabra
durante la homologación de seguridad, con el argumento de las vulnerabilidades en librerías de
terceros. Reabrirla en ese momento no es una discusión de criterio: la ventana de ethical hacking
va del 21/09 al 02/10, y para entonces el motor y su certificación de fidelidad ya están
construidos sobre esta base.

**El argumento de las vulnerabilidades está atendido por adelantado.** Arquitectura y Desarrollo
advirtió en el KOM que con Python y librerías de terceros es frecuente que aparezcan hallazgos, y
planteó priorizar críticas y altas antes de la salida en vivo, postergando medias y bajas. La
compuerta de las canalizaciones aplica exactamente ese criterio, y `pip-audit`, `Bandit` y `CodeQL`
corren en cada integración desde la semana 3, no en la homologación. La respuesta a una observación
de seguridad es un historial de análisis, no una promesa.

**El motor puro es una consecuencia de esta decisión, no una casualidad.** `packages/engine` no hace
E/S, no lee Excel y no toca red ni base de datos. Eso es lo que permite ejecutarlo contra el modelo
de referencia sin levantar la plataforma, y es la condición del contraste N0-N3.

**La transferencia exige competencia en Python.** Al cierre del servicio, MINSUR recibe el código
bajo su titularidad y lo mantiene. El equipo que lo sostenga necesita el lenguaje que aquí se
excepciona, y no el del estándar corporativo. El manual técnico y de operación (E08) y la
capacitación (E10) se dimensionan con ese supuesto.

**No se reabre.** La decisión está tomada y el desarrollo depende de ella. Una discusión nueva sobre
el lenguaje se registra como un ADR que supersede a este, con su propio análisis de impacto sobre el
cronograma, y no como una revisión de este documento.
