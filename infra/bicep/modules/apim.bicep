// API Management: la única puerta al backend.
//
// Fernando Parodi la definió como parte del estándar de arquitectura de MINSUR
// en la reunión de arranque: frontend como Static Web App, backend detrás de
// API Management. La interfaz nunca llama a las funciones de forma directa.
//
// Advertencia de cronograma: el SKU Developer tarda entre 30 y 45 minutos en
// aprovisionarse, y los cambios de red otro tanto. Eso está contemplado en
// PT6.7, pero conviene no descubrirlo durante la ventana de pase.

param nombreBase string
param ubicacion string
param sku string
param correoPublicador string
param idTenant string
param urlBackend string
param idAppInsights string
@secure()
param claveAppInsights string
param etiquetas object

@description('Unidades de capacidad. Consumption escala a cero y no las usa.')
param capacidad int = 1

@description('Porcentaje de muestreo de trazas. Reducirlo baja la ingesta de registros.')
param muestreo int = 25

// Consumption escala a cero y factura por llamada, con el primer millon
// mensual sin costo. Conserva el acuerdo de nivel de servicio de 99,95 % que
// necesita el alcance. Lo que cede es la integracion con red virtual y el
// tamano del cuerpo que las politicas pueden almacenar: por eso la carga de
// plantillas se resuelve con firma de acceso compartido directo al
// almacenamiento, sin atravesar la puerta.
var esConsumption = sku == 'Consumption'

resource apim 'Microsoft.ApiManagement/service@2023-05-01-preview' = {
  name: '${nombreBase}-apim'
  location: ubicacion
  tags: etiquetas
  sku: {
    name: sku
    capacity: esConsumption ? 0 : capacidad
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: correoPublicador
    publisherName: 'INVA · Servicio INVA-01-2026-182'
    // Consumption no expone customProperties: ya impone TLS 1.2 como mínimo.
    customProperties: esConsumption ? null : {
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls10': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls11': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls10': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls11': 'False'
    }
  }
}

resource registrador 'Microsoft.ApiManagement/service/loggers@2023-05-01-preview' = {
  parent: apim
  name: 'appinsights'
  properties: {
    loggerType: 'applicationInsights'
    resourceId: idAppInsights
    credentials: {
      instrumentationKey: claveAppInsights
    }
  }
}

resource diagnostico 'Microsoft.ApiManagement/service/diagnostics@2023-05-01-preview' = {
  parent: apim
  name: 'applicationinsights'
  properties: {
    loggerId: registrador.id
    alwaysLog: 'allErrors'
    sampling: {
      samplingType: 'fixed'
      percentage: muestreo
    }
    httpCorrelationProtocol: 'W3C'
  }
}

resource backend 'Microsoft.ApiManagement/service/backends@2023-05-01-preview' = {
  parent: apim
  name: 'funciones'
  properties: {
    protocol: 'http'
    url: urlBackend
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}

// Política global. Valida el token de Entra ID en la puerta, de modo que una
// solicitud sin identidad válida nunca alcance el backend.
//
// Los literales multilínea de Bicep no interpolan, así que el tenant se
// sustituye con replace() en lugar de con ${...}.
var plantillaPolitica = '''
<policies>
  <inbound>
    <validate-azure-ad-token tenant-id="TENANT_ID" failed-validation-httpcode="401"
                             failed-validation-error-message="Token no valido para el tenant corporativo." />
    <rate-limit-by-key calls="120" renewal-period="60"
                       counter-key="@(context.Request.Headers.GetValueOrDefault(&quot;Authorization&quot;,&quot;anonimo&quot;))" />
    <set-header name="X-Servicio" exists-action="override">
      <value>INVA-01-2026-182</value>
    </set-header>
  </inbound>
  <backend>
    <forward-request timeout="300" />
  </backend>
  <outbound>
    <set-header name="X-Powered-By" exists-action="delete" />
    <set-header name="Server" exists-action="delete" />
  </outbound>
  <on-error>
    <base />
  </on-error>
</policies>
'''

resource politicaGlobal 'Microsoft.ApiManagement/service/policies@2023-05-01-preview' = {
  parent: apim
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: replace(plantillaPolitica, 'TENANT_ID', idTenant)
  }
}

output nombre string = apim.name
output id string = apim.id
output urlPuerta string = apim.properties.gatewayUrl
output idPrincipal string = apim.identity.principalId
