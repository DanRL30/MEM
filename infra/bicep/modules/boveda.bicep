// Bóveda de secretos y certificados.
//
// Acceso exclusivo por identidad administrada, con RBAC en lugar de políticas
// de acceso: las políticas de acceso no se pueden auditar por rol ni heredar
// del grupo de recursos, y el estándar corporativo de MINSUR exige lo segundo.

param nombreBase string
param ubicacion string
param idTenant string
param idPrincipalIdentidad string
param idSubredPrivada string
param idRedVirtual string
param crearZonaDns bool
param etiquetas object

@description('Protección contra purga. Irreversible una vez activada.')
param protegerContraPurga bool = true

resource boveda 'Microsoft.KeyVault/vaults@2023-07-01' = {
  // El nombre de la bóveda admite hasta 24 caracteres.
  name: take('${nombreBase}-kv', 24)
  location: ubicacion
  tags: etiquetas
  properties: {
    tenantId: idTenant
    sku: {
      family: 'A'
      name: 'standard'
    }
    // RBAC en lugar de políticas de acceso.
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: protegerContraPurga ? true : null
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

// Key Vault Secrets User: leer secretos, no administrarlos. El backend no
// necesita crear ni rotar; eso corresponde a la operación.
var rolLectorSecretos = '4633458b-17de-408a-b874-0445c86b69e6'

resource acceso 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: boveda
  name: guid(boveda.id, idPrincipalIdentidad, rolLectorSecretos)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', rolLectorSecretos)
    principalId: idPrincipalIdentidad
    principalType: 'ServicePrincipal'
  }
}

module punto 'punto-privado.bicep' = if (!empty(idSubredPrivada)) {
  name: 'punto-boveda'
  params: {
    nombre: '${nombreBase}-pe-kv'
    ubicacion: ubicacion
    idRecurso: boveda.id
    grupoSubrecurso: 'vault'
    nombreZonaDns: 'privatelink.vaultcore.azure.net'
    idSubredPrivada: idSubredPrivada
    idRedVirtual: idRedVirtual
    crearZonaDns: crearZonaDns
    etiquetas: etiquetas
  }
}

output nombre string = boveda.name
output id string = boveda.id
output uri string = boveda.properties.vaultUri
