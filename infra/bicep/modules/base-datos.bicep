// Azure SQL: persistencia transaccional de casos, corridas y parámetros.
//
// Autenticación exclusiva por Entra ID. `azureADOnlyAuthentication` en true
// elimina el usuario administrador con contraseña, y con él la necesidad de
// custodiar ese secreto. Un servicio que no tiene contraseña no puede filtrarla.
//
// El administrador es un GRUPO de Entra ID, no una persona: si quien administra
// cambia de rol, no hay que redesplegar la base.

param nombreBase string
param ubicacion string
param sku string
param idTenant string
param objetoAdmin string
param nombreAdmin string
param idSubredPrivada string
param idRedVirtual string
param crearZonaDns bool
param diasRetencionCopias int
param etiquetas object

resource servidor 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: '${nombreBase}-sql'
  location: ubicacion
  tags: etiquetas
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    version: '12.0'
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Disabled'
    restrictOutboundNetworkAccess: 'Enabled'
    administrators: {
      administratorType: 'ActiveDirectory'
      principalType: 'Group'
      login: nombreAdmin
      sid: objetoAdmin
      tenantId: idTenant
      azureADOnlyAuthentication: true
    }
  }
}

resource baseDatos 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: servidor
  name: 'evaluacion-economica'
  location: ubicacion
  tags: etiquetas
  sku: {
    name: sku
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    // Zona redundante solo donde el SKU y la región lo permiten.
    zoneRedundant: false
    // Pausa automática en entornos que no son productivos: siete usuarios
    // concurrentes no justifican cómputo encendido de noche.
    autoPauseDelay: startsWith(sku, 'GP_S_') ? 60 : -1
    requestedBackupStorageRedundancy: 'Zone'
  }
}

resource politicaCopias 'Microsoft.Sql/servers/databases/backupShortTermRetentionPolicies@2023-08-01-preview' = {
  parent: baseDatos
  name: 'default'
  properties: {
    retentionDays: diasRetencionCopias
    diffBackupIntervalInHours: 12
  }
}

// Retención de largo plazo: la retención mínima del alcance es de cinco años.
resource politicaLargoPlazo 'Microsoft.Sql/servers/databases/backupLongTermRetentionPolicies@2023-08-01-preview' = {
  parent: baseDatos
  name: 'default'
  properties: {
    weeklyRetention: 'P4W'
    monthlyRetention: 'P12M'
    yearlyRetention: 'P5Y'
    weekOfYear: 1
  }
}

resource auditoria 'Microsoft.Sql/servers/auditingSettings@2023-08-01-preview' = {
  parent: servidor
  name: 'default'
  properties: {
    state: 'Enabled'
    isAzureMonitorTargetEnabled: true
  }
}

module punto 'punto-privado.bicep' = if (!empty(idSubredPrivada)) {
  name: 'punto-sql'
  params: {
    nombre: '${nombreBase}-pe-sql'
    ubicacion: ubicacion
    idRecurso: servidor.id
    grupoSubrecurso: 'sqlServer'
    nombreZonaDns: 'privatelink${environment().suffixes.sqlServerHostname}'
    idSubredPrivada: idSubredPrivada
    idRedVirtual: idRedVirtual
    crearZonaDns: crearZonaDns
    etiquetas: etiquetas
  }
}

output nombreServidor string = servidor.name
output fqdnServidor string = servidor.properties.fullyQualifiedDomainName
output nombreBaseDatos string = baseDatos.name
