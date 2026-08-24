# Infraestructura como código

Servicio `INVA-01-2026-182` · PT6.4, PT6.5, PT6.7, PT6.9, PT6.12

Una sola plantilla para los cuatro entornos. Las diferencias viven en
`envs/*.bicepparam` y **nunca** en el cuerpo de los módulos: es lo que impide que el entorno de
construcción de INVA y el de producción de MINSUR diverjan, que es la causa más frecuente de fallo
en un pase corporativo.

La configuración manual está prohibida en cualquier entorno del cliente. Si algo no está aquí, no
existe.

## Estructura

```
main.bicep                        Orquestador
modules/
  red.bicep                       VNet y tres subredes
  punto-privado.bicep             Patrón reutilizable de private endpoint + DNS
  boveda.bicep                    Key Vault con RBAC
  almacenamiento.bicep            Blob, Table, inmutabilidad y ciclo de vida
  base-datos.bicep                Azure SQL, solo Entra ID
  funciones.bicep                 Plan, Function App y ranura de preparación
  apim.bicep                      API Management y política global
  interfaz.bicep                  Static Web Apps
  observabilidad.bicep            Log Analytics, App Insights y alertas
  publicacion-frontdoor.bicep     Patrón A
  publicacion-appgateway.bicep    Patrón B
envs/
  inva-build.bicepparam           Construcción · suscripción de INVA
  minsur-dev.bicepparam           Desarrollo · tenant MINSUR
  minsur-qa.bicepparam            Calidad · tenant MINSUR
  minsur-prod.bicepparam          Producción · tenant MINSUR
```

## Decisiones que conviene entender antes de tocar nada

**Sin claves de cuenta.** `allowSharedKeyAccess` está en `false` en el almacenamiento y la base de
datos usa `azureADOnlyAuthentication`. No hay contraseña de administrador que custodiar. Un
servicio que no tiene contraseña no puede filtrarla. La consecuencia práctica: las funciones
acceden al almacenamiento por identidad (`AzureWebJobsStorage__accountName`), no por cadena de
conexión — cambiar eso rompe el modelo entero.

**El backend solo acepta tráfico de API Management.** La restricción de IP usa el service tag
`ApiManagement`, no `AzureFrontDoor`: Front Door publica la *interfaz*, y quien alcanza las
funciones es APIM. Confundirlos deja el backend expuesto.

**Elastic Premium, no Consumo.** El plan de consumo no ofrece integración con red virtual —sin ella
no hay puntos de conexión privados— ni ranuras de despliegue, que son lo que permite revertir el
pase con un intercambio en lugar de un redespliegue dentro de una ventana de seis horas.

**Los dos patrones de publicación coexisten.** MINSUR no ha confirmado si aplica Front Door o
Application Gateway; el plan de traspaso lo declara como riesgo. Ambos módulos están escritos y se
eligen con `patronPublicacion`. Cambiar de uno a otro no toca la aplicación. Por eso `red.bicep`
reserva la subred `puerta` aunque el patrón elegido sea Front Door: cambiar después no debe obligar
a redireccionar espacio de direcciones ya en uso.

## La inmutabilidad, con cuidado

El alcance exige que una evaluación congelada no pueda alterarla ni un administrador de la
suscripción. Eso se implementa con una política de inmutabilidad basada en tiempo sobre el
contenedor `selladas`, con 1825 días (cinco años).

**La plantilla crea la política desbloqueada.** El bloqueo es irreversible: una vez bloqueada no se
puede reducir ni eliminar durante el periodo de retención, ni siquiera borrando la suscripción de
forma ordenada. Por eso no se hace desde un despliegue automático, sino como paso explícito del
pase (P4), con TI presente:

```bash
az storage container immutability-policy lock --account-name <cuenta> --container-name selladas --if-match <etag>
```

Hasta que se ejecute ese comando, el requisito de congelamiento está implementado pero **no
garantizado**. Conviene que quede en el acta de pase, no en la memoria de alguien.

El ciclo de vida no borra nada: con inmutabilidad activa no podría, y la retención mínima lo
prohíbe. Solo mueve a niveles de menor costo.

## Cómo se usa

Validar sin desplegar:

```bash
az bicep build --file infra/bicep/main.bicep --stdout > /dev/null
```

Ver qué cambiaría en un entorno existente:

```bash
az deployment group what-if -g <rg> -f infra/bicep/main.bicep -p infra/bicep/envs/minsur-dev.bicepparam
```

Desplegar:

```bash
az deployment group create -g <rg> -f infra/bicep/main.bicep -p infra/bicep/envs/minsur-dev.bicepparam
```

`what-if` falla si una definición de Azure Policy corporativa deniega algún recurso. Ese fallo es el
objetivo de PT6.5, no un accidente: se descubre en la validación y no en la homologación de la
semana del 5 de octubre, cuando la holgura para corregir es cero.

## Lo que falta y por qué

Estos valores están como marcador y **deben completarse antes del primer despliegue real**:

| Parámetro | Falta | Restricción |
|---|---|---|
| `objetoAdminSql` | GUID del grupo de Entra ID administrador | `R-25` |
| `prefijoNombre` | Estándar de nomenclatura corporativa | `R-21` |
| `crearRedVirtual` | Si MINSUR integra a su red existente, pasa a `false` | `R-22` |
| `patronPublicacion` | Front Door o Application Gateway | `R-22` |
| `ubicacion` | Región corporativa autorizada | `R-11` |
| Certificado TLS y dominio | El escucha HTTPS de App Gateway aún no se declara | `R-48` |

`objetoAdminSql` está en ceros a propósito: un GUID inventado desplegaría una base con un
administrador que no existe, y el fallo aparecería recién al intentar conectarse.

## Advertencias de tiempo

- **API Management tarda entre 30 y 45 minutos en aprovisionarse** (Developer y Premium), y los
  cambios de red otro tanto. Está contemplado en PT6.7, pero no conviene descubrirlo durante la
  ventana de pase.
- **Static Web Apps no está disponible en todas las regiones.** Si la región corporativa de MINSUR
  no la soporta, `ubicacionSwa` permite anclarla a otra sin mover el resto del servicio.
- **La protección contra purga de Key Vault es irreversible.** Está en `true` por defecto; en el
  entorno de construcción de INVA conviene evaluarlo, porque impide recrear la bóveda con el mismo
  nombre durante 90 días.
