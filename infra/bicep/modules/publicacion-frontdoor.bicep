// Publicación mediante Azure Front Door con cortafuegos de aplicación.
//
// Uno de los dos patrones que admite la plantilla. MINSUR no ha confirmado
// cuál aplica (riesgo declarado en el plan de traspaso: política de red
// corporativa incompatible con el modelo de publicación propuesto).
//
// Cambiar de este módulo a publicacion-appgateway.bicep es un cambio de
// parámetro. La aplicación no se entera.

param nombreBase string
param hostnameOrigen string
param idSitioEstatico string
@allowed(['Prevention', 'Detection'])
param modoWaf string
param etiquetas object

@description('SKU del perfil. Standard no ofrece enlace privado al origen ni conjunto de reglas gestionado.')
@allowed(['Standard_AzureFrontDoor', 'Premium_AzureFrontDoor'])
param sku string = 'Standard_AzureFrontDoor'

var esPremium = sku == 'Premium_AzureFrontDoor'

@description('Region del origen para el enlace privado. Debe coincidir con la de Static Web Apps.')
param ubicacionOrigen string = 'eastus2'

resource perfil 'Microsoft.Cdn/profiles@2024-02-01' = {
  name: '${nombreBase}-afd'
  location: 'global'
  tags: etiquetas
  sku: {
    // Premium habilita el enlace privado hacia el origen y el conjunto de
    // reglas gestionado. Standard cubre el resto por una décima parte del
    // costo: el contenido servido es estático, sin datos ni secretos, y los
    // datos viajan por la puerta de enlace con el token ya validado.
    name: sku
  }
}

resource extremo 'Microsoft.Cdn/profiles/afdEndpoints@2024-02-01' = {
  parent: perfil
  name: '${nombreBase}-ep'
  location: 'global'
  tags: etiquetas
  properties: {
    enabledState: 'Enabled'
  }
}

resource grupoOrigen 'Microsoft.Cdn/profiles/originGroups@2024-02-01' = {
  parent: perfil
  name: 'interfaz'
  properties: {
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
      additionalLatencyInMilliseconds: 50
    }
    healthProbeSettings: {
      probePath: '/'
      probeRequestType: 'HEAD'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 60
    }
  }
}

resource origen 'Microsoft.Cdn/profiles/originGroups/origins@2024-02-01' = {
  parent: grupoOrigen
  name: 'swa'
  properties: {
    hostName: hostnameOrigen
    httpPort: 80
    httpsPort: 443
    originHostHeader: hostnameOrigen
    priority: 1
    weight: 1000
    enabledState: 'Enabled'
    enforceCertificateNameCheck: true
    // El enlace privado al origen solo existe en Premium.
    sharedPrivateLinkResource: esPremium ? {
      privateLink: {
        id: idSitioEstatico
      }
      groupId: 'staticSites'
      privateLinkLocation: ubicacionOrigen
      requestMessage: 'Front Door del servicio INVA-01-2026-182'
    } : null
  }
}

resource ruta 'Microsoft.Cdn/profiles/afdEndpoints/routes@2024-02-01' = {
  parent: extremo
  name: 'predeterminada'
  properties: {
    originGroup: {
      id: grupoOrigen.id
    }
    supportedProtocols: ['Https']
    patternsToMatch: ['/*']
    forwardingProtocol: 'HttpsOnly'
    linkToDefaultDomain: 'Enabled'
    httpsRedirect: 'Enabled'
  }
  dependsOn: [origen]
}

resource waf 'Microsoft.Network/FrontDoorWebApplicationFirewallPolicies@2024-02-01' = {
  name: replace('${nombreBase}waf', '-', '')
  location: 'global'
  tags: etiquetas
  sku: {
    name: sku
  }
  properties: {
    policySettings: {
      enabledState: 'Enabled'
      // Detección en entornos no productivos: bloquear durante la construcción
      // genera falsos positivos que el equipo no puede distinguir de defectos.
      mode: modoWaf
      requestBodyCheck: 'Enabled'
    }
    // El conjunto de reglas gestionado requiere Premium. En Standard se
    // sustituye por reglas propias sobre los vectores que aplican a una
    // aplicación de página única: limitación de tasa y bloqueo de métodos
    // que la interfaz no usa.
    managedRules: esPremium ? {
      managedRuleSets: [
        {
          ruleSetType: 'Microsoft_DefaultRuleSet'
          ruleSetVersion: '2.1'
          ruleSetAction: 'Block'
        }
        {
          ruleSetType: 'Microsoft_BotManagerRuleSet'
          ruleSetVersion: '1.0'
        }
      ]
    } : null
    customRules: esPremium ? null : {
      rules: [
        {
          name: 'limitarTasaPorOrigen'
          priority: 100
          enabledState: 'Enabled'
          ruleType: 'RateLimitRule'
          rateLimitDurationInMinutes: 1
          rateLimitThreshold: 600
          action: 'Block'
          matchConditions: [
            {
              matchVariable: 'RequestUri'
              operator: 'Any'
              matchValue: []
            }
          ]
        }
        {
          name: 'bloquearMetodosNoUsados'
          priority: 200
          enabledState: 'Enabled'
          ruleType: 'MatchRule'
          action: 'Block'
          matchConditions: [
            {
              matchVariable: 'RequestMethod'
              operator: 'Equal'
              negateCondition: false
              matchValue: ['PUT', 'DELETE', 'PATCH', 'TRACE']
            }
          ]
        }
      ]
    }
  }
}

resource politicaSeguridad 'Microsoft.Cdn/profiles/securityPolicies@2024-02-01' = {
  parent: perfil
  name: 'waf'
  properties: {
    parameters: {
      type: 'WebApplicationFirewall'
      wafPolicy: {
        id: waf.id
      }
      associations: [
        {
          domains: [
            {
              id: extremo.id
            }
          ]
          patternsToMatch: ['/*']
        }
      ]
    }
  }
}

output hostname string = extremo.properties.hostName
output idPerfil string = perfil.id
