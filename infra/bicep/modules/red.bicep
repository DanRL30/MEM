// Red virtual dedicada y subredes del servicio.
//
// Solo se despliega si MINSUR no integra la solución a su red corporativa
// existente. Esa decisión es de TI y está pendiente (R-22).
//
// Tres subredes con propósitos que no se mezclan:
//   integracion  delegada a las funciones, para su salida hacia la VNet
//   privada      puntos de conexión privados de almacenamiento, bóveda y SQL
//   puerta       exclusiva de Application Gateway, si ese es el patrón elegido

param nombreBase string
param ubicacion string
param espacioDirecciones string
param etiquetas object

// /22 dividido en tres /24. El resto queda libre para crecimiento sin
// reasignar el espacio ya en uso.
var prefijo = split(espacioDirecciones, '/')[0]
var octetos = split(prefijo, '.')
var base = '${octetos[0]}.${octetos[1]}'
var tercerOcteto = int(octetos[2])

resource redVirtual 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: '${nombreBase}-vnet'
  location: ubicacion
  tags: etiquetas
  properties: {
    addressSpace: {
      addressPrefixes: [espacioDirecciones]
    }
    subnets: [
      {
        name: 'integracion'
        properties: {
          addressPrefix: '${base}.${tercerOcteto}.0/24'
          delegations: [
            {
              name: 'delegacion-funciones'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ]
          privateEndpointNetworkPolicies: 'Enabled'
          serviceEndpoints: [
            { service: 'Microsoft.Storage' }
            { service: 'Microsoft.KeyVault' }
            { service: 'Microsoft.Sql' }
          ]
        }
      }
      {
        name: 'privada'
        properties: {
          addressPrefix: '${base}.${tercerOcteto + 1}.0/24'
          // Los puntos de conexión privados exigen que las políticas de red
          // estén deshabilitadas en su subred.
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: 'puerta'
        properties: {
          addressPrefix: '${base}.${tercerOcteto + 2}.0/24'
        }
      }
    ]
  }
}

output idRedVirtual string = redVirtual.id
output nombreRedVirtual string = redVirtual.name
output idSubredIntegracion string = redVirtual.properties.subnets[0].id
output idSubredPrivada string = redVirtual.properties.subnets[1].id
output idSubredPuerta string = redVirtual.properties.subnets[2].id
