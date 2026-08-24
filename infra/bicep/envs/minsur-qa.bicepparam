// Entorno de calidad · tenant de MINSUR
//
// Homologación técnica y de seguridad, pruebas de rendimiento y UAT preliminar
// (H11, 18/09/2026). Es el entorno que se libera a Seguridad de la Información
// para el ethical hacking (PT6.11).
//
// CONFIGURACIÓN DE COSTO MÍNIMO · ~US$ 162/mes
//
// Regla que gobierna este archivo: calidad debe reflejar la configuración de
// producción en todo lo que el ethical hacking evalúa. Homologar sobre una
// configuración distinta de la productiva devalúa esa evaluación.
// Por eso el borde es Standard igual que producción, y por eso la inmutabilidad
// se activa: lo que se homologa es lo que se despliega.

using '../main.bicep'

param entorno = 'minsur-qa'
param prefijoNombre = 'invaminsur'
param ubicacion = 'eastus2'

param crearRedVirtual = true
param espacioDirecciones = '10.61.0.0/22'
param patronPublicacion = 'frontDoor'

param skuApim = 'Consumption'

// Flex sin instancias siempre listas: aquí el arranque en frío no tiene
// consecuencia contractual. Las pruebas de rendimiento contra el objetivo de
// nivel de servicio se ejecutan sobre producción, no sobre calidad.
param skuFunciones = 'FC1'

param skuBaseDatos = 'GP_S_Gen5_2'
param minutosPausaSql = 60

// Igual que producción, por la razón indicada arriba.
param skuBorde = 'Standard_AzureFrontDoor'

param skuSwa = 'Standard'
param redundanciaAlmacenamiento = 'Standard_ZRS'

param habilitarInmutabilidad = true
param diasRetencion = 1825
param diasRetencionLogs = 90
param topeDiarioLogsGb = 3
param muestreoApim = 50

param objetoAdminSql = '00000000-0000-0000-0000-000000000000'
param nombreAdminSql = 'MINSUR-Plataforma-DBA'
param correoAlertas = 'daniel.robles@invaglobal.com'

param origenesCarga = [
  'https://invaminsur-qa-swa.azurestaticapps.net'
]

param etiquetasAdicionales = {
  Titularidad: 'MINSUR'
  Responsable: 'Fernando Parodi'
  EthicalHacking: 'Alcance del 21-09 al 02-10'
}
