// Static Web Apps: la interfaz de React.
//
// El SKU Free no admite dominio corporativo con certificado gestionado ni
// restricciones de red, así que en cualquier entorno del cliente se usa
// Standard.

param nombreBase string
param ubicacion string
param sku string
param urlApi string
param etiquetas object

// Static Web Apps no está disponible en todas las regiones. Se ancla a una
// región soportada y se documenta: es una limitación del servicio, no una
// decisión de arquitectura.
@description('Región de Static Web Apps. Debe ser una de las soportadas por el servicio.')
param ubicacionSwa string = ubicacion

resource sitio 'Microsoft.Web/staticSites@2023-12-01' = {
  name: '${nombreBase}-swa'
  location: ubicacionSwa
  tags: etiquetas
  sku: {
    name: sku
    tier: sku
  }
  properties: {
    // El despliegue lo hace la canalización con el token de la aplicación,
    // no una integración directa con el repositorio.
    allowConfigFileUpdates: true
    stagingEnvironmentPolicy: 'Enabled'
    enterpriseGradeCdnStatus: 'Disabled'
  }
}

resource configuracion 'Microsoft.Web/staticSites/config@2023-12-01' = {
  parent: sitio
  name: 'appsettings'
  properties: {
    VITE_API_ORIGIN: urlApi
  }
}

output id string = sitio.id
output nombre string = sitio.name
output hostname string = sitio.properties.defaultHostname
