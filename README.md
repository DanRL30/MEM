# Plataforma de Evaluación Económica · Modelo MINSUR

Monorepo de la solución. **Esta carpeta es la raíz del repositorio en Azure DevOps Repos.**

Contexto del servicio: [../README.md](../README.md)
Convenciones de ingenieria: [docs/convenciones.md](docs/convenciones.md)

## Stack

| Capa | Tecnología | Servicio Azure |
|---|---|---|
| Interfaz | React 18 + TypeScript + Vite, Recharts/ECharts, MSAL | Static Web Apps |
| Puerta de enlace | — | **API Management** |
| Servicios | FastAPI + Pydantic (Python 3.12) | Functions o Container Apps |
| Cálculo | NumPy, numpy-financial, pandas, SciPy | — |
| Plantillas y reportes | openpyxl + composición PDF | — |
| Persistencia | — | **Azure SQL** + Storage Blob/Table |
| Secretos | — | Key Vault + identidad administrada |
| Identidad | MSAL | Entra ID, 6 perfiles |
| IaC | Bicep | — |
| CI/CD | Azure Pipelines + Sonar | Azure DevOps |

## Estructura

```
apps/         api (FastAPI) y web (React)
packages/     engine · ingest · domain · risk · reporting · contracts
infra/        bicep/{modules,envs} · policy · pipelines
tests/        fidelidad/{casos,niveles} · e2e · rendimiento
fixtures/     sinteticos (versionados) · certificados (solo manifiestos)
docs/         adr · arquitectura · modelo-economico · operacion · seguridad · usuario
scripts/
```

## Entornos

| Entorno | Suscripción | Datos | Desde |
|---|---|---|---|
| Construcción | INVA | Sintéticos | 24/08/2026 |
| Desarrollo | MINSUR | Sintéticos y casos de contraste | 09/09/2026 (H10) |
| Calidad | MINSUR | Casos reales bajo control de Finanzas | 18/09/2026 (H11) |
| Producción | MINSUR | Evaluaciones reales, clasificación confidencial | 12/10/2026 (H8) |

Los cuatro se aprovisionan con **la misma plantilla Bicep**, diferenciada solo por parámetros.
Configuración manual prohibida en cualquier entorno del cliente.

## Puesta en marcha

Requisitos previos, una sola vez por máquina:

```bash
python -m pip install --user uv
npm install --global pnpm
```

Ambos gestionan el resto: `uv` crea y sincroniza el entorno virtual de Python 3.12 a partir de
`pyproject.toml`, y `pnpm` resuelve el espacio de trabajo declarado en `pnpm-workspace.yaml`.
Node 20 o superior.

```bash
uv sync
pnpm install
uv run pytest
pnpm --filter web dev
```

`uv run` ejecuta dentro del entorno del proyecto sin necesidad de activarlo. Las comprobaciones que
corren también en integración continua:

```bash
uv run ruff check .
uv run mypy --strict packages apps/api/src
uv run pytest --cov
```

> El repositorio, los pipelines y Sonar se crean en Azure DevOps una vez habilitados por TI
> (`R-24`). Hasta entonces, trabaja en local contra el entorno espejo de INVA (PT6.2).
