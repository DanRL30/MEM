// Entorno de calidad · tenant de MINSUR
//
// Homologación técnica y de seguridad, pruebas de rendimiento y UAT preliminar
// (H11, 18/09/2026). Es el entorno que se libera a Seguridad de la Información
// para el ethical hacking (PT6.11).
//
// Aquí sí hay casos de contraste reales, bajo control de Finanzas. Por eso la
// inmutabilidad se activa: el comportamiento que se homologa debe ser el mismo
// que el de producción, incluida la irreversibilidad del congelamiento.

using '../main.bicep'

param entorno = 'minsur-qa'
param prefijoNombre = 'invaminsur'
param ubicacion = 'eastus2'

param crearRedVirtual = true
param espacioDirecciones = '10.61.0.0/22'
param patronPublicacion = 'frontDoor'

param skuFunciones = 'EP1'
param skuApim = 'Developer'
param skuSwa = 'Standard'
param redundanciaAlmacenamiento = 'Standard_ZRS'
param skuBaseDatos = 'GP_S_Gen5_2'

param habilitarInmutabilidad = true
param diasRetencion = 1825
param diasRetencionLogs = 90

param objetoAdminSql = '00000000-0000-0000-0000-000000000000'
param nombreAdminSql = 'MINSUR-Plataforma-DBA'
param correoAlertas = 'daniel.robles@invaglobal.com'

param etiquetasAdicionales = {
  Titularidad: 'MINSUR'
  Responsable: 'Fernando Parodi'
  EthicalHacking: 'Alcance del 21-09 al 02-10'
}
