// Entorno productivo · tenant de MINSUR
//
// Operación real por la Vicepresidencia de Proyectos de Expansión desde el
// 12/10/2026. Evaluaciones económicas reales, con clasificación financiera y
// confidencial.
//
// CONFIGURACIÓN DE COSTO MÍNIMO PRÁCTICO · ~US$ 316/mes
//
// Cada decisión de SKU está tomada al mínimo que conserva las garantías del
// alcance. La única excepción deliberada es el plan de cómputo: ver más abajo.
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

// Consumption escala a cero y factura por llamada, con el primer millón
// mensual sin costo. Conserva el acuerdo de nivel de servicio de 99,95 %, que
// cubre con holgura el compromiso de >99 % en horario laboral del alcance.
// Requiere que la carga de plantillas se resuelva con firma de acceso
// compartido directo al almacenamiento, sin atravesar la puerta.
param skuApim = 'Consumption'

// EXCEPCIÓN DELIBERADA AL MÍNIMO.
// Flex Consumption ahorraría ~US$ 59 al mes, pero no ofrece ranuras de
// despliegue. Sin ranuras, revertir el pase deja de ser un intercambio de
// segundos y pasa a ser un redespliegue de artefacto, dentro de una ventana de
// seis horas. Esa reversibilidad es la salvaguarda del hito de mayor riesgo del
// servicio y no se cambia por esa cifra.
// Para bajar al mínimo absoluto: cambiar a 'FC1'.
param skuFunciones = 'EP1'

// Serverless en lugar de capacidad aprovisionada: ~US$ 291 menos al mes.
// Sin pausa automática, para que no exista latencia de reanudación en el
// primer acceso del día.
param skuBaseDatos = 'GP_S_Gen5_2'
param minutosPausaSql = -1

// Standard en lugar de Premium: ~US$ 295 menos al mes. Cede el conjunto de
// reglas gestionado y el enlace privado al origen; a cambio se aplican reglas
// propias de limitación de tasa y bloqueo de métodos no utilizados.
// El contenido servido es estático y sin secretos: los datos viajan por la
// puerta de enlace con el token ya validado.
// PENDIENTE DE CONFIRMACIÓN DE TI · R-22
param skuBorde = 'Standard_AzureFrontDoor'

param skuSwa = 'Standard'
param redundanciaAlmacenamiento = 'Standard_GZRS'

param habilitarInmutabilidad = true
param diasRetencion = 1825
param diasRetencionLogs = 365
param topeDiarioLogsGb = 5
param muestreoApim = 25

param objetoAdminSql = '00000000-0000-0000-0000-000000000000'
param nombreAdminSql = 'MINSUR-Plataforma-DBA'
param correoAlertas = 'daniel.robles@invaglobal.com'

// Orígenes autorizados a cargar plantillas directamente al almacenamiento.
// Se completa con el dominio corporativo cuando TI lo entregue (R-48).
param origenesCarga = [
  'https://invaminsur-prod-swa.azurestaticapps.net'
]

param etiquetasAdicionales = {
  Titularidad: 'MINSUR'
  Responsable: 'Fernando Parodi'
  Criticidad: 'Media'
  VentanaMantenimiento: 'Domingo 00:00-06:00'
}
