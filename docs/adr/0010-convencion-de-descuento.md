# 0010. Descuento a fin de año, con la convención del modelo vigente

- Estado: aceptada
- Fecha: 03/09/2026
- Decide: Project Manager de INVA
- Restricción relacionada: regla `005` de
  [reglas-no-documentadas.md](../modelo-economico/reglas-no-documentadas.md) y
  [`DM-STD-PE-27` §5.1](../modelo-economico/estandar-dm-std-pe-27.md)

## Contexto

El contraste de dos evaluaciones históricas —`Nazareth Dic_24` y `Santo Domingo 17.12`— mostró que
esos libros **descuentan a mitad de año contra una fecha base posterior al inicio del horizonte**.
Sus exponentes van de −7,5 a 27,5 en una hoja y de −6,5 a 28,5 en otra: los ejercicios anteriores a
la base no se descuentan, se capitalizan, y su factor es mayor que uno.

Es lo que pide el estándar corporativo en su sección 5.1 y es lo que **el modelo vigente no hace**.
El `Abr_26` descuenta `1/(1 + r)^t` con `t` entero desde el primer ejercicio del horizonte, que es
la regla `005`, confirmada por Finanzas el 01/09/2026.

La evidencia importa porque invierte el sentido de la discrepancia: la convención del estándar no es
una exigencia que nadie haya aplicado nunca, es una práctica que existía en 2024 y que el modelo
vigente abandonó. Eso la vuelve una pregunta legítima para la certificación, no un tecnicismo.

Sobre las dos hojas históricas, la diferencia entre el NPV que calcula el motor y el que publica el
libro es **exactamente el factor de traslado de la fecha base**, `(1 + r)` elevado al exponente del
primer ejercicio. No hay ninguna otra diferencia: las cuatro líneas del flujo coinciden ejercicio a
ejercicio en las dos.

## Decisión

El motor descuenta **a fin de año, con `t` entero desde el primer ejercicio del caso**, y no
implementa la convención de mitad de año ni una fecha base distinta del inicio del horizonte.

## Alternativas consideradas

- **Adoptar mitad de año por seguir el estándar.** Descartada: la jerarquía del servicio pone el
  modelo por encima del estándar. `DM-STD-PE-27` dice cómo debería calcularse; el modelo es la
  implementación vigente y es lo que el motor reproduce.
- **Parametrizar las dos convenciones y elegir por caso.** Descartada por ahora: no hay ningún caso
  que evaluar con la convención antigua, y un parámetro sin uso es una vía de error en una corrida
  congelada, que registra la terna exacta con que se calculó.

## Consecuencias

- El contraste N3 cierra sin brecha contra el modelo vigente, que es el criterio de aceptación.
- Queda **una discrepancia declarada** contra `DM-STD-PE-27` §5.1. Se reporta y no se corrige, y
  tiene que aparecer en la certificación de fidelidad de H6.
- Reabrirla más adelante es aditivo y no una reescritura: el descuento está aislado en
  `factores_de_descuento()` y el resto del motor recibe la serie ya descontada.
- **No resuelve la regla `062`.** El modelo vigente además anula el primer ejercicio escribiendo un
  cero en su factor, y eso el motor no lo reproduce. Es una consulta abierta con Finanzas porque
  cambia el NPV de cabecera, y esta decisión no la toca.
