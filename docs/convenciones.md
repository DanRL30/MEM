# Convenciones de ingenieria

Servicio `INVA-01-2026-182` - Plataforma de Evaluacion Economica, Modelo MINSUR

Este codigo se entrega a MINSUR al cierre del servicio y queda bajo su titularidad. Las reglas de
este documento existen para que se lea como el trabajo de un unico equipo y no como la suma de
estilos individuales.

---

> La regla no depende de la disciplina de quien escribe: `scripts/verificar_convenciones.py` la
> comprueba en cada integracion y en local. Devuelve la ruta y la linea de cada infraccion.
>
> ```bash
> python scripts/verificar_convenciones.py
> ```

## 1. Estructura del monorepo

| Ruta | Responsabilidad | Hace E/S |
|---|---|---|
| `apps/api` | Exponer servicios HTTP, autenticar, autorizar por perfil | Si |
| `apps/web` | Interfaz de usuario | Si, solo contra `apps/api` |
| `packages/engine` | Calculo economico | **No** |
| `packages/ingest` | Leer y validar plantillas Excel | Si, lectura |
| `packages/domain` | Casos, corridas, versionado, estados, auditoria | Si, persistencia |
| `packages/risk` | Sensibilidad, escenarios, Montecarlo | **No** |
| `packages/reporting` | Exportar a Excel y PDF | Si, escritura |
| `packages/contracts` | Tipos compartidos generados desde OpenAPI | No |

La dependencia va en un solo sentido:

```
apps/api  ->  domain, ingest, risk, reporting  ->  engine  ->  (nada interno)
```

**El motor no importa nada del resto del arbol.** No lee Excel, no toca red, no consulta la base de
datos. Recibe estructuras validadas y devuelve series.

No es purismo: es la condicion para que una corrida sea funcion exclusiva de sus entradas, y por
tanto reproducible. Si el motor pudiera leer un archivo o consultar la base, una evaluacion
congelada dejaria de poder recalcularse con garantia de obtener el mismo resultado.

---

## 2. Estilo de codigo

### Prohibido en cualquier archivo del repositorio

| Elemento | Regla |
|---|---|
| Emojis | En ningun sitio: codigo, comentarios, documentacion, mensajes de commit, salida de consola |
| Caracteres de dibujo de caja | Los separadores y los diagramas se escriben en ASCII, que es portable entre terminales y no depende de la fuente instalada |
| Comentarios de proceso | Nada de "aqui anadimos", "ahora vamos a", "version mejorada". El comentario explica el codigo, no como llego a existir |
| Marcadores de andamiaje | Sin `TODO` sin responsable, sin `FIXME` generico, sin codigo comentado por si acaso |
| Ejemplos de relleno | Sin `foo`, `bar`, `lorem`. Los ejemplos usan datos del dominio: casos, comites de precios, lineas del flujo |

### Separadores de seccion

```python
# --- Serializacion canonica --------------------------------------------------
```

Una linea, ASCII, hasta la columna 79. En TypeScript, `// ---`. En YAML y Bicep, `# ---`.

### Comentarios

Un comentario explica **por que**, no **que**. Si describe lo que la linea siguiente ya dice, sobra.

```python
# Correcto: explica una decision que el codigo no puede expresar
# Sin pausa, serverless factura el minimo las 730 horas del mes y supera a la
# capacidad aprovisionada, que es lo contrario de lo que se busca al elegirlo.
autoPauseDelay = 60

# Incorrecto: repite el codigo
# Asigna 60 a autoPauseDelay
autoPauseDelay = 60
```

Los docstrings de modulo explican el proposito y las decisiones estructurales. Los de funcion, el
contrato y las condiciones de error.

### Nombres

Espanol para el dominio, ingles para lo que el lenguaje o la libreria imponen.

```python
def congelar_evaluacion(id_caso: str, motivo: str) -> ImagenSellada: ...


class TernaVersion: ...


router = APIRouter()  # el termino lo fija FastAPI
```

Sin abreviaturas inventadas: `evaluacion`, no `eval`; `parametros`, no `params`.

### Tipado y errores

- Anotaciones de tipo completas en Python. `mypy --strict` pasa.
- Las excepciones llevan mensaje accionable: que fallo y que hacer. Nunca `raise Exception("error")`.
- Un fallo no esperado se registra con detalle y se devuelve sin detalle: un mensaje de excepcion
  puede revelar rutas, consultas o nombres de recursos.

### Paquetes Python

Disposicion `src/`, prefijo `minsur_`, `snake_case`. Build backend `hatchling`, gestion con `uv`.

---

## 3. Reglas del motor de calculo

1. Funciones puras sobre series de `pandas` y arreglos de `numpy`. Sin estado global.
2. **Un modulo por linea del contraste N1** (`docs/modelo-economico/mapa-n1.md`). No se fusionan
   bloques: la trazabilidad del contraste depende de esa correspondencia, y es lo que permite
   localizar una discrepancia en un archivo en lugar de en el conjunto.
3. Cero constantes economicas en el codigo. Todo parametro viene de `parametros.py`, alimentado por
   la version de datos maestros de la corrida.
4. Cada regla replicada del modelo de referencia lleva un comentario que cita su origen (hoja y
   celda) y el numero de entrada en `docs/modelo-economico/reglas-no-documentadas.md`.
5. Nada de comparar `float` con `==` en las pruebas. Se usan las tolerancias de N0 a N3.

### Fidelidad antes que elegancia

El motor reproduce la logica del modelo economico corporativo, incluidos sus redondeos y valores
incrustados. Si se detecta un error metodologico en el modelo, **se documenta y se reporta, no se
corrige**: la correccion metodologica del modelo permanece bajo responsabilidad de MINSUR conforme a
las exclusiones del alcance.

---

## 4. Pruebas

| Suite | Comando | Cuando corre |
|---|---|---|
| Unitarias | `pytest packages/*/tests` | Cada commit |
| Contrato de la API | `pytest apps/api/tests` | Cada commit |
| Fidelidad N0 a N3 | `pytest tests/fidelidad` | Cada commit con datos sinteticos; con casos certificados, solo en el tenant del cliente |
| Interfaz | `pnpm playwright test` | Cada solicitud de incorporacion a `main` |
| Rendimiento | `k6 run tests/rendimiento/` | Antes de la homologacion y antes del pase |

Una vez conciliado, **cada caso de la bateria se congela como prueba de regresion**. Un cambio del
motor que rompa un caso certificado no se despliega, aunque provenga de una actualizacion del modelo
corporativo.

---

## 5. Datos

- `fixtures/sinteticos/` es lo unico que se versiona.
- `fixtures/certificados/` contiene manifiestos con identificador, resumen SHA-256 y ubicacion del
  blob en el tenant de MINSUR. **Sin cifras en claro.**
- Una prueba que necesite datos reales se marca `@pytest.mark.tenant_minsur` y solo se ejecuta alli.

Los tres casos de contraste son evaluaciones economicas reales y confidenciales. No salen del
perimetro del cliente, no se copian y no se anonimizan de forma provisional.

---

## 6. Credenciales y secretos

**No se solicita ni se acepta ninguna credencial, clave, cadena de conexion o token.**

Cuando una tarea necesita acceso a un recurso protegido, el trabajo consiste en documentar el
procedimiento para configurarlo:

1. Que se necesita, con su nombre exacto y su formato.
2. Donde se configura: Key Vault, grupo de variables de Azure DevOps, configuracion de la
   aplicacion, o `.env.example` en desarrollo local.
3. Quien tiene autoridad para crearlo, con la restriccion `R-xx` si esta registrada.
4. El codigo lee el valor desde su origen configurado, con un mensaje de error que explique que
   falta si no esta presente.

```python
# Correcto
cuenta = config().cuenta_almacenamiento
if not cuenta:
    raise RuntimeError(
        "Falta ALMACENAMIENTO_CUENTA. La plantilla Bicep la inyecta en la "
        "configuracion de la aplicacion; en local se define en .env."
    )

# Prohibido
cuenta = "invaminsurprodst"
clave = "DefaultEndpointsProtocol=https;AccountKey=..."
```

La arquitectura esta disenada para que esto sea posible: identidad administrada en lugar de claves,
federacion de identidades en lugar de secretos de despliegue, y `allowSharedKeyAccess` deshabilitado
en el almacenamiento. **Si una tarea parece exigir una credencial en el codigo, es senal de un error
de diseno, no de que haga falta la credencial.**

### Archivos que nunca se versionan

`.env`, `*.pem`, `*.pfx`, `*.key`, `local.settings.json` y cualquier `*.parameters.local.json`.
Estan en `.gitignore`. El archivo `.env.example` si se versiona, con los nombres de las variables y
sin un solo valor real.

---

## 7. Mensajes de commit

```
Resumen en imperativo, sin punto final, hasta 72 caracteres

Cuerpo que explica el porque del cambio y las decisiones no obvias.
Ancho de 72 columnas. Se citan las restricciones y actividades del
cronograma cuando aplique (R-02, PT6.4, H8).
```

- Sin emojis, sin prefijos decorativos, sin trailers de coautoria de herramientas.
- El cuerpo describe el estado del codigo, no el proceso que lo produjo.
- Si el cambio corrige un error propio, se dice que era y por que importaba.

El enlace `.githooks/commit-msg` verifica estas reglas. Se activa una sola vez por copia de trabajo:

```
git config core.hooksPath .githooks
```

---

## 8. Infraestructura

- Un solo juego de plantillas Bicep en `infra/bicep/modules/`, parametrizado por entorno en
  `infra/bicep/envs/`. Si un entorno necesita algo distinto, la diferencia va en parametros, no en
  una copia del modulo.
- `infra/policy/` valida contra Azure Policy corporativo antes de aprovisionar. Un despliegue que no
  pase esa validacion no se intenta en el tenant del cliente.
- **Configuracion manual prohibida en cualquier entorno del cliente.** Es la garantia de que el
  entorno homologado y el productivo no puedan divergir.

---

## 9. Antes de abrir una solicitud de incorporacion

- [ ] `ruff` y `mypy` limpios
- [ ] `pytest` verde, incluidas las suites de fidelidad disponibles
- [ ] `bandit` y `pip-audit` sin hallazgos criticos ni altos
- [ ] Sonar sin incidencias bloqueantes
- [ ] Si cambia una regla de calculo: entrada nueva en `reglas-no-documentadas.md` con la
      confirmacion de Finanzas
- [ ] Si cambia una decision estructural: registro de decision en `docs/adr/`
