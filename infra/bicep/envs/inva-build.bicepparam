// Entorno de construcción · suscripción de INVA
//
// Del 24 de agosto al 2 de octubre. Se desactiva al cierre del servicio.
// Datos sintéticos y, si Finanzas lo autoriza, el caso de referencia
// anonimizado. Nunca evaluaciones reales.
//
// Es también el entorno espejo del patrón de MINSUR (PT6.2): replica SWA,
// API Management, Azure SQL, puntos de conexión privados y Key Vault, para que
// el equipo no descubra incompatibilidades el día que TI habilite el tenant.
//
// Lo paga INVA, no MINSUR. Aun así se configura al mínimo.

using '../main.bicep'

param entorno = 'inva-build'
param prefijoNombre = 'invaeval'
param ubicacion = 'eastus2'

param crearRedVirtual = true
param espacioDirecciones = '10.90.0.0/22'
param patronPublicacion = 'ninguno'

param skuApim = 'Consumption'
param skuFunciones = 'FC1'
param skuBaseDatos = 'GP_S_Gen5_1'
param minutosPausaSql = 60
param skuBorde = 'Standard_AzureFrontDoor'
param skuSwa = 'Free'
param redundanciaAlmacenamiento = 'Standard_LRS'

// Sin datos reales, la inmutabilidad estorbaría a la limpieza del entorno.
param habilitarInmutabilidad = false
param diasRetencion = 1825
param diasRetencionLogs = 30
param topeDiarioLogsGb = 1
param muestreoApim = 100

param objetoAdminSql = '00000000-0000-0000-0000-000000000000' // grupo de INVA
param nombreAdminSql = 'INVA-Plataforma-DBA'
param correoAlertas = 'daniel.robles@invaglobal.com'

param origenesCarga = [
  'http://localhost:5173'
]

param etiquetasAdicionales = {
  Titularidad: 'INVA'
  Temporal: 'Hasta 2026-10-02'
}
