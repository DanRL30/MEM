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
del tenant del cliente por depender de datos reales, y `lento` la simulacion de Montecarlo. CI
excluye ambos:

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

### TypeScript

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm dev
```

Una sola prueba del frontend:

```bash
pnpm --filter @minsur/web test -- --run tablero
```

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

Ejecutado el 24/08/2026 sobre el arbol completo. **Todas las puertas de
[ci.yml](infra/pipelines/ci.yml) estan en verde.** Cualquier fallo es una regresion introducida
despues, no deuda heredada.

| Comprobacion | Resultado |
|---|---|
| `verificar_convenciones.py` | Sin infracciones |
| `ruff check .` | Limpio |
| `ruff format --check .` | Limpio, 46 archivos |
| `mypy packages apps/api/src` | Limpio en modo estricto, 28 archivos |
| `pytest` | 77 de 77 |
| `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build` | Limpios |

Dos cosas que conviene saber sobre como se llego aqui, porque explican decisiones que de otro modo
parecen arbitrarias:

**Las puertas se declararon antes de que existiera un entorno donde correrlas.** Hasta el
24/08/2026 nadie habia ejecutado `ruff`, `mypy` ni `pytest` sobre este arbol, y los manifiestos
arrastraban huecos que solo aparecen al ejecutar: faltaba `httpx2` para el `TestClient`, faltaba
`@types/node` para `vite.config.ts` y `vitest` 2 arrastraba un `vite` 5 paralelo al `vite` 6 de la
aplicacion. Si al añadir una herramienta algo no arranca, sospecha del manifiesto antes que del
codigo.

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

`minsur_ingest`, `minsur_risk` y `minsur_reporting` cuelgan del mismo tronco y los consume la API.
La direccion no se invierte nunca. Que el motor no importe nada de dominio ni de infraestructura es
lo que permite ejecutarlo contra el modelo de referencia sin levantar la plataforma, y es la
condicion del contraste N0-N3.

### El motor se organiza por linea de contraste

Los modulos de `packages/engine/src/minsur_engine/` mapean 1:1 con las filas de
[docs/modelo-economico/mapa-n1.md](docs/modelo-economico/mapa-n1.md). No es una preferencia
estetica: cuando una corrida difiere del modelo corporativo, la tabla de ese documento traduce la
linea discrepante a un archivo y a una prueba. Fusionar dos bloques rompe esa propiedad.

Hoy el paquete solo contiene `__init__.py`: PT2 espera la entrega del modelo de referencia (`R-02`).

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

### Las pruebas de contrato detectan deriva, no comportamiento

[test_contrato.py](apps/api/tests/test_contrato.py) hace algo poco habitual y conviene entenderlo
antes de "arreglar" un fallo suyo: lee los artefactos reales del repositorio y comprueba la
correspondencia con el esquema OpenAPI. Extrae las rutas de
`infra/pipelines/scripts/verificacion_pase.py`, verifica que `/api/salud` aparezca en
`templates/desplegar.yml` y que `package.json` siga invocando `python -m minsur_api.openapi`.

La consecuencia practica: renombrar un endpoint, mover un script de pipeline o cambiar un comando
de `package.json` rompe estas pruebas a proposito. Sin ellas, el fallo aparece durante la ventana de
mantenimiento del domingo del pase.

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

**Los umbrales de tolerancia son provisionales.** Los de `mapa-n1.md` son la propuesta de INVA. El
valor contractual lo fija Finanzas (`R-31`). Hasta entonces no se declaran como criterio de
aceptacion en ningun documento ni mensaje al cliente.
