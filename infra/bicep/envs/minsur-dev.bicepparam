// Entorno de desarrollo · tenant de MINSUR
//
// Primer despliegue en el entorno del cliente (H10, 09/09/2026). Valida
// conectividad, identidad y estándares corporativos.
//
// Si R-12 resulta restrictiva —si MINSUR prohíbe tratar información financiera
// fuera de su tenant—, este entorno debe adelantarse del 14/09 al 31/08 y pasa
// a ser el único lugar donde se ejecuta el contraste con datos reales.

using '../main.bicep'

param entorno = 'minsur-dev'
param prefijoNombre = 'invaminsur'
param ubicacion = 'eastus2'

// A confirmar con TI: si MINSUR integra a su red existente, esto pasa a false
// y se completan idSubredIntegracion e idSubredPrivada (R-22).
param crearRedVirtual = true
param espacioDirecciones = '10.60.0.0/22'
param patronPublicacion = 'frontDoor'

param skuFunciones = 'EP1'
param skuApim = 'Developer'
param skuSwa = 'Standard'
param redundanciaAlmacenamiento = 'Standard_LRS'
param skuBaseDatos = 'GP_S_Gen5_1'

param habilitarInmutabilidad = false
param diasRetencion = 1825
param diasRetencionLogs = 30

param objetoAdminSql = '00000000-0000-0000-0000-000000000000' // grupo de Entra ID, lo entrega TI
param nombreAdminSql = 'MINSUR-Plataforma-DBA'
param correoAlertas = 'daniel.robles@invaglobal.com'

param etiquetasAdicionales = {
  Titularidad: 'MINSUR'
  Responsable: 'Fernando Parodi'
}
