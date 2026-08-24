# CLAUDE.md — Monorepo de la plataforma

Complementa el [CLAUDE.md raíz](../CLAUDE.md). Aquí van las reglas que aplican al código.

## Qué es cada cosa

| Ruta | Responsabilidad | Puede hacer I/O |
|---|---|---|
| `apps/api` | Exponer servicios HTTP, autenticar, autorizar por perfil | Sí |
| `apps/web` | Interfaz de usuario | Sí (solo contra `apps/api`) |
| `packages/engine` | Cálculo económico | **No** |
| `packages/ingest` | Leer y validar plantillas Excel | Sí (lectura) |
| `packages/domain` | Casos, corridas, versionado, estados, auditoría | Sí (persistencia) |
| `packages/risk` | Sensibilidad, escenarios, Montecarlo | **No** |
| `packages/reporting` | Exportar a Excel y PDF | Sí (escritura) |
| `packages/contracts` | Tipos compartidos generados desde OpenAPI | No |

**El motor no importa nada de `apps/`, `ingest`, `domain` ni `reporting`.** La dependencia va en un
solo sentido: `apps → domain → engine`. Si el motor necesita un dato, se le pasa como argumento.

## Flujo de tipos

FastAPI genera OpenAPI → `packages/contracts` genera los tipos TypeScript → `apps/web` los consume.
Nunca escribas a mano un tipo del frontend que ya exista en el esquema Pydantic. Regenera.

## Reglas del motor

1. Funciones puras sobre series de `pandas` / arreglos de `numpy`. Sin estado global.
2. Un módulo por línea del contraste N1 (`docs/modelo-economico/mapa-n1.md`). No fusiones bloques:
   la trazabilidad del contraste depende de esa correspondencia.
3. Cero constantes económicas en el código. Todo parámetro viene de `parametros.py`, alimentado por
   la versión de datos maestros de la corrida.
4. Cada regla replicada del modelo de referencia lleva un comentario que cita su origen
   (hoja y celda) y el número de entrada en `reglas-no-documentadas.md`.
5. Nada de `float` comparado con `==` en las pruebas. Usa las tolerancias de N0–N3.

## Pruebas

| Suite | Comando | Cuándo corre |
|---|---|---|
| Unitarias | `pytest packages/*/tests` | Cada commit |
| Fidelidad N0–N3 | `pytest tests/fidelidad` | Cada commit, con fixtures sintéticos. Con los casos certificados, solo en el entorno del cliente |
| E2E | `pnpm playwright test` | Cada PR a `main` |
| Rendimiento | `k6 run tests/rendimiento/` | Antes de H11 y antes del pase |

Una vez conciliado, **cada caso de la batería se congela como prueba de regresión**. Un cambio del
motor que rompa un caso certificado no se despliega, aunque venga de una actualización del modelo
corporativo.

## Datos

- `fixtures/sinteticos/` es lo único que se versiona.
- `fixtures/certificados/` contiene manifiestos: `caso-id`, `sha256`, `uri` del blob en el tenant de
  MINSUR y resultados esperados **como referencia a la evidencia, no como cifras en claro**.
- Si un test necesita datos reales, se marca `@pytest.mark.tenant_minsur` y solo corre allí.

## Infraestructura

- Un solo juego de plantillas Bicep en `infra/bicep/modules/`, parametrizado por entorno en
  `infra/bicep/envs/`. Si un entorno necesita un módulo distinto, la diferencia va en parámetros,
  no en una copia del módulo.
- `infra/policy/` valida contra Azure Policy corporativo **antes** de aprovisionar (PT6.5). Un
  despliegue que no pase esa validación no se intenta en el tenant del cliente.
- El patrón de publicación debe soportar **Front Door y Application Gateway** sin tocar la
  aplicación. MINSUR aún no lo ha confirmado.

## Antes de abrir un PR

- [ ] `ruff` y `mypy` limpios
- [ ] `pytest` verde, incluidas las suites de fidelidad disponibles
- [ ] `bandit` y `pip-audit` sin hallazgos críticos ni altos
- [ ] Sonar sin issues bloqueantes
- [ ] Si cambia una regla de cálculo: entrada nueva en `reglas-no-documentadas.md` con la
      confirmación de Finanzas
- [ ] Si cambia una decisión estructural: ADR en `docs/adr/`
