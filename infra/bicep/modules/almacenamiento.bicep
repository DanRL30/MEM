// Almacenamiento de evaluaciones, plantillas, evidencias e imágenes selladas.
//
// Aquí vive el requisito más exigente del alcance: el congelamiento de una
// evaluación debe ser irreversible por tecnología, no por un atributo editable.
// Ni un administrador de la plataforma ni uno de la suscripción pueden alterar
// una imagen sellada dentro del periodo de retención.
//
// Sin claves de cuenta: `allowSharedKeyAccess` en false obliga a que todo
// acceso sea por identidad de Entra ID. Es lo que hace verificable la promesa
// de que no hay credenciales embebidas en el código.

param nombre string
param ubicacion string
param redundancia string
param diasRetencion int
param habilitarInmutabilidad bool
param idPrincipalIdentidad string
param idSubredPrivada string
param idRedVirtual string
param crearZonaDns bool
param etiquetas object

@description('Bloquea la política de inmutabilidad. IRREVERSIBLE: una vez bloqueada no se puede reducir ni eliminar durante el periodo de retención. Se activa como paso deliberado del pase a producción, nunca en dev ni en calidad.')
param bloquearInmutabilidad bool = false

var contenedores = [
  { nombre: 'evaluaciones', inmutable: false }
  { nombre: 'plantillas', inmutable: false }
  { nombre: 'evidencias', inmutable: false }
  { nombre: 'selladas', inmutable: true } // imágenes selladas de corridas congeladas
  { nombre: 'contraste', inmutable: false } // casos certificados de fidelidad
]

resource cuenta 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: nombre
  location: ubicacion
  tags: etiquetas
  sku: {
    name: redundancia
  }
  kind: 'StorageV2'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    // Sin claves compartidas: solo Entra ID.
    allowSharedKeyAccess: false
    publicNetworkAccess: 'Disabled'
    defaultToOAuthAuthentication: true
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
    encryption: {
      requireInfrastructureEncryption: true
      services: {
        blob: { enabled: true, keyType: 'Account' }
        table: { enabled: true, keyType: 'Account' }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

resource servicioBlob 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: cuenta
  name: 'default'
  properties: {
    isVersioningEnabled: true
    changeFeed: {
      enabled: true
      retentionInDays: 730
    }
    deleteRetentionPolicy: {
      enabled: true
      days: 90
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 90
    }
    restorePolicy: {
      enabled: true
      days: 89
    }
  }
}

resource contenedor 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [
  for c in contenedores: {
    parent: servicioBlob
    name: c.nombre
    properties: {
      publicAccess: 'None'
      metadata: {
        servicio: 'INVA-01-2026-182'
      }
    }
  }
]

// Política de inmutabilidad basada en tiempo sobre el contenedor de imágenes
// selladas. Se crea desbloqueada: el bloqueo es irreversible y se ejecuta como
// paso explícito del pase (P4), no como efecto colateral de un despliegue.
resource inmutabilidad 'Microsoft.Storage/storageAccounts/blobServices/containers/immutabilityPolicies@2023-05-01' = if (habilitarInmutabilidad) {
  name: '${cuenta.name}/default/selladas/default'
  properties: {
    immutabilityPeriodSinceCreationInDays: diasRetencion
    // Permite anexar sin permitir modificar lo ya escrito: la bitácora de
    // auditoría es de solo escritura, no de solo lectura.
    allowProtectedAppendWrites: true
  }
  dependsOn: [contenedor]
}

// El ciclo de vida no borra: con inmutabilidad activa no podría, y la retención
// mínima de cinco años lo prohíbe. Solo mueve a niveles de menor costo.
resource cicloVida 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = {
  parent: cuenta
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'enfriar-evaluaciones-antiguas'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['evaluaciones/', 'evidencias/', 'selladas/']
            }
            actions: {
              baseBlob: {
                tierToCool: { daysAfterModificationGreaterThan: 180 }
                tierToArchive: { daysAfterModificationGreaterThan: 730 }
              }
              version: {
                tierToCool: { daysAfterCreationGreaterThan: 90 }
              }
            }
          }
        }
      ]
    }
  }
}

resource servicioTabla 'Microsoft.Storage/storageAccounts/tableServices@2023-05-01' = {
  parent: cuenta
  name: 'default'
}

// Índices de consulta del historial. El dato de detalle vive en blob.
resource tabla 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = [
  for t in ['corridas', 'casos', 'auditoria', 'comitesPrecios']: {
    parent: servicioTabla
    name: t
  }
]

// -----------------------------------------------------------------------------
// Accesos por identidad administrada
// -----------------------------------------------------------------------------

var rolBlobContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var rolTableContributor = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'

resource accesoBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: cuenta
  name: guid(cuenta.id, idPrincipalIdentidad, rolBlobContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', rolBlobContributor)
    principalId: idPrincipalIdentidad
    principalType: 'ServicePrincipal'
  }
}

resource accesoTabla 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: cuenta
  name: guid(cuenta.id, idPrincipalIdentidad, rolTableContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', rolTableContributor)
    principalId: idPrincipalIdentidad
    principalType: 'ServicePrincipal'
  }
}

// -----------------------------------------------------------------------------
// Puntos de conexión privados
// -----------------------------------------------------------------------------

module puntoBlob 'punto-privado.bicep' = if (!empty(idSubredPrivada)) {
  name: 'punto-blob'
  params: {
    nombre: '${nombre}-pe-blob'
    ubicacion: ubicacion
    idRecurso: cuenta.id
    grupoSubrecurso: 'blob'
    nombreZonaDns: 'privatelink.blob.${environment().suffixes.storage}'
    idSubredPrivada: idSubredPrivada
    idRedVirtual: idRedVirtual
    crearZonaDns: crearZonaDns
    etiquetas: etiquetas
  }
}

module puntoTabla 'punto-privado.bicep' = if (!empty(idSubredPrivada)) {
  name: 'punto-tabla'
  params: {
    nombre: '${nombre}-pe-table'
    ubicacion: ubicacion
    idRecurso: cuenta.id
    grupoSubrecurso: 'table'
    nombreZonaDns: 'privatelink.table.${environment().suffixes.storage}'
    idSubredPrivada: idSubredPrivada
    idRedVirtual: idRedVirtual
    crearZonaDns: crearZonaDns
    etiquetas: etiquetas
  }
}

output nombre string = cuenta.name
output id string = cuenta.id
output inmutabilidadBloqueada bool = bloquearInmutabilidad
