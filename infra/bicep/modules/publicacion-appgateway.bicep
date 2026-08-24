// Publicación mediante Application Gateway v2 con cortafuegos de aplicación.
//
// El segundo de los dos patrones. Se usa cuando la política corporativa exige
// que la entrada quede dentro de la red virtual del cliente, en lugar de un
// servicio de borde global.
//
// Requiere una subred dedicada: Application Gateway no comparte subred con
// ningún otro recurso. Por eso red.bicep reserva la subred `puerta` aunque el
// patrón elegido sea Front Door — cambiar de patrón no debe obligar a
// redireccionar el espacio de direcciones ya en uso.

param nombreBase string
param ubicacion string
param hostnameOrigen string
param idSubredPuerta string
@allowed(['Prevention', 'Detection'])
param modoWaf string
param etiquetas object

@description('Unidades mínimas y máximas de escalado automático.')
param capacidadMinima int = 1
param capacidadMaxima int = 3

var nombrePuerta = '${nombreBase}-agw'

resource ipPublica 'Microsoft.Network/publicIPAddresses@2023-11-01' = {
  name: '${nombrePuerta}-pip'
  location: ubicacion
  tags: etiquetas
  sku: {
    name: 'Standard'
    tier: 'Regional'
  }
  zones: ['1', '2', '3']
  properties: {
    publicIPAllocationMethod: 'Static'
    dnsSettings: {
      domainNameLabel: toLower(replace(nombrePuerta, '-', ''))
    }
  }
}

resource politicaWaf 'Microsoft.Network/ApplicationGatewayWebApplicationFirewallPolicies@2023-11-01' = {
  name: '${nombrePuerta}-waf'
  location: ubicacion
  tags: etiquetas
  properties: {
    policySettings: {
      state: 'Enabled'
      mode: modoWaf
      requestBodyCheck: true
      maxRequestBodySizeInKb: 128
      // Las plantillas de Producción, CAPEX y OPEX pesan entre 1 y 10 MB según
      // el alcance. Sin este límite ampliado, la carga fallaría en la puerta.
      fileUploadLimitInMb: 16
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'OWASP'
          ruleSetVersion: '3.2'
        }
      ]
    }
  }
}

var idPuerta = resourceId('Microsoft.Network/applicationGateways', nombrePuerta)

resource puerta 'Microsoft.Network/applicationGateways@2023-11-01' = {
  name: nombrePuerta
  location: ubicacion
  tags: etiquetas
  zones: ['1', '2', '3']
  properties: {
    sku: {
      name: 'WAF_v2'
      tier: 'WAF_v2'
    }
    autoscaleConfiguration: {
      minCapacity: capacidadMinima
      maxCapacity: capacidadMaxima
    }
    gatewayIPConfigurations: [
      {
        name: 'configuracion-ip'
        properties: {
          subnet: {
            id: idSubredPuerta
          }
        }
      }
    ]
    frontendIPConfigurations: [
      {
        name: 'frontal-publico'
        properties: {
          publicIPAddress: {
            id: ipPublica.id
          }
        }
      }
    ]
    frontendPorts: [
      {
        name: 'puerto-https'
        properties: {
          port: 443
        }
      }
      {
        name: 'puerto-http'
        properties: {
          port: 80
        }
      }
    ]
    backendAddressPools: [
      {
        name: 'grupo-interfaz'
        properties: {
          backendAddresses: [
            {
              fqdn: hostnameOrigen
            }
          ]
        }
      }
    ]
    backendHttpSettingsCollection: [
      {
        name: 'https-interfaz'
        properties: {
          port: 443
          protocol: 'Https'
          cookieBasedAffinity: 'Disabled'
          pickHostNameFromBackendAddress: true
          requestTimeout: 300
          probe: {
            id: '${idPuerta}/probes/sonda-interfaz'
          }
        }
      }
    ]
    probes: [
      {
        name: 'sonda-interfaz'
        properties: {
          protocol: 'Https'
          path: '/'
          interval: 30
          timeout: 30
          unhealthyThreshold: 3
          pickHostNameFromBackendHttpSettings: true
          match: {
            statusCodes: ['200-399']
          }
        }
      }
    ]
    httpListeners: [
      {
        name: 'escucha-http'
        properties: {
          frontendIPConfiguration: {
            id: '${idPuerta}/frontendIPConfigurations/frontal-publico'
          }
          frontendPort: {
            id: '${idPuerta}/frontendPorts/puerto-http'
          }
          protocol: 'Http'
        }
      }
    ]
    // La redirección a HTTPS se define aquí; el escucha HTTPS se añade cuando
    // TI entregue el certificado del dominio corporativo (R-48). Declararlo
    // ahora sin certificado haría fallar el despliegue.
    redirectConfigurations: [
      {
        name: 'redirigir-a-https'
        properties: {
          redirectType: 'Permanent'
          includePath: true
          includeQueryString: true
          targetUrl: 'https://${hostnameOrigen}'
        }
      }
    ]
    requestRoutingRules: [
      {
        name: 'regla-http'
        properties: {
          ruleType: 'Basic'
          priority: 100
          httpListener: {
            id: '${idPuerta}/httpListeners/escucha-http'
          }
          redirectConfiguration: {
            id: '${idPuerta}/redirectConfigurations/redirigir-a-https'
          }
        }
      }
    ]
    firewallPolicy: {
      id: politicaWaf.id
    }
    enableHttp2: true
    sslPolicy: {
      policyType: 'Predefined'
      policyName: 'AppGwSslPolicy20220101S'
    }
  }
}

output hostname string = ipPublica.properties.dnsSettings.fqdn
output idPuerta string = puerta.id
output ipPublica string = ipPublica.properties.ipAddress
