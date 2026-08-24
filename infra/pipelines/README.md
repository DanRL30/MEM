# Canalizaciones de Azure DevOps

Servicio `INVA-01-2026-182` · PT6.8 · Depende de `R-24` (Azure DevOps habilitado por TI)

## Qué hay aquí

| Pipeline | Disparo | Propósito |
|---|---|---|
| `ci.yml` | PR y push a `main` | Lint, tipos, pruebas, build, Sonar, SAST y SCA |
| `cd.yml` | Al completar CI en `main` | Dev → QA → Producción, con aprobaciones y verificación de pase |
| `iac-validate.yml` | Cambios en `infra/` · manual | Compila Bicep, `what-if`, Azure Policy y aprovisionamiento |
| `security-dast.yml` | Nocturno · manual | OWASP ZAP y paquete de evidencia para SecOps (PT6.10) |
| `fidelidad-tenant.yml` | Cambios en el motor · diario | Regresión N0–N3 contra los casos certificados (PT4.5) |

`templates/` contiene los pasos reutilizables; `scripts/` la lógica que no cabe en YAML.

## Por qué están separados

**CI y CD son pipelines distintos** porque el artefacto que pasa calidad debe ser el mismo que
llega a producción. Si el despliegue reconstruyera, no habría garantía de que lo verificado es lo
desplegado.

**La IaC va aparte** porque su ciclo es independiente del desarrollo. El aprovisionamiento en el
tenant de MINSUR arranca el 31/08, seis semanas antes del pase: los tiempos de identidad, red y
aprobaciones de seguridad corporativa no siguen el ritmo del código.

**La fidelidad contra casos reales va aparte** porque solo puede correr dentro del tenant de
MINSUR, sobre un agente autoalojado. Los tres casos de contraste no salen del perímetro del cliente.

## Lo que TI debe crear antes (`R-24`, `R-25`)

### Conexiones de servicio

Todas con **federación de identidades de carga de trabajo**, no con secretos de cliente. El rol es
Contributor **acotado al grupo de recursos del servicio**, nunca a la suscripción.

| Nombre | Alcance |
|---|---|
| `minsur-dev` | Grupo de recursos de desarrollo |
| `minsur-qa` | Grupo de recursos de calidad |
| `minsur-prod` | Grupo de recursos de producción |
| `sonarqube-minsur` | Servidor SonarQube corporativo |

### Entornos y aprobaciones

**Las aprobaciones no viven en el YAML.** Se configuran en el Environment, en la UI de Azure DevOps:
*Pipelines → Environments → [entorno] → Approvals and checks*.

| Environment | Aprobadores | Verificaciones |
|---|---|---|
| `minsur-dev` | ninguno | — |
| `minsur-qa` | Arquitecto INVA | — |
| `minsur-prod` | **TI MINSUR + Product Owner** | Ventana de despliegue: domingo 00:00–06:00 |

La autorización de pase a producción tiene doble A en la matriz RACI (Product Owner y TI). El
entorno debe reflejarlo: dos aprobadores, no uno.

### Grupos de variables

`minsur-comun`, vinculado a Key Vault:

```
serviceConnectionDev / serviceConnectionQa / serviceConnectionProd
rgDev / rgQa / rgProd
urlDev / urlQa / urlProd
functionApp-minsur-dev / -qa / -prod
apim-minsur-dev / -qa / -prod
backendUrl-minsur-dev / -qa / -prod
swaToken-minsur-dev / -qa / -prod     ← secretos
sonarServiceConnection / sonarProjectKey
ghazdoHabilitado                      ← "true" solo si TI licencia GHAzDO
```

`minsur-fidelidad`, solo para el agente dentro del tenant:

```
poolMinsur              nombre del pool autoalojado
cuentaContraste         cuenta de almacenamiento de los casos certificados
muestraCongeladas       cuántas corridas congeladas se reverifican por corrida
CASO_BASE_ID            identificador del caso base de contraste
SLO_EVALUACION_S        umbral de la evaluación estándar (pendiente, R-51)
TOKEN_ADMINISTRADOR … TOKEN_AUDITOR   ← seis tokens de prueba, uno por perfil
```

### Extensiones del Marketplace

- **SonarQube** (tasks `SonarQubePrepare/Analyze/Publish@6`)
- **Sonar Build Breaker** (opcional; rompe la compilación si la compuerta falla)
- **GitHub Advanced Security for Azure DevOps** — solo si TI la licencia. Sin ella, CodeQL queda
  desactivado y la cobertura de SAST la da Bandit.

## Política de compuertas

El criterio es el escalonado que se lleva a MINSUR como `R-29`:

| Severidad | En rama de trabajo | En `main` y `release/*` | Antes del pase |
|---|---|---|---|
| Crítica / Alta | avisa | **bloquea** | **bloquea** |
| Media / Baja | avisa | avisa | se difiere a segunda fase |

Sin ese escalonamiento cualquier vulnerabilidad menor en una librería de terceros detiene el pase.
El propio cliente advirtió en el KOM que con Python y librerías de terceros eso es frecuente, y por
eso propuso priorizar críticas y altas antes de la salida productiva.

## La ventana de producción

`cd.yml` implementa el procedimiento del Plan de Trabajo:

1. Despliega al slot `preparacion`, no directo a producción.
2. Ejecuta las **cinco comprobaciones obligatorias** (`scripts/verificacion_pase.py`).
3. Si todas pasan, intercambia el slot y procede el acta.
4. Si alguna falla, revierte con un swap y reprograma al domingo siguiente.

Revertir es un intercambio de slot, no un redespliegue: dentro de una ventana de seis horas esa
diferencia decide si se alcanza a revertir. La infraestructura no se toca — es idempotente y está
codificada.

## Antes de la primera ejecución

Los pipelines referencian recursos que aún no existen. Este es el orden real:

1. `iac-validate.yml` con `entorno: solo-validar` — comprueba que las plantillas compilan.
2. `iac-validate.yml` con `entorno: minsur-dev` — aprovisiona (PT6.7, semana del 07/09).
3. `ci.yml` — necesita el lockfile de uv y pnpm; ejecuta `uv lock` y `pnpm install` primero.
4. `cd.yml` — necesita CI publicada y los Environments creados.
5. `security-dast.yml` — necesita QA desplegado (PT6.9, semana del 14/09).
6. `fidelidad-tenant.yml` — necesita el pool autoalojado y los casos cargados (`R-30`).
