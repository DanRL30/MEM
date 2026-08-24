// Servicios de aplicación: FastAPI sobre Azure Functions.
//
// El plan admite Functions o Container Apps. Se eligió Functions por integrarse
// de forma nativa con la identidad administrada y con el modelo de escalado que
// pide el alcance: siete usuarios concurrentes, con evaluaciones que son
// ráfagas de cómputo, no carga sostenida.
//
// Elastic Premium en lugar de Consumo porque el servicio necesita dos cosas que
// el plan de consumo no ofrece: integración con la red virtual —sin ella no hay
// puntos de conexión privados— y ranuras de despliegue, que son lo que permite
// revertir el pase con un intercambio en vez de un redespliegue dentro de la
// ventana de seis horas.

param nombreBase string
param ubicacion string
param sku string
param idIdentidad string
param idClienteIdentidad string
param idSubredIntegracion string
param nombreAlmacenamiento string
param uriBoveda string
param cadenaAppInsights string
param servidorSql string
param baseDatos string
param crearSlot bool
param etiquetas object

var esElastico = startsWith(sku, 'EP')

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${nombreBase}-plan'
  location: ubicacion
  tags: etiquetas
  sku: {
    name: sku
    tier: esElastico ? 'ElasticPremium' : 'Dynamic'
  }
  kind: esElastico ? 'elastic' : 'functionapp'
  properties: {
    reserved: true // Linux
    maximumElasticWorkerCount: esElastico ? 3 : null
  }
}

var configuracionComun = [
  {
    name: 'FUNCTIONS_EXTENSION_VERSION'
    value: '~4'
  }
  {
    name: 'FUNCTIONS_WORKER_RUNTIME'
    value: 'python'
  }
  // Almacenamiento por identidad, no por cadena de conexión: la cuenta tiene
  // deshabilitado el acceso por clave compartida.
  {
    name: 'AzureWebJobsStorage__accountName'
    value: nombreAlmacenamiento
  }
  {
    name: 'AzureWebJobsStorage__credential'
    value: 'managedidentity'
  }
  {
    name: 'AzureWebJobsStorage__clientId'
    value: idClienteIdentidad
  }
  {
    name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
    value: cadenaAppInsights
  }
  {
    name: 'AZURE_CLIENT_ID'
    value: idClienteIdentidad
  }
  {
    name: 'KEY_VAULT_URI'
    value: uriBoveda
  }
  {
    name: 'ALMACENAMIENTO_CUENTA'
    value: nombreAlmacenamiento
  }
  {
    name: 'SQL_SERVIDOR'
    value: '${servidorSql}${environment().suffixes.sqlServerHostname}'
  }
  {
    name: 'SQL_BASE_DATOS'
    value: baseDatos
  }
  // Todo el tráfico de salida atraviesa la red virtual, incluido el que va a
  // los servicios de Azure. Sin esto, los puntos de conexión privados quedan
  // parcialmente sin efecto.
  {
    name: 'WEBSITE_VNET_ROUTE_ALL'
    value: '1'
  }
  {
    name: 'WEBSITE_CONTENTOVERVNET'
    value: '1'
  }
]

resource funciones 'Microsoft.Web/sites@2023-12-01' = {
  name: '${nombreBase}-func'
  location: ubicacion
  tags: etiquetas
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${idIdentidad}': {}
    }
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    virtualNetworkSubnetId: empty(idSubredIntegracion) ? null : idSubredIntegracion
    keyVaultReferenceIdentity: idIdentidad
    siteConfig: {
      linuxFxVersion: 'Python|3.12'
      // alwaysOn no aplica a Elastic Premium: alli el calentamiento se
      // controla con instancias siempre listas.
      alwaysOn: false
      minimumElasticInstanceCount: esElastico ? 1 : null
      functionAppScaleLimit: esElastico ? 5 : null
      http20Enabled: true
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      vnetRouteAllEnabled: !empty(idSubredIntegracion)
      appSettings: configuracionComun
      // La única puerta al backend es API Management. Restringir aquí evita que
      // un descuido de configuración exponga las funciones de forma directa.
      ipSecurityRestrictions: [
        {
          ipAddress: 'ApiManagement'
          tag: 'ServiceTag'
          action: 'Allow'
          priority: 100
          name: 'solo-apim'
        }
        {
          ipAddress: 'Any'
          action: 'Deny'
          priority: 2147483647
          name: 'denegar-el-resto'
        }
      ]
    }
  }
}

// Ranura de preparación: el pase despliega aquí, se verifica y recién entonces
// se intercambia. Revertir es volver a intercambiar.
resource slot 'Microsoft.Web/sites/slots@2023-12-01' = if (crearSlot) {
  parent: funciones
  name: 'preparacion'
  location: ubicacion
  tags: etiquetas
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${idIdentidad}': {}
    }
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    virtualNetworkSubnetId: empty(idSubredIntegracion) ? null : idSubredIntegracion
    keyVaultReferenceIdentity: idIdentidad
    siteConfig: {
      linuxFxVersion: 'Python|3.12'
      alwaysOn: false
      minimumElasticInstanceCount: esElastico ? 1 : null
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      vnetRouteAllEnabled: !empty(idSubredIntegracion)
      appSettings: configuracionComun
    }
  }
}

output nombre string = funciones.name
output id string = funciones.id
output hostname string = funciones.properties.defaultHostName
output idPrincipal string = idClienteIdentidad
