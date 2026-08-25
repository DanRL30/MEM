# 0008. Versionar CLAUDE.md con su encabezado de origen

- Estado: aceptada
- Fecha: 24/08/2026
- Decide: Project Manager del servicio (INVA)
- Restricción relacionada: ninguna del cuadro de control. La regla afectada es
  `docs/convenciones.md`, sección 2.

## Contexto

`CLAUDE.md` concentra el contexto de ingeniería del monorepo: los comandos reales de cada
comprobación, el estado verificado de las puertas de calidad, la cadena de dependencias entre el
motor, el dominio y la API, y las trampas que solo se descubren ejecutando el toolchain. Es el
documento que evita que quien llega al repositorio repita el trabajo de averiguar cómo se construye.

La primera línea del archivo es un encabezado que nombra la herramienta de asistencia con la que se
trabaja. `docs/convenciones.md`, sección 2, prohíbe esa atribución en cualquier archivo del
repositorio: el código se entrega bajo titularidad de MINSUR y no menciona con qué se escribió.
`scripts/verificar_convenciones.py` hace cumplir esa regla en cada integración.

De ahí el conflicto. El archivo empezó excluido en `.gitignore`, lo que resolvía la regla pero
dejaba fuera del entregable el único documento que explica cómo trabajar en el repositorio. Los
entregables E05 (código fuente y repositorio) y E08 (manual técnico y de operación) se transfieren
a MINSUR para que opere y mantenga la plataforma; un repositorio cuyo contexto de ingeniería se
quedó en el computador de INVA transfiere el código pero no la capacidad de sostenerlo.

## Decisión

`CLAUDE.md` se versiona con su encabezado de origen intacto, y `verificar_convenciones.py` exime a
ese único archivo de la regla de atribución, sin eximirlo de las demás.

## Alternativas consideradas

**Mantenerlo fuera del repositorio.** Cumple la convención sin excepciones y fue el estado inicial.
Descartada por el costo descrito arriba: el contexto de ingeniería no llega a quien recibe el
código.

**Versionarlo sin el encabezado.** Cumple la convención y conserva el contenido. Descartada por la
jefatura del servicio: el encabezado identifica el propósito del archivo y su formato es el que
esperan las herramientas de trabajo del equipo.

**Eximir a `CLAUDE.md` del verificador por completo.** Más corto de escribir. Descartada porque
deja de comprobar los caracteres decorativos en un archivo del entregable, que es la mitad de la
regla y la que más se infringe por descuido.

**Relajar el patrón de atribución para todo el árbol.** Descartada: debilita la regla en los
cuarenta y siete archivos que la cumplen para acomodar a uno.

## Consecuencias

Quien reciba el repositorio recibe también el documento que explica cómo construirlo, probarlo y
sostenerlo, sin depender de que alguien de INVA lo acompañe.

A cambio, el entregable contiene un archivo que incumple la sección 2 de las convenciones con una
excepción codificada en el propio verificador. **Si MINSUR audita las convenciones, la excepción
tiene que poder explicarse, y este registro es esa explicación.** Sin él, la excepción parece un
atajo que alguien se permitió.

La excepción está acotada por diseño. `SIN_REGLA_DE_ATRIBUCION` afecta a una sola regla y a un solo
archivo: `CLAUDE.md` se sigue auditando por caracteres decorativos, y ningún otro archivo queda
exento de nada. Ambas direcciones están comprobadas: un archivo cualquiera con la misma línea sigue
siendo rechazado, y un carácter decorativo dentro de `CLAUDE.md` se sigue reportando.

`.claude/` permanece excluido. Son las definiciones de las herramientas de trabajo de INVA, no
documentación de la plataforma, y su exclusión no está en discusión aquí.

Si en algún momento se retira el encabezado, `SIN_REGLA_DE_ATRIBUCION` deja de tener función y se
elimina con él. El comentario en `verificar_convenciones.py` lo advierte.
