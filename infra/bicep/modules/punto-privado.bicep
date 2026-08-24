// Punto de conexión privado con su zona DNS.
//
// Módulo reutilizable: almacenamiento, bóveda y base de datos lo consumen con
// el mismo contrato. Concentrar aquí el patrón evita que cada recurso resuelva
// el DNS privado a su manera, que es de donde salen los fallos que solo se
// manifiestan en el entorno del cliente.

param nombre string
param ubicacion string
param idRecurso string
param grupoSubrecurso string
param nombreZonaDns string
param idSubredPrivada string
param idRedVirtual string
param crearZonaDns bool
param etiquetas object

resource zona 'Microsoft.Network/privateDnsZones@2020-06-01' = if (crearZonaDns) {
  name: nombreZonaDns
  location: 'global'
  tags: etiquetas
}

resource vinculo 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = if (crearZonaDns) {
  parent: zona
  name: 'vinculo-${uniqueString(idRedVirtual)}'
  location: 'global'
  tags: etiquetas
  properties: {
    virtualNetwork: {
      id: idRedVirtual
    }
    registrationEnabled: false
  }
}

resource punto 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: nombre
  location: ubicacion
  tags: etiquetas
  properties: {
    subnet: {
      id: idSubredPrivada
    }
    privateLinkServiceConnections: [
      {
        name: nombre
        properties: {
          privateLinkServiceId: idRecurso
          groupIds: [grupoSubrecurso]
        }
      }
    ]
  }
}

resource grupoZonas 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = if (crearZonaDns) {
  parent: punto
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: replace(nombreZonaDns, '.', '-')
        properties: {
          privateDnsZoneId: zona.id
        }
      }
    ]
  }
  dependsOn: [vinculo]
}

output id string = punto.id
