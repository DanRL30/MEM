// Log Analytics, Application Insights y alertas sobre el nivel de servicio.
//
// Las alertas no son decorativas: el alcance compromete apertura del tablero
// por debajo de 5 segundos y disponibilidad superior al 99 % en horario
// laboral. Sin instrumentación, ese compromiso no es verificable y la
// discusión al cierre del servicio se vuelve una opinión contra otra.

param nombreBase string
param ubicacion string
param diasRetencion int

@description('Tope diario de ingesta en GB. La ingesta se detiene al alcanzarlo, no se factura de mas.')
param topeDiarioGb int = 2

param correoAlertas string
param etiquetas object

@description('Objetivo de apertura del tablero, en milisegundos.')
param umbralTableroMs int = 5000

resource areaTrabajo 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${nombreBase}-log'
  location: ubicacion
  tags: etiquetas
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: diasRetencion
    // Con siete usuarios concurrentes la ingesta real es de pocos GB al mes.
    // El tope es una salvaguarda contra un bucle de registro, no una
    // restriccion operativa.
    workspaceCapping: {
      dailyQuotaGb: topeDiarioGb
    }
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${nombreBase}-appi'
  location: ubicacion
  tags: etiquetas
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: areaTrabajo.id
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource grupoAccion 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${nombreBase}-ag'
  location: 'global'
  tags: etiquetas
  properties: {
    groupShortName: 'evalmin'
    enabled: true
    emailReceivers: [
      {
        name: 'operacion'
        emailAddress: correoAlertas
        useCommonAlertSchema: true
      }
    ]
  }
}

resource alertaLatencia 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${nombreBase}-alerta-latencia'
  location: 'global'
  tags: etiquetas
  properties: {
    description: 'Tiempo de respuesta del servidor sobre el objetivo de nivel de servicio.'
    severity: 2
    enabled: true
    scopes: [appInsights.id]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'latencia'
          metricNamespace: 'microsoft.insights/components'
          metricName: 'requests/duration'
          operator: 'GreaterThan'
          threshold: umbralTableroMs
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: grupoAccion.id
      }
    ]
  }
}

resource alertaFallos 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${nombreBase}-alerta-fallos'
  location: 'global'
  tags: etiquetas
  properties: {
    description: 'Solicitudes fallidas por encima del umbral de disponibilidad comprometido.'
    severity: 1
    enabled: true
    scopes: [appInsights.id]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'fallos'
          metricNamespace: 'microsoft.insights/components'
          metricName: 'requests/failed'
          operator: 'GreaterThan'
          threshold: 5
          timeAggregation: 'Count'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: grupoAccion.id
      }
    ]
  }
}

output idAreaTrabajo string = areaTrabajo.id
output idAppInsights string = appInsights.id
output cadenaConexion string = appInsights.properties.ConnectionString
output claveInstrumentacion string = appInsights.properties.InstrumentationKey
output idGrupoAccion string = grupoAccion.id
