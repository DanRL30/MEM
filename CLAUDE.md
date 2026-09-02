# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Contexto de ingenieria del monorepo: como se construye, se prueba y se sostiene el codigo de la
plataforma. Esta dirigido a quien llega al repositorio sin haber participado en su construccion.

El estilo lo fija [docs/convenciones.md](docs/convenciones.md), las decisiones de diseno con coste
de reversion alto viven en [docs/adr/](docs/adr/) y la estructura general esta en
[README.md](README.md). Este archivo no repite ninguno de los tres.

---

## 1. Puesta en marcha

Dos gestores independientes sobre el mismo arbol. `uv` gobierna Python (workspace declarado en
`pyproject.toml`), `pnpm` gobierna TypeScript (workspace en `pnpm-workspace.yaml`). No se solapan.

Requisitos: Python 3.12 (`.python-version`) y Node 22 o superior.

```bash
python -m pip install --user uv
npm install --global pnpm
```

En Windows, `pip install --user` deja `uv.exe` en `%APPDATA%\Python\Python312\Scripts`, que no
suele estar en el PATH. Mientras no se agregue, `python -m uv <subcomando>` es equivalente a `uv`.

```bash
uv sync --all-packages
pnpm install
```

`--all-packages` no es opcional: sin el, los miembros del workspace no se instalan en el entorno y
`minsur_engine` no resuelve. Es la misma invocacion que usa
[templates/setup-python.yml](infra/pipelines/templates/setup-python.yml).

El gancho que rechaza emojis y trailers de coautoria se activa una vez por copia de trabajo:

```bash
git config core.hooksPath .githooks
```

---

## 2. Comandos

### Python

```bash
uv run pytest
```

Un solo archivo, una sola clase, una sola prueba:

```bash
uv run pytest packages/domain/tests/test_sellado.py
uv run pytest packages/domain/tests/test_sellado.py::TestSerializacionCanonica
uv run pytest apps/api/tests/test_contrato.py::TestSalud::test_responde_sin_autenticacion
uv run pytest -k "sellado and utc"
```

Los marcadores estan declarados en `pyproject.toml`. `tenant_minsur` marca lo que solo corre dentro
del tenant del cliente por depender de datos reales, `lento` la simulacion de Montecarlo y
`fidelidad` el contraste N0-N3. CI excluye los dos primeros y corre `fidelidad` sobre los fixtures
sinteticos; los casos certificados quedan para
[fidelidad-tenant.yml](infra/pipelines/fidelidad-tenant.yml):

```bash
uv run pytest -m "not tenant_minsur and not lento"
```

Estilo, tipos y convenciones, en el mismo orden en que corren en integracion continua:

```bash
python scripts/verificar_convenciones.py
uv run ruff check .
uv run ruff format --check .
uv run mypy packages apps/api/src
uv run pytest --cov
```

`verificar_convenciones.py` es la unica de las cuatro que no necesita el entorno sincronizado: es
ASCII puro y sin dependencias, a proposito.

Seguridad del codigo y de las dependencias. Las herramientas viven en el grupo `security` de
`pyproject.toml`, que no es un grupo por defecto: `uv sync --all-packages` no lo instala y hay que
pedirlo por su nombre.

```bash
uv run --group security bandit -r packages apps/api/src infra/pipelines/scripts scripts
uv run --group security pip-audit
```

En integracion las corre [sast-sca.yml](infra/pipelines/templates/sast-sca.yml) desde la semana 3,
no en la homologacion.

### Las herramientas de `scripts/`

Las dos que tocan Excel necesitan `openpyxl` y por tanto el entorno sincronizado; `modelo_costos.py`
y `verificar_convenciones.py` son de biblioteca estandar y corren con `python` a secas.

```bash
uv run python scripts/diseccionar_modelo.py <modelo.xlsx> --salida informe/
uv run python scripts/generar_plantilla_inputs.py --salida plantilla.xlsx \
    --unidad "Proyecto X:mina:Sn,Cu" --primer-ano 2027 --anos 20
python scripts/modelo_costos.py --detalle
```

[diseccionar_modelo.py](scripts/diseccionar_modelo.py) abre el libro corporativo en solo lectura y
levanta justo lo que despues aparece como discrepancia en el contraste: constantes incrustadas,
redondeos explicitos, referencias circulares, macros y nombres rotos. Es la herramienta de PT1.4,
que tiene tres dias en ruta critica. **Su informe hereda la clasificacion del modelo** — contiene
formulas y valores del libro — y va a `00-gestion/03-insumos-minsur/`, nunca al repositorio.

[generar_plantilla_inputs.py](scripts/generar_plantilla_inputs.py) emite la plantilla canonica de
inputs a partir de las unidades productivas que el caso declare. Es la contraparte ejecutable de
[catalogo-inputs.md](docs/modelo-economico/catalogo-inputs.md): si el catalogo y el script divergen,
manda el catalogo. La plantilla sale vacia; llenarla con un caso real la convierte en informacion
confidencial y deja de poder volver al repositorio.

[modelo_costos.py](scripts/modelo_costos.py) modela el consumo de Azure de los cuatro entornos a
partir del dimensionamiento del alcance. Es el sustento aritmetico de la eleccion de SKU del
artefacto de arquitectura, y ese consumo lo paga MINSUR.

### TypeScript

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm dev
```

Una sola prueba del frontend, filtrando por el nombre del archivo:

```bash
pnpm --filter @minsur/web test -- App
```

Hoy `apps/web/tests/` solo contiene `App.test.tsx`. Un filtro por una vista que aun no existe no
selecciona nada y vitest termina en 1 con `No test files found`: es un filtro vacio, no una
regresion.

Las pruebas de extremo a extremo estan declaradas y sin poblar. `pnpm test:e2e` apunta a
`tests/e2e/playwright.config.ts`, que todavia no existe; el directorio solo tiene su `.gitkeep`.
Son PT7.2 y llegan detras de las vistas.

`tests/rendimiento/` esta en la misma situacion y con una consecuencia mas inmediata: el trabajo
`rendimiento` de [cd.yml](infra/pipelines/cd.yml) ya invoca `k6 run tests/rendimiento/tablero.js`
contra QA, y ese archivo tampoco existe. El primer despliegue a QA falla ahi hasta que se escriba.
El umbral de apertura del tablero es de 5 s; el de la evaluacion estandar lo fija MINSUR (`R-51`),
de modo que el guion no se puede cerrar del todo antes de esa respuesta. Corre con k6, no con
pytest ni con vitest.

### El puente entre ambos

`packages/contracts` es la costura: el esquema OpenAPI que emite la API se convierte en los tipos
que consume la interfaz. Regenerarlo despues de tocar `apps/api/src/minsur_api/esquemas.py` o
cualquier router:

```bash
pnpm contracts
```

Se descompone en `pnpm api:schema` (Python, escribe `packages/contracts/openapi.json`) y
`pnpm api:types` (Node, escribe `packages/contracts/src/api.d.ts`). El primero invoca `python` a
secas, no `uv run`, asi que exige el entorno del proyecto activo o falla con `ModuleNotFoundError`.

---

## 3. Estado verificado de las comprobaciones

Reejecutado el 02/09/2026 sobre el arbol completo. **Todas las puertas de
[ci.yml](infra/pipelines/ci.yml) estan en verde.** Cualquier fallo es una regresion introducida
despues, no deuda heredada.

| Comprobacion | Resultado |
|---|---|
| `verificar_convenciones.py` | Sin infracciones |
| `ruff check .` | Limpio |
| `ruff format --check .` | Limpio, 96 archivos |
| `mypy packages apps/api/src` | Limpio en modo estricto, 61 archivos |
| `pytest` | 331 de 331, de las que 31 son el contraste de fidelidad |
| `pnpm lint`, `pnpm typecheck`, `pnpm build` | Limpios |
| `pnpm test` | 2 de 2, un archivo |

Dos cosas que conviene saber sobre como se llego aqui, porque explican decisiones que de otro modo
parecen arbitrarias:

**Las puertas se declararon antes de que existiera un entorno donde correrlas.** Hasta el
24/08/2026 nadie habia ejecutado `ruff`, `mypy` ni `pytest` sobre este arbol, y los manifiestos
arrastraban huecos que solo aparecen al ejecutar: faltaba `httpx2` para el `TestClient`, faltaba
`@types/node` para `vite.config.ts` y `vitest` 2 arrastraba un `vite` 5 paralelo al `vite` 6 de la
aplicacion, que se cerro subiendo a `vitest` 3. El manifiesto de `apps/web` fija hoy `vitest ^3`
sobre `vite ^6`; bajar de version reabre el conflicto. Si al añadir una herramienta algo no
arranca, sospecha del manifiesto antes que del codigo.

**Dos reglas estan desactivadas con motivo, no por comodidad.** `N818` exige que las excepciones
terminen en `Error`, incompatible con nombres de dominio en espanol donde el calificador va detras
(`TransicionInvalida`). `B008` marca las llamadas en valores por defecto, que es exactamente como
FastAPI declara dependencias y parametros. Ambas estan documentadas en `pyproject.toml`. No las
reactives sin leer el motivo.

---

## 4. Arquitectura del codigo

### La cadena de dependencias, y por que importa

```
minsur_engine   puro: sin I/O, sin red, sin persistencia
      |
minsur_domain   casos, corridas, versionado, estados, sellado, auditoria
      |
minsur_api      routers FastAPI, seguridad, esquemas
```

`minsur_ingest` cuelga del mismo tronco y lo consume la API. `minsur_risk` y `minsur_reporting`
estan declarados en el workspace y hoy son cascaras: solo tienen su `__init__.py` y nadie los
importa todavia. Estan ahi para que sensibilidad, Montecarlo y exportacion entren por su sitio
cuando lleguen, no porque ya aporten algo. La direccion no se invierte nunca. Que el motor no importe nada de dominio ni de infraestructura es
lo que permite ejecutarlo contra el modelo de referencia sin levantar la plataforma, y es la
condicion del contraste N0-N3.

### El motor se organiza por linea de contraste

Los modulos de `packages/engine/src/minsur_engine/` mapean 1:1 con las filas de
[docs/modelo-economico/mapa-n1.md](docs/modelo-economico/mapa-n1.md). No es una preferencia
estetica: cuando una corrida difiere del modelo corporativo, la tabla de ese documento traduce la
linea discrepante a un archivo y a una prueba. Fusionar dos bloques rompe esa propiedad.

Un modulo por bloque del libro, mas `caso.py` y `corrida.py`, que son el ensamblaje:
`corrida.calcular()` es el unico sitio que conoce el orden del calculo y los demas resuelven su
linea sin saber quien los llama. **El inventario no se lleva aqui**: son las filas de `mapa-n1.md`,
y repetir su cuenta en este archivo solo produce un numero que envejece. El contraste N0-N3 vive en `tests/fidelidad/` y corre
en cada integracion.

Un detalle del arnes que conviene entender antes de tocarlo: **el contraste sintetico es exacto, no
tolerante**. La tolerancia contractual —0,1 % o US$ 10 000— existe para comparar contra un libro de
Excel; aplicada a un caso sintetico se vuelve ciega, porque una linea cuyo valor esperado son 10 000
pasaria valiendo cero. La regla contractual esta implementada y verificada aparte, reservada para el
contraste contra el modelo.

### La ingesta es la frontera

`packages/ingest` lee la plantilla que emite `scripts/generar_plantilla_inputs.py` y devuelve un
caso validado. Es el unico sitio donde se convierten escalas —la regla 003, con el libro alternando
dolares y miles de dolares— y donde vive la tabla de sinonimos que traduce el vocabulario del libro
al del catalogo: sin ella, leer una plantilla llenada al estilo del libro pierde una de cada veinte
lineas en silencio.

La lectura **acumula incidencias con su hoja y su celda** en vez de detenerse en la primera. Una
plantilla llena a mano llega con varios errores a la vez, y devolverlos de uno en uno obliga a
corregir y reenviar tantas veces como errores tenga.

**La produccion viene en su propio libro, con una pestana por proyecto y una sola
estructura para todas.** No se adapta al proyecto: uno sin preconcentracion deja
esas filas en cero y la plataforma no las muestra. Las etiquetas, las unidades de
medida y el orden son los del libro de MINSUR, y viven en
[produccion.py](packages/ingest/src/minsur_ingest/produccion.py), que es la unica
fuente de verdad: el generador la escribe y el lector la espera.

**Se lee por secuencia, no por nombre.** El libro repite la etiqueta `Ley Sn`
cinco veces y lo unico que las distingue es la fila que llevan encima. Si la
secuencia se rompe, la lectura de esa pestana se detiene y se reporta: seguir
leyendo asignaria cada serie al concepto de al lado y el caso saldria plausible y
equivocado.

`leer_produccion()` devuelve los bloques **en el orden de las pestanas**, sin
unidad asignada: el archivo se sube desde un caso que la plataforma ya tiene
abierto, y `asociar_por_orden()` empareja la pestana n con la unidad n. El nombre
de la pestana viaja como pista y nunca como identidad. Por lo mismo el libro **no
lleva hoja `Caso`**, y el horizonte se deduce contando la fila de anos: nada fija
el numero de ejercicios de antemano, de modo que un proyecto de vida larga no
exige tocar el lector.

**La refineria no tiene pestana.** Sus filas son resultado del concentrado que le
entregan las minas —la lectura de las formulas del libro lo confirmo fila por
fila— y sus dos entradas reales, la capacidad y la recuperacion, son supuestos
que en el libro viven en la hoja `Supuestos`.

**Lo que la ingesta no sabe consumir se reporta.** Hasta el 01/09/2026 una fila
con concepto desconocido se descartaba con un `continue`: el usuario la llenaba,
el caso se leia sin errores y su dato no se usaba. Es el peor fallo posible en una
frontera, porque no deja sintoma.

### El opex tiene su libro, y ahi la refineria si lleva pestana

[opex.py](packages/ingest/src/minsur_ingest/opex.py) declara la estructura y
[leer_opex()](packages/ingest/src/minsur_ingest/plantilla.py) la lee, con el
mismo patron que produccion: una pestana por unidad, estructura fija, lectura por
secuencia y asociacion por orden. Tres cosas lo diferencian y conviene tenerlas
presentes antes de tocarlo.

**La refineria lleva pestana**, al reves que en produccion. Su produccion es
resultado, pero su costo es dato. Por eso el libro de opex trae **una pestana
mas** que el de produccion, y `aplicar()` recorre `caso.unidades` sin saltar la
fundicion.

**Sus conceptos van en la misma estructura que los de las minas**, no en una
plantilla aparte: fundicion, refineria, planta de subproductos y su
mantenimiento. Una mina los deja en cero, igual que deja en cero la
preconcentracion la unidad que no la tiene. Partir la plantilla en dos habria
roto justo la propiedad que la hace servir para un proyecto que no existe
todavia.

**El catalogo no reproduce el libro concepto a concepto.** Tres de los suyos
quedan fuera por decision del 02/09/2026, listados en la seccion 9 de
[brechas-plantilla-opex.md](docs/modelo-economico/brechas-plantilla-opex.md).
Dos se cargan por la cola si un caso los necesita; el tercero, `Planillas`, no
vuelve por ningun camino, porque es la planilla derivada y pedirla como dato es
lo que la regla `026` prohibe.

**No hay corroborador y no lo habra.** La auditoria de `InputsOpex`
—[brechas-plantilla-opex.md](docs/modelo-economico/brechas-plantilla-opex.md)—
confirmo que el bloque es todo dato. Lo que el libro calcula ahi son totales,
ratios y la produccion que trae de `InputsProd`, y nada de eso se carga: no hay
dos valores que comparar. Es la diferencia con produccion, donde el usuario carga
tambien lo derivado.

**La cola de conceptos propios es de longitud fija y va en un lugar fijo.** Es el
acuerdo 6 del 27/08/2026, y esa disposicion es lo que permite seguir leyendo por
secuencia. Pasada la cuenta de la cola, lo que venga tiene que ser el bloque de
gastos: seguir tragando filas convertiria un gasto mal escrito en un costo con su
nombre. Lo que se escriba en la cola **solo afecta al total**, que es la condicion
con que el acuerdo la mantiene contrastable.

### Los gastos no son cash cost, y cada fila va a un sitio distinto

El bloque de gastos de `InputsOpex` entra por la misma pestana y vive en
`UnidadProductiva.gastos`, separado de `costos`. La separacion no es de orden:
los administrativos y la gestion social van al flujo operativo, los predios y los
estudios al de inversiones, y solo una parte de todos ellos rebaja la base
imponible.

**Dos filas no se piden porque el libro las deriva.** `Planilla` sale del cash
cost de la unidad por la tasa de los supuestos (regla `026`) y `Gestión Social
Deducible` es la gestion social por su fraccion deducible, que sin declarar es
entera (regla `027`). Pedirlas como dato invitaria a que contradijeran a su
origen.

**Los estudios se llevan por partida doble.** `estudios` es la salida de caja
completa y `estudios_deducibles` la parte que rebaja la base: la diferencia son
los capitalizables, que el libro deprecia en vez de deducir. Su naturaleza
contable no esta declarada en ninguna parte, asi que hoy salen de caja y no se
deprecian; eso se cierra con la plantilla de CAPEX.

### El bloque de la refineria: todo resultado, y sin agrupar

[refineria.py](packages/engine/src/minsur_engine/refineria.py) rehace el bloque
entero desde lo que producen las minas: lo alimentado por cada origen y su ley,
el consolidado acotado por la capacidad, la ley promedio ponderada, el refinado,
el excedente y su venta spot, y el `Check` del libro. **Ninguna de esas filas es
un dato.** Sus dos unicas entradas son supuestos —la capacidad y la recuperacion
de cada componente—, que en el libro viven en la hoja `Supuestos`.

**Regla de oro: nada se agrupa.** Cada unidad aporta con su propia recuperacion y
su refinado se calcula por separado; el total es la suma de esos aportes. El libro
agrupa —`Recuperación Sn SR + B2` y `NZ + SRP`— y la plataforma no lo reproduce,
por decision del 01/09/2026: un proyecto nuevo no cabe en ningun grupo sin decidir
a cual se parece, y una diferencia en un total agregado no se puede atribuir a una
unidad. El efecto es medible, no un matiz, y esta fijado en
`test_refineria.py::TestReglaDeOro`. Dar el mismo valor a las unidades de un grupo
reproduce el comportamiento del libro sin tocar el motor.

**Cuando la refineria se satura, el recorte se reparte por merito**: va a spot
primero el concentrado de menor ley, y **con leyes iguales decide el margen por
tonelada** —lo que gana la refineria por refinar una tonelada en vez de venderla—,
que con igual contenido es la diferencia de recuperaciones. El libro se lo resta entero a la ultima unidad en entrar, y eso no se
generaliza a un proyecto nuevo. Es la desviacion `D-05`, y arrastra una segunda
consecuencia de coherencia: **el excedente se valoriza a la ley de lo que
efectivamente fue a spot**, no a la del conjunto. Decir que sale el peor
concentrado y cobrarlo al promedio seria contradictorio.

### Los supuestos van en dos plantillas, y no por comodidad

`minsur_ingest/supuestos.py` define las dos, y `leer_comite_de_precios()` y
`leer_supuestos()` las leen. **Tienen duenos distintos.** El comite de precios es
dato maestro: lo aprueba y lo sube Finanzas, y quien modela solo elige que comite
usa. El resto de los supuestos son del caso. Mezclarlos en un archivo dejaria a
cualquiera cambiando un precio aprobado sin que nadie lo advierta.

El comite lleva **nombre y fecha de aprobacion**, y sin nombre se rechaza: una
corrida registra que comite uso, no "el vigente", y sin identificacion no hay a
que referirse. No tiene las ocho ranuras del libro —que reserva ocho juegos y
elige uno con un selector—: versionar es lo mismo sin el limite ni las ranuras
rotuladas `xxx`.

La plantilla de supuestos lleva una pestana `Comunes` y una por proyecto, en
orden. Lo que es de cada unidad es su depreciacion —tributaria y financiera, como
pide `D-04`— y su recuperacion en la refineria, **una por unidad y no por los
grupos del libro**, que es la regla de oro.

Tres unidades de medida nuevas que conviene no perder de vista: la plata se
cotiza en `$/oz` y su ley pagable en `g/t`, y la depreciacion del libro va en
`k$`, que la ingesta convierte a dolares. Es la regla `003` otra vez.

### Los tres caminos de ingreso, y por fin los tres cableados

El libro vende por tres vias y `corrida._ventas` las recorre todas: **estano
refinado** a precio mas premio, **estano en concentrado** a precio por el factor
pagable, y el **concentrado polimetalico**, que se liquida embarque a embarque
valorizando su contenido pagable y descontando maquila y refinacion.

La tercera estuvo implementada y sin cablear hasta el 01/09/2026:
`liquidar_concentrado` existia, estaba probada, y nadie la llamaba. El
concentrado de cobre se calculaba y no se cobraba.

La liquidacion se guarda **por unidad** en `concentrado_liquidado_por_unidad`, no
solo su suma: es la regla de oro aplicada a la venta, y sin ella una diferencia
no se puede atribuir a un origen.

**Los aportes reguladores son series del caso, no tasas fijas.** MINSUR confirmo
el 01/09/2026 que varian los primeros ejercicios porque hay mejor informacion
sobre ellos. `ParametrosCorporativos` conserva la tasa de referencia y
`DatosComunes.osinergmin` y `.oefa` la sobrescriben cuando el caso las declara;
vacio significa usar la de referencia.

### Una fila entera en cero no se muestra

La estructura de la plantilla es la misma para todos los proyectos, de modo que
un caso de solo estano recibe igual las filas de cobre y de plata. En pantalla no
tienen nada que decir, y `campos_con_dato()` es quien decide cuales sobran: una
serie sin ningun valor distinto de cero significa que el concepto **no aplica a
esa unidad**.

Vive en el motor y la corrida lo expone en `campos_con_dato_por_unidad`, para que
la API y la interfaz lleguen a la misma conclusion del mismo caso. Si cada
pantalla lo resolviera por su cuenta acabarian mostrando cosas distintas.

**Vacio y todo ceros son lo mismo aqui.** Una serie que no se lleno y una que se
lleno con ceros dicen ambas que el concepto no aplica; distinguirlas obligaria al
usuario a recordar cual de las dos escribio.

### El corroborador: alarma y control de calidad, no correccion

Toda la produccion entra como dato, **incluidos los valores que salen de un
calculo interno**. El usuario carga sus series tal como las tiene y
[corroboracion.py](packages/engine/src/minsur_engine/corroboracion.py) las rehace
y compara, celda a celda, con su unidad, su ano y su magnitud.

Las ocho reglas no son una interpretacion nuestra: son las formulas del bloque
`Calculo Interno` del libro de produccion que MINSUR entrego el 01/09/2026. Estan
transcritas en el docstring del modulo y en
[brechas-plantilla-produccion.md](docs/modelo-economico/brechas-plantilla-produccion.md).
Dos merecen atencion porque es facil equivocarlas: **las toneladas finas llevan
el factor de recuperacion**, y **el concentrado es las finas entre su ley y nada
mas** —aplicar la recuperacion otra vez la cuenta dos veces—.

Tres propiedades que no conviene romper:

- **El dato cargado es el que usa el flujo.** El recalculo lo audita y no lo
  sustituye nunca. Es la misma regla de fidelidad que impide corregir el modelo
  corporativo, y esta atada por `test_corroboracion.py::TestElDatoDelUsuarioEsElQueManda`:
  alterar una fila corroborable mueve el resultado **como mueve el dato**, no
  como dice el recalculo, y alterar una que solo lee el corroborador deja el
  resultado intacto hasta el ultimo decimal. Si alguna de esas dos pruebas
  falla, es que el recalculo se colo en el calculo.
- **Corroborar nunca detiene el calculo.** Un caso con una ley mal tecleada llega
  hasta el NPV para que se vea el efecto.
- **El informe viaja en la corrida** y se congela con ella. Sin eso no se puede
  sustentar despues por que se acepto una diferencia.

La tolerancia de corroboracion **no es la del contraste N1**: aquella compara el
motor contra el libro y la fija Finanzas (`R-31`); esta compara el dato del
usuario contra el recalculo del propio sistema. El 0,5 % de
`TOLERANCIA_POR_DEFECTO` es propuesta de INVA y esta consultada.

### Lo que ya esta construido: el dominio

Es la parte densa del repositorio y la que conviene leer antes de tocar nada.

- [versionado.py](packages/domain/src/minsur_domain/versionado.py) — la terna motor, datos maestros
  e inputs. Una corrida guarda las tres versiones exactas, nunca una referencia a "lo vigente":
  de otro modo, publicar una version nueva del modelo reescribiria evaluaciones pasadas.
- [estados.py](packages/domain/src/minsur_domain/estados.py) — BORRADOR, CALCULADA, CONGELADA.
  Recalcular una corrida congelada crea una corrida nueva que apunta a la anterior; no la modifica.
- [sellado.py](packages/domain/src/minsur_domain/sellado.py) — imagen autocontenida y SHA-256 sobre
  una serializacion canonica. El cuidado esta en la estabilidad del resumen: orden de claves,
  formato de flotantes y normalizacion de zona horaria. Reproducir a cinco anos es el requisito.
- [auditoria.py](packages/domain/src/minsur_domain/auditoria.py) — bitacora de solo escritura. El
  diccionario `COBERTURA` mapea cada uno de los ocho requisitos de gobierno del alcance a un campo
  concreto, para que el cumplimiento sea verificable y no declarativo.
- [carga_directa.py](packages/domain/src/minsur_domain/carga_directa.py) — las plantillas de Excel
  no atraviesan la API. La interfaz obtiene una autorizacion de corta vigencia y sube directo al
  almacenamiento.

### La API

`crear_app()` en [main.py](apps/api/src/minsur_api/main.py) monta siete routers bajo `/api`. Dos
decisiones que se repiten en todo el modulo:

- El backend revalida el token aunque API Management ya lo haya validado. La restriccion de red que
  limita el backend a la puerta es configuracion, y configuracion cambia por error.
- Un `501` no es una laguna: senala una operacion bloqueada por un insumo del cliente que aun no
  llega, y el cuerpo incluye la restriccion `R-xx` responsable. No los conviertas en `200` con datos
  inventados.

El perfil del usuario se deriva de la reclamacion `groups` del token; la plataforma no consulta
Microsoft Graph. El mapeo vive en [seguridad.py](apps/api/src/minsur_api/seguridad.py) con una
precedencia explicita para usuarios que pertenecen a varios grupos.

**Hoy no hay persistencia y conviene saberlo antes de probar nada.**
[repositorio.py](apps/api/src/minsur_api/repositorio.py) define el puerto `RepositorioDeCasos` y lo
sirve con un almacen en memoria: lo que se guarda se pierde al reiniciar el proceso. El destino es
Azure SQL y aprovisionarlo depende de `R-23`. Lo definitivo es el puerto — el adaptador de Azure SQL
entra por ahi sin tocar un router—, de modo que un caso que "desaparece" entre dos corridas del
servicio no es un fallo.
[evaluacion.py](apps/api/src/minsur_api/evaluacion.py) es la otra costura: mide el tiempo, calcula
la huella de los insumos y arma la terna de versiones. No reproduce ni una linea del motor.

### Las pruebas de contrato detectan deriva, no comportamiento

[test_contrato.py](apps/api/tests/test_contrato.py) hace algo poco habitual y conviene entenderlo
antes de "arreglar" un fallo suyo: lee los artefactos reales del repositorio y comprueba la
correspondencia con el esquema OpenAPI. Extrae las rutas de
`infra/pipelines/scripts/verificacion_pase.py`, verifica que `/api/salud` aparezca en
`templates/desplegar.yml` y que `package.json` siga invocando `python -m minsur_api.openapi`.

La consecuencia practica: renombrar un endpoint, mover un script de pipeline o cambiar un comando
de `package.json` rompe estas pruebas a proposito. Sin ellas, el fallo aparece durante la ventana de
mantenimiento del domingo del pase.

### La interfaz

[App.tsx](apps/web/src/App.tsx) es todavia el armazon: un encabezado y el `<main>` donde PT3 montara
casos, tablero, historial y comparador. Lo que si esta resuelto, y no conviene tocar a ciegas, es la
capa de marca que carga [main.tsx](apps/web/src/main.tsx).

- [estilos/color.css](apps/web/src/estilos/color.css) traduce el Manual de Marca Minsur. Los valores
  de marca son los del manual y no se interpolan ni se ajustan. Los tokens semanticos derivados
  — densidad, tablas, estados, formularios, fondo oscuro — son propuesta de INVA, porque el manual
  no cubre interfaz de aplicacion, y **estan pendientes de aprobacion de Comunicaciones de MINSUR**.
  Hasta que llegue no son definitivos, y no se presentan como tales al cliente.
- [activos/fuentes/](apps/web/src/activos/fuentes/) guarda tipografias comerciales licenciadas por
  MINSUR, no activos intercambiables. Rationell y Bagiora son propiedad de sus fundiciones; la
  procedencia, la version y la situacion de licencia de cada archivo estan en
  [LEEME.md](apps/web/src/activos/fuentes/LEEME.md). Agregar un peso o sustituir una familia exige
  actualizar ese registro en el mismo commit.

`apps/web/staticwebapp.config.json` viaja con el artefacto: Static Web Apps lo lee del `dist`
publicado, de modo que un cambio de rutas o de cabeceras no se comprueba corriendo `pnpm dev`.

### Infraestructura

Una sola plantilla, `infra/bicep/main.bicep`, para los cuatro entornos; solo cambian los
`.bicepparam` de `envs/`. Los pipelines de `infra/pipelines/` se apoyan en cuatro scripts de Python
(`verificacion_pase.py`, `verificar_manifiestos.py`, `evaluar_hallazgos.py`, `evaluar_zap.py`) que
tambien estan sujetos a `ruff` y `mypy`.

---

## 5. Lo que muerde

**Los archivos de bloqueo estan versionados y CI los exige intactos.** Corre `uv sync --frozen` y
`pnpm install --frozen-lockfile`, de modo que un `uv.lock` o un `pnpm-lock.yaml` que no concuerde
con su manifiesto detiene el pipeline en el primer paso. Si cambias una dependencia, el lock
regenerado entra en el mismo commit.

**`packages/contracts/src/api.d.ts` es generado pero CI no lo genera.** El trabajo `web` de
[ci.yml](infra/pipelines/ci.yml) corre `pnpm typecheck` sin pasar antes por `pnpm contracts`, y
`src/index.ts` importa `./api`. El archivo tiene que estar en el repositorio aunque sea derivado; la
alternativa es agregar el paso de generacion al pipeline. No lo edites a mano en ninguno de los dos
casos.

**`allowBuilds` de esbuild.** pnpm 11 aborta la instalacion si un script de instalacion no esta
aprobado. `pnpm-workspace.yaml` lo declara; si aparece un gestor de paquetes nuevo con la misma
necesidad, se agrega ahi y no con `pnpm approve-builds`, que solo afecta a la maquina local.

**El motor no corrige el modelo.** Si el libro corporativo tiene un error metodologico, se documenta
en [reglas-no-documentadas.md](docs/modelo-economico/reglas-no-documentadas.md) y se reporta a
Finanzas. Corregirlo en el codigo rompe el contraste de fidelidad, que es el criterio de aceptacion
del entregable.

**La excepcion son las desviaciones acordadas, y hoy son cinco lineas del contraste N1.** MINSUR
pidio expresamente que la plataforma se aparte del modelo en esos puntos; el registro, con la
reunion que origina cada acuerdo y el tratamiento que le corresponde, esta en
[desviaciones-acordadas.md](docs/modelo-economico/desviaciones-acordadas.md). Ahi el motor no
coincide con el modelo y no debe coincidir: se contrasta contra el valor esperado que define el
acuerdo, y la prueba declara la desviacion que aplica. Una linea que difiera sin citar una
desviacion registrada sigue siendo un fallo.

**El estandar corporativo no le gana al modelo.** `DM-STD-PE-27` dice como deberia calcularse; el
modelo es la implementacion vigente y es lo que el motor reproduce. Donde difieran, manda el modelo
y la diferencia se registra como discrepancia.
[estandar-dm-std-pe-27.md](docs/modelo-economico/estandar-dm-std-pe-27.md) recoge lo que el estandar
exige y que hoy no esta especificado en el arbol; ningun punto marcado pendiente de confirmacion se
implementa hasta que Finanzas responda.

**Los umbrales de tolerancia son provisionales.** Los de `mapa-n1.md` son la propuesta de INVA. El
valor contractual lo fija Finanzas (`R-31`). Hasta entonces no se declaran como criterio de
aceptacion en ningun documento ni mensaje al cliente.
