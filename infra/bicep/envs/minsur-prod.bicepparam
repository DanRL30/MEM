// Entorno productivo · tenant de MINSUR
//
// Operación real por la Vicepresidencia de Proyectos de Expansión desde el
// 12/10/2026. Evaluaciones económicas reales, con clasificación financiera y
// confidencial.
//
// Tres diferencias sustantivas con calidad, todas deliberadas:
//   - API Management con acuerdo de nivel de servicio (Developer no lo tiene)
//   - Almacenamiento con redundancia de zona y geográfica
//   - Ranura de despliegue, para que revertir el pase sea un intercambio
//
// El bloqueo de la política de inmutabilidad NO se hace desde aquí. Es
// irreversible y se ejecuta como paso explícito del pase (P4), con TI presente.

using '../main.bicep'

param entorno = 'minsur-prod'
param prefijoNombre = 'invaminsur'
param ubicacion = 'eastus2'

param crearRedVirtual = true
param espacioDirecciones = '10.62.0.0/22'
param patronPublicacion = 'frontDoor'

param skuFunciones = 'EP1'
// Developer no tiene acuerdo de nivel de servicio. El alcance compromete
// disponibilidad superior al 99 % en horario laboral: no es compatible.
param skuApim = 'StandardV2'
param skuSwa = 'Standard'
param redundanciaAlmacenamiento = 'Standard_GZRS'
param skuBaseDatos = 'GP_Gen5_2'

param habilitarInmutabilidad = true
param diasRetencion = 1825
param diasRetencionLogs = 365

param objetoAdminSql = '00000000-0000-0000-0000-000000000000'
param nombreAdminSql = 'MINSUR-Plataforma-DBA'
param correoAlertas = 'daniel.robles@invaglobal.com'

param etiquetasAdicionales = {
  Titularidad: 'MINSUR'
  Responsable: 'Fernando Parodi'
  Criticidad: 'Media'
  VentanaMantenimiento: 'Domingo 00:00-06:00'
}
