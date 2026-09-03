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

Los bloques de esta seccion invocan `uv` directamente. Si el shell no lo resuelve
-el caso habitual en Windows, con `uv.exe` fuera del PATH-, `python -m uv
<subcomando>` es equivalente linea por linea, como explica la seccion 1.

### Python

La API en local, que es contra quien apunta el proxy de la interfaz:

```bash
uv run uvicorn minsur_api.main:app --reload --port 8000
```

[main.py](apps/api/src/minsur_api/main.py) arma la aplicacion en `crear_app()` y
expone `app` a nivel de modulo, de modo que uvicorn la toma sin `--factory`. El
puerto no es arbitrario: [vite.config.ts](apps/web/vite.config.ts) redirige `/api`
a `http://localhost:8000` salvo que `VITE_API_ORIGIN` diga otra cosa, asi que
`pnpm dev` contra otro puerto sirve la interfaz y no encuentra backend. No hace
falta configurar nada mas para arrancar: las variables de
[config.py](apps/api/src/minsur_api/config.py) tienen valor por defecto y sus
nombres estan en `.env.example`. Lo que falte se nota al usar la funcion que lo
necesita, no al levantar el proceso.

Las pruebas:

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

Dos pruebas tardan cerca de minuto y medio, y casi todo ese tiempo es el montaje del entorno jsdom
en Windows -- 70 s de los 83 s medidos el 02/09/2026-. No esta colgado: vitest no imprime nada
hasta que termina de preparar el entorno.

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

### Las plantillas de Bicep

Ninguna de las puertas anteriores mira las plantillas de Bicep. `pytest` no las toca, y `ruff` y
`mypy` alcanzan solo a los cuatro scripts de Python de `infra/pipelines/scripts/`, que si estan
sujetos a las dos. Lo que valida las plantillas es
[iac-validate.yml](infra/pipelines/iac-validate.yml); en local, con la CLI de Azure instalada, son
estos dos comandos:

```bash
az bicep build --file infra/bicep/main.bicep --stdout > /dev/null
az bicep lint --file infra/bicep/main.bicep
```

El primero compila y delata lo que no resuelve; el segundo aplica las reglas de estilo. Los dos
apuntan a `main.bicep` a proposito: el pipeline recorre `infra/bicep/*.bicep`, que hoy es solo esa
plantilla, y los once modulos de `modules/` se compilan a traves de ella. Un modulo que nadie
referencie no lo compila nadie. Hoy los once son alcanzables -`punto-privado.bicep` por la via de
`almacenamiento`, `base-datos` y `boveda`-, y conviene que siga siendo asi.

**El `what-if` no se corre desde una maquina local.** Necesita la conexion de servicio del pipeline
contra el entorno destino, y ese contraste es parte de la aprobacion del pase, no de la
verificacion previa a un commit.

---

## 3. Estado verificado de las comprobaciones

Reejecutadas el 02/09/2026 sobre el arbol completo, las puertas de
[ci.yml](infra/pipelines/ci.yml) -convenciones, `ruff check`, `ruff format`, `mypy` en estricto,
`pytest`, y `pnpm lint`, `typecheck`, `test` y `build`- **estan todas en verde**. Cualquier fallo es
una regresion introducida despues, no deuda heredada.

Aqui no va la cuenta de pruebas ni de archivos: es un numero que envejece en el commit siguiente y
que el propio comando informa mejor. Lo que este archivo fija es el invariante -el arbol se entrega
en verde- y lo que cuesta reaprender si se pierde, que es lo que sigue.

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

`packages/ingest` lee las plantillas que emite `scripts/generar_plantilla_inputs.py` y devuelve un
caso validado, o las incidencias con su hoja y su celda. Es el unico sitio donde se convierten
escalas -la regla `003`, con el libro alternando dolares, `k$` y `$k`- y donde vive la tabla de
sinonimos que traduce el vocabulario del libro al del catalogo: sin ella, leer una plantilla llenada
al estilo del libro pierde una de cada veinte lineas en silencio.

Cinco propiedades sostienen la lectura de los tres libros de entrada. Romper cualquiera de ellas no
produce un error: produce un caso plausible y equivocado.

- **Estructura fija y una pestana por unidad, en orden.** El libro no identifica el caso -no lleva
  hoja `Caso`-: el archivo se sube desde un caso que la plataforma ya tiene abierto y
  `asociar_por_orden()` empareja la pestana n con la unidad n. El nombre de la pestana viaja como
  pista y nunca como identidad, y el horizonte se deduce contando la fila de anos.
- **Se lee por secuencia, no por nombre.** El libro repite la etiqueta `Ley Sn` cinco veces y lo
  unico que las distingue es la fila que llevan encima. Si la secuencia se rompe, la lectura de esa
  pestana se detiene y se reporta: seguir leyendo asignaria cada serie al concepto de al lado.
- **Lo que no se sabe consumir se reporta.** Hasta el 01/09/2026 una fila con concepto desconocido
  se descartaba con un `continue`: el usuario la llenaba, el caso se leia sin errores y su dato no
  llegaba al motor. Es el peor fallo posible en una frontera, porque no deja sintoma.
- **Las incidencias se acumulan.** Una plantilla llena a mano llega con varios errores a la vez, y
  devolverlos de uno en uno obliga a corregir y reenviar tantas veces como errores tenga.
- **La misma estructura para todos los proyectos.** Un caso de solo estano recibe igual las filas de
  cobre y de plata y las deja en cero. Partir la plantilla por tipo de unidad habria roto justo la
  propiedad que la hace servir para un proyecto que todavia no existe.

La estructura de cada libro vive en su modulo
-[produccion.py](packages/ingest/src/minsur_ingest/produccion.py),
[opex.py](packages/ingest/src/minsur_ingest/opex.py),
[capex.py](packages/ingest/src/minsur_ingest/capex.py)-, y ese modulo es la unica fuente de verdad:
el generador la escribe y el lector la espera. La auditoria fila a fila contra el libro corporativo,
que es de donde salen, esta en los `brechas-plantilla-*.md` de
[docs/modelo-economico/](docs/modelo-economico/).

### Los tres libros de entrada no son simetricos

| | Produccion | Opex | Capex |
|---|---|---|---|
| Pestana de la refineria | No: su produccion es resultado | Si: su costo es dato | Si |
| Pestana del deposito | No: no extrae mineral | Si | Si |
| Corroborador | Si | No, y no lo habra | No |
| Cola de conceptos propios | No | Si, de longitud y lugar fijos | No |

**La refineria no tiene pestana de produccion** porque todas sus filas salen del concentrado que le
entregan las minas, y sus dos unicas entradas -capacidad y recuperacion- son supuestos. **Si tiene
bloque de opex**, con cuatro conceptos propios que las minas dejan en cero, de modo que el libro de
opex trae una pestana mas que el de produccion.

**No hay corroborador en opex ni en capex, y no lo habra.** Ahi el bloque es todo dato y no hay dos
valores que comparar; lo que esas hojas calculan -totales, ratios, subtotales- no se carga. Es la
diferencia con produccion, donde el usuario carga tambien lo derivable.

**La cola de conceptos propios del opex es de longitud fija y va en un lugar fijo** -acuerdo 6 del
27/08/2026-, y eso es lo que permite seguir leyendo por secuencia: pasada la cuenta de la cola, lo
que venga tiene que ser el bloque de gastos. Lo que se escriba en la cola solo afecta al total, que
es la condicion con que el acuerdo la mantiene contrastable.

**Del capex se pide una sola clasificacion, la contable, y cinco conceptos por unidad.** La etapa no
se pide porque el libro no la carga: sale por formula, y
[clasificar_por_etapa](packages/engine/src/minsur_engine/capex.py) la reproduce. La consecuencia
importa al leer una prueba: el `Check` del libro se cumple por construccion y dejo de ser una
verificacion. `Equipos de Computo` se pide aparte de la maquinaria y se consolida al leer.

**La etapa distingue unidades de proyecto de unidades base**, y no es una puerta por produccion
aplicada a todas por igual. El capital depreciable de una unidad base es sostenimiento siempre,
produzca o no; el de un proyecto es inicial mientras su cuenta de ejercicios con produccion no pase
el `umbral_de_capital_inicial` que declara el caso, y vacio significa unidad base. El libro usa uno
para Nazareth y dos para Santo Domingo, sin decir por que. Contrastado contra las bandas de los
casos 1 y 7, las tres etapas coinciden ejercicio a ejercicio.

**Tres filas del bloque de gastos no se piden porque el libro las deriva**: `Ano con operacion`,
`Planilla` y `Gestion Social Deducible`, que son las reglas `026` y `027`. Los gastos no son cash
cost -viven en `UnidadProductiva.gastos`, aparte de `costos`- y cada fila va a un sitio distinto:
los administrativos y la gestion social al flujo operativo, los predios y los estudios al de
inversiones, y solo una parte de todos ellos rebaja la base imponible. Los estudios se llevan por
partida doble, `estudios` y `estudios_deducibles`: la diferencia son los capitalizables, que el
libro deprecia en vez de deducir.

**`TIPOS_DE_UNIDAD` tiene `mina`, `refineria` y `deposito`.** Un deposito recibe relave, no extrae y
no vende: solo lleva capital y depreciacion, y su costo operativo se carga en la linea `Relavera` de
la mina a la que sirve. No confundirlo con una relavera de reprocesamiento, que es una mina con
origen de relave. `UnidadProductiva.produce` decide quien lleva pestana de produccion, y es tambien
la puerta de la regla `013`: aplicarla a una unidad que no produce por diseno le anularia el escudo
fiscal entero en vez de retrasarlo. **Esa puerta difiere y libera, no anula**: la cuota de los
ejercicios anteriores al primero con produccion se reconoce entera en ese primer ejercicio, que es
lo que hace el libro y lo que impide perder capital depreciable por el camino.

### La depreciacion tiene dos vias y dos metodos, no dos juegos de tasas

Es lo mas facil de romper del motor, porque las dos vias se parecen y no lo son.

| Componente | Tributaria | Financiera |
|---|---|---|
| Maquinaria, equipos y vehiculos | Lineal | Lineal |
| Equipos de computo | Lineal | Lineal |
| Instalaciones y equipos diversos | Lineal | **Agotamiento** |
| Edificaciones y construcciones | Lineal | **Agotamiento** |
| No depreciable | **Entero en su ano** | **Entero en su ano** |
| Estudios capitalizables | Lineal al 5 % | Lineal al 5 % |

**Agotamiento** es el metodo de unidades de produccion: no hay cronograma por ano de inversion, hay
un solo saldo que recibe las inversiones y se agota al ritmo al que se vacia el yacimiento. Y **`No
depreciable` engana con el nombre**: no es que no se deprecie, es que no se reparte, y entra entero
en su ejercicio.

Cuatro cosas que conviene no reaprender por las malas:

- **Las dos vias miran la produccion de forma distinta.** La tributaria acumula; la financiera
  cierra ano a ano contra la bandera `Ano con produccion`, de modo que una parada a mitad de vida no
  difiere la cuota financiera: la pierde. Es la regla `041`, y es facil de perder porque las dos
  parecen la misma condicion.
- **Cada componente se deprecia y se informa por separado**, aunque el libro fusione el computo con
  la maquinaria bajo un mismo codigo. `Corrida` lleva las dos vistas, el total por mina y el detalle
  por componente: un proyecto nuevo puede traer componentes que hoy no existen, y una depreciacion
  que llega sumada no se puede volver a separar.
- **Dos puntos no reproducen el modelo a proposito**, las reglas `036` y `039`, por el mismo
  criterio: una excepcion alojada en la formula de una unidad concreta no tiene donde vivir cuando
  lo que se evalua es un proyecto que hoy no existe. Estan a la espera del acta que las registre
  como desviaciones.
- **Las tasas y las reservas son dato maestro que el caso puede sobrescribir**, componente a
  componente, y van en filas constantes: una sola celda, no cuarenta. Declarar las reservas las
  convierte en dato; dejarlas vacias, en calculo, y vacio no es cero.

El estudio capitalizable no sale del capital: llega por los gastos del opex, de modo que una unidad
puede depreciar sin haber invertido. La `Proyeccion SAP` tampoco es un componente: es la
depreciacion ya contabilizada de los activos que existen antes del primer ano del caso, y viaja en
el mismo mapa porque se suma con ellos.

La derivacion completa, con la celda de origen de cada regla, esta en
[brechas-plantilla-capex.md](docs/modelo-economico/brechas-plantilla-capex.md) y
[reglas-no-documentadas.md](docs/modelo-economico/reglas-no-documentadas.md).

### El bloque de la refineria: todo resultado, y sin agrupar

[refineria.py](packages/engine/src/minsur_engine/refineria.py) rehace el bloque de Pisco entero
desde lo que producen las minas: lo alimentado por cada origen y su ley, el consolidado acotado por
la capacidad, la ley promedio ponderada, el refinado, el excedente y su venta spot, y el `Check` del
libro. **Ninguna de esas filas es un dato.**

**Regla de oro: nada se agrupa.** El libro junta la recuperacion en `SR + B2` y `NZ + SRP`; la
plataforma la lleva por unidad. Un proyecto nuevo no cabe en ningun grupo sin decidir a cual se
parece, y una diferencia en un total agregado no se puede atribuir a un origen. El efecto es
medible, no un matiz, y lo fija `test_refineria.py::TestReglaDeOro`. Dar el mismo valor a las
unidades de un grupo reproduce el comportamiento del libro sin tocar el motor. La misma regla rige
la venta: la liquidacion se guarda en `concentrado_liquidado_por_unidad`, no solo su suma.

**Cuando la refineria satura, el recorte se reparte por merito** -sale a spot el concentrado de
menor ley, y con leyes iguales desempata el margen por tonelada-, y **solo al superar la capacidad,
nunca antes**, aunque algun origen de margen negativo. Es la desviacion `D-05`, decidida por el
Project Manager y no una lectura del libro, y arrastra que el excedente se valorice a la ley de lo
que efectivamente fue a spot: decir que sale el peor concentrado y cobrarlo al promedio seria
contradictorio. Ver
[desviaciones-acordadas.md](docs/modelo-economico/desviaciones-acordadas.md).

Los supuestos que lo alimentan van en **dos plantillas con duenos distintos**: el comite de precios
es dato maestro que aprueba y sube Finanzas -lleva nombre y fecha de aprobacion, y sin nombre se
rechaza, porque una corrida registra que comite uso y no el vigente-, y el resto son supuestos del
caso, con una pestana `Comunes` y una por proyecto. Mezclarlos dejaria a cualquiera cambiando un
precio aprobado sin que nadie lo advierta.

### El corroborador: alarma y control de calidad, no correccion

Toda la produccion entra como dato, **incluidos los valores que salen de un calculo interno**, y
[corroboracion.py](packages/engine/src/minsur_engine/corroboracion.py) los rehace y compara celda a
celda, con su unidad, su ano y su magnitud. Las ocho reglas no son una interpretacion nuestra: son
las formulas del bloque `Calculo Interno` del libro que MINSUR entrego el 01/09/2026, transcritas en
el docstring del modulo.

Tres propiedades que no conviene romper:

- **El dato cargado es el que usa el flujo.** El recalculo lo audita y no lo sustituye nunca; es la
  misma regla de fidelidad que impide corregir el modelo corporativo. Lo atan las dos pruebas de
  `test_corroboracion.py::TestElDatoDelUsuarioEsElQueManda`, y si alguna falla es que el recalculo
  se colo en el calculo.
- **Corroborar nunca detiene el calculo.** Un caso con una ley mal tecleada llega hasta el NPV para
  que se vea el efecto.
- **El informe viaja en la corrida** y se congela con ella. Sin eso no se puede sustentar despues
  por que se acepto una diferencia.

La tolerancia de corroboracion **no es la del contraste N1**: aquella compara el motor contra el
libro y la fija Finanzas (`R-31`); esta compara el dato del usuario contra el recalculo del propio
sistema, y el 0,5 % de `TOLERANCIA_POR_DEFECTO` es propuesta de INVA.

### Seis decisiones del motor que no se deducen leyendolo

- **El unico lazo del motor esta en `impuestos.py`, y no se itera.** La hoja `Impuestos` se muerde
  la cola: el fondo de jubilacion minera es gasto de la misma utilidad operativa que sirve para
  calcularlo, y en el libro es la fila 19 leyendo la 57. El libro lo cierra con el calculo iterativo
  de Excel; el motor resuelve el sistema en forma cerrada, porque es afin a trozos, y lo contrasta
  contra un punto fijo independiente. Si `test_coincide_con_el_punto_fijo` falla, la derivacion esta
  mal aunque el resultado parezca razonable. Lo decide el
  [ADR 0009](docs/adr/0009-resolucion-de-la-circularidad-tributaria.md). El bloque expone la hoja
  entera **con el signo del libro** -ventas positivas, gastos negativos-, de modo que cada total es
  literalmente la suma de las filas que tiene encima, y eso es lo que se contrasta.
- **Los tres caminos de ingreso.** `corrida._ventas` recorre estano refinado a precio mas premio,
  estano en concentrado a precio por el factor pagable, y la liquidacion del polimetalico embarque a
  embarque. El tercero estuvo implementado, probado y sin cablear hasta el 01/09/2026: el
  concentrado de cobre se calculaba y no se cobraba.
- **Una fila entera en cero no se muestra.** `campos_con_dato()` vive en el motor y la corrida lo
  expone en `campos_con_dato_por_unidad`, para que la API y la interfaz lleguen a la misma
  conclusion del mismo caso; si cada pantalla lo resolviera por su cuenta acabarian mostrando cosas
  distintas. Vacio y todo ceros son lo mismo aqui.
- **La deuda del capital de trabajo rota sobre la bolsa de egresos, capital incluido**, no sobre el
  costo operativo. Dejar el capex fuera mueve la variacion por encima de la tolerancia de N1 justo
  en el ano de mayor desembolso. La bolsa no vuelve al flujo: cada componente ya llega por su linea.
  Y la cuenta no se mueve en un ano sin produccion, con los tres comportamientos de la regla `053`
  que fija `test_el_ciclo_cierra_salvo_lo_que_abre_antes_de_producir`.
- **El IGV se calcula entero y llega al flujo multiplicado por cero.** No es codigo muerto ni una
  omision: el bloque tiene cifras, sale en los estados financieros y su variacion entra multiplicada
  por `PESO_DEL_IGV_EN_EL_FLUJO`, que vale cero porque el libro escribe ese cero. Es la regla `014`,
  sin confirmar por Finanzas; el dia que la confirmen, cambia esa linea y nada mas.
- **Los aportes reguladores son series del caso, no tasas fijas.** MINSUR confirmo el 01/09/2026 que
  varian los primeros ejercicios porque hay mejor informacion sobre ellos. `ParametrosCorporativos`
  conserva la tasa de referencia y `DatosComunes.osinergmin` y `.oefa` la sobrescriben cuando el
  caso las declara.

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
tambien estan sujetos a `ruff` y `mypy`. Como se compilan y se analizan las plantillas esta en la
seccion 2.

---

## 5. Lo que muerde

**Los archivos de bloqueo estan versionados y CI los exige intactos.** Corre `uv sync --frozen` y
`pnpm install --frozen-lockfile`, de modo que un `uv.lock` o un `pnpm-lock.yaml` que no concuerde
con su manifiesto detiene el pipeline en el primer paso. Si cambias una dependencia, el lock
regenerado entra en el mismo commit:

```bash
uv lock
pnpm install --lockfile-only
```

`uv sync --all-packages` tambien regenera el lock si el manifiesto cambio, de modo que un
`uv.lock` modificado despues de instalar no es ruido: es el cambio que hay que versionar.

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
