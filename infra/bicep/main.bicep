// =============================================================================
// Plataforma de Evaluación Económica · Modelo MINSUR
// Servicio INVA-01-2026-182 · PT6.4
// =============================================================================
//
// Una sola plantilla para los cuatro entornos. Las diferencias viven en
// envs/*.bicepparam y nunca en el cuerpo de los módulos: es lo que hace que el
// entorno de construcción de INVA y el de producción de MINSUR no puedan
// divergir, que es la falla más frecuente en un pase corporativo.
//
// La configuración manual está prohibida en cualquier entorno del cliente.
// Si algo no está aquí, no existe.
//
// Despliegue:
//   az deployment group create -g <rg> -f main.bicep -p envs/minsur-dev.bicepparam

targetScope = 'resourceGroup'

// -----------------------------------------------------------------------------
// Identidad del despliegue
// -----------------------------------------------------------------------------

@description('Entorno destino. Gobierna dimensionamiento, redundancia y exposición.')
@allowed(['inva-build', 'minsur-dev', 'minsur-qa', 'minsur-prod'])
param entorno string

@description('Prefijo de nomenclatura corporativa. Pendiente de confirmar con TI (R-21).')
@minLength(2)
@maxLength(12)
param prefijoNombre string = 'invaminsur'

@description('Región de despliegue.')
param ubicacion string = resourceGroup().location

@description('Centro de costos de MINSUR para el etiquetado corporativo.')
param ceco string = '880001594'

@description('Etiquetas adicionales exigidas por el estándar de MINSUR.')
param etiquetasAdicionales object = {}

// -----------------------------------------------------------------------------
// Red y perímetro
// -----------------------------------------------------------------------------

@description('Crear una red virtual dedicada. Si MINSUR integra a su red existente, se pasa false y se indica idSubredIntegracion.')
param crearRedVirtual bool = true

@description('Espacio de direcciones de la red dedicada.')
param espacioDirecciones string = '10.60.0.0/22'

@description('Subred existente para la integración de las funciones, cuando crearRedVirtual es false.')
param idSubredIntegracion string = ''

@description('Subred existente para los puntos de conexión privados, cuando crearRedVirtual es false.')
param idSubredPrivada string = ''

@description('Patrón de publicación del frontend. La aplicación no cambia entre uno y otro.')
@allowed(['frontDoor', 'applicationGateway', 'ninguno'])
param patronPublicacion string = 'frontDoor'

// -----------------------------------------------------------------------------
// Dimensionamiento
// -----------------------------------------------------------------------------

@description('SKU del plan de funciones. El alcance dimensiona para siete usuarios concurrentes.')
param skuFunciones string = 'EP1'

@description('SKU de API Management. Developer no tiene acuerdo de nivel de servicio y no debe usarse en producción.')
@allowed(['Developer', 'Basic', 'Standard', 'StandardV2', 'Premium'])
param skuApim string = 'Developer'

@description('SKU de Static Web Apps. Standard es necesario para dominio propio y redes privadas.')
@allowed(['Free', 'Standard'])
param skuSwa string = 'Standard'

@description('Redundancia del almacenamiento. La criticidad declarada es media.')
@allowed(['Standard_LRS', 'Standard_ZRS', 'Standard_GRS', 'Standard_GZRS'])
param redundanciaAlmacenamiento string = 'Standard_ZRS'

@description('Objetivo de servicio de la base de datos.')
param skuBaseDatos string = 'GP_S_Gen5_2'

// -----------------------------------------------------------------------------
// Gobierno del dato
// -----------------------------------------------------------------------------

@description('Retención mínima exigida por el alcance: cinco años.')
@minValue(1825)
param diasRetencion int = 1825

@description('Aplicar inmutabilidad al contenedor de imágenes selladas. En producción no es negociable.')
param habilitarInmutabilidad bool = true

@description('Días de retención de los registros de observabilidad.')
param diasRetencionLogs int = 90

// -----------------------------------------------------------------------------
// Identidad corporativa
// -----------------------------------------------------------------------------

@description('Identificador del tenant de Entra ID.')
param idTenant string = subscription().tenantId

@description('Objeto de Entra ID que administra la base de datos. Grupo, no persona.')
param objetoAdminSql string

@description('Nombre del grupo administrador de la base de datos.')
param nombreAdminSql string

@description('Correo para las alertas de disponibilidad y latencia.')
param correoAlertas string

// -----------------------------------------------------------------------------
// Convenciones derivadas
// -----------------------------------------------------------------------------

var sufijoEntorno = last(split(entorno, '-'))
var nombreBase = '${prefijoNombre}-${sufijoEntorno}'
// Los nombres de almacenamiento no admiten guiones ni mayúsculas.
var nombreBaseCompacto = toLower(replace(nombreBase, '-', ''))
var esProduccion = entorno == 'minsur-prod'

var etiquetas = union(
  {
    Servicio: 'INVA-01-2026-182'
    Aplicacion: 'Plataforma de Evaluacion Economica'
    Entorno: entorno
    CECO: ceco
    Proveedor: 'INVA'
    Clasificacion: esProduccion ? 'Financiera-Confidencial' : 'Interna'
    Despliegue: 'IaC-Bicep'
  },
  etiquetasAdicionales
)

// =============================================================================
// Red
// =============================================================================

module red 'modules/red.bicep' = if (crearRedVirtual) {
  name: 'red'
  params: {
    nombreBase: nombreBase
    ubicacion: ubicacion
    espacioDirecciones: espacioDirecciones
    etiquetas: etiquetas
  }
}

var subredIntegracion = crearRedVirtual ? red!.outputs.idSubredIntegracion : idSubredIntegracion
var subredPrivada = crearRedVirtual ? red!.outputs.idSubredPrivada : idSubredPrivada
var idRedVirtual = crearRedVirtual ? red!.outputs.idRedVirtual : ''

// =============================================================================
// Observabilidad
// =============================================================================

module observabilidad 'modules/observabilidad.bicep' = {
  name: 'observabilidad'
  params: {
    nombreBase: nombreBase
    ubicacion: ubicacion
    diasRetencion: diasRetencionLogs
    correoAlertas: correoAlertas
    etiquetas: etiquetas
  }
}

// =============================================================================
// Identidad administrada
// =============================================================================
// Una identidad asignada por el usuario, compartida por las funciones y las
// canalizaciones. Sin credenciales embebidas en el código, conforme al
// prerrequisito de identidad del plan de traspaso.

resource identidad 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${nombreBase}-id'
  location: ubicacion
  tags: etiquetas
}

// =============================================================================
// Custodia de secretos
// =============================================================================

module boveda 'modules/boveda.bicep' = {
  name: 'boveda'
  params: {
    nombreBase: nombreBase
    ubicacion: ubicacion
    idTenant: idTenant
    idPrincipalIdentidad: identidad.properties.principalId
    idSubredPrivada: subredPrivada
    idRedVirtual: idRedVirtual
    crearZonaDns: crearRedVirtual
    etiquetas: etiquetas
  }
}

// =============================================================================
// Almacenamiento
// =============================================================================

module almacenamiento 'modules/almacenamiento.bicep' = {
  name: 'almacenamiento'
  params: {
    nombre: '${nombreBaseCompacto}st'
    ubicacion: ubicacion
    redundancia: redundanciaAlmacenamiento
    diasRetencion: diasRetencion
    habilitarInmutabilidad: habilitarInmutabilidad
    idPrincipalIdentidad: identidad.properties.principalId
    idSubredPrivada: subredPrivada
    idRedVirtual: idRedVirtual
    crearZonaDns: crearRedVirtual
    etiquetas: etiquetas
  }
}

// =============================================================================
// Base de datos
// =============================================================================

module baseDatos 'modules/base-datos.bicep' = {
  name: 'baseDatos'
  params: {
    nombreBase: nombreBase
    ubicacion: ubicacion
    sku: skuBaseDatos
    idTenant: idTenant
    objetoAdmin: objetoAdminSql
    nombreAdmin: nombreAdminSql
    idSubredPrivada: subredPrivada
    idRedVirtual: idRedVirtual
    crearZonaDns: crearRedVirtual
    diasRetencionCopias: esProduccion ? 35 : 7
    etiquetas: etiquetas
  }
}

// =============================================================================
// Servicios de aplicación
// =============================================================================

module funciones 'modules/funciones.bicep' = {
  name: 'funciones'
  params: {
    nombreBase: nombreBase
    ubicacion: ubicacion
    sku: skuFunciones
    idIdentidad: identidad.id
    idClienteIdentidad: identidad.properties.clientId
    idSubredIntegracion: subredIntegracion
    nombreAlmacenamiento: almacenamiento.outputs.nombre
    uriBoveda: boveda.outputs.uri
    cadenaAppInsights: observabilidad.outputs.cadenaConexion
    servidorSql: baseDatos.outputs.nombreServidor
    baseDatos: baseDatos.outputs.nombreBaseDatos
    crearSlot: esProduccion
    etiquetas: etiquetas
  }
}

// =============================================================================
// Puerta de enlace
// =============================================================================
// API Management es la única vía de acceso al backend. La interfaz nunca llama
// a las funciones de forma directa.

module apim 'modules/apim.bicep' = {
  name: 'apim'
  params: {
    nombreBase: nombreBase
    ubicacion: ubicacion
    sku: skuApim
    correoPublicador: correoAlertas
    idTenant: idTenant
    urlBackend: 'https://${funciones.outputs.hostname}'
    idAppInsights: observabilidad.outputs.idAppInsights
    claveAppInsights: observabilidad.outputs.claveInstrumentacion
    etiquetas: etiquetas
  }
}

// =============================================================================
// Interfaz
// =============================================================================

module interfaz 'modules/interfaz.bicep' = {
  name: 'interfaz'
  params: {
    nombreBase: nombreBase
    ubicacion: ubicacion
    sku: skuSwa
    urlApi: apim.outputs.urlPuerta
    etiquetas: etiquetas
  }
}

// =============================================================================
// Publicación
// =============================================================================
// MINSUR aún no confirmó el patrón (riesgo declarado en el plan de traspaso).
// Ambos módulos existen y se eligen por parámetro: cambiar de uno a otro no
// toca la aplicación ni obliga a reescribir la infraestructura.

module publicacionFrontDoor 'modules/publicacion-frontdoor.bicep' = if (patronPublicacion == 'frontDoor') {
  name: 'publicacionFrontDoor'
  params: {
    nombreBase: nombreBase
    hostnameOrigen: interfaz.outputs.hostname
    idSitioEstatico: interfaz.outputs.id
    modoWaf: esProduccion ? 'Prevention' : 'Detection'
    etiquetas: etiquetas
  }
}

module publicacionAppGateway 'modules/publicacion-appgateway.bicep' = if (patronPublicacion == 'applicationGateway') {
  name: 'publicacionAppGateway'
  params: {
    nombreBase: nombreBase
    ubicacion: ubicacion
    hostnameOrigen: interfaz.outputs.hostname
    idSubredPuerta: crearRedVirtual ? red!.outputs.idSubredPuerta : ''
    modoWaf: esProduccion ? 'Prevention' : 'Detection'
    etiquetas: etiquetas
  }
}

// =============================================================================
// Salidas
// =============================================================================

output entornoDesplegado string = entorno
output urlInterfaz string = patronPublicacion == 'frontDoor'
  ? 'https://${publicacionFrontDoor!.outputs.hostname}'
  : (patronPublicacion == 'applicationGateway'
      ? 'https://${publicacionAppGateway!.outputs.hostname}'
      : 'https://${interfaz.outputs.hostname}')
output urlApi string = apim.outputs.urlPuerta
output nombreFunciones string = funciones.outputs.nombre
output nombreAlmacenamiento string = almacenamiento.outputs.nombre
output uriBoveda string = boveda.outputs.uri
output idIdentidad string = identidad.id
output servidorSql string = baseDatos.outputs.nombreServidor
