// Entorno de desarrollo · tenant de MINSUR
//
// Primer despliegue en el entorno del cliente (H10, 09/09/2026). Valida
// conectividad, identidad y estándares corporativos.
//
// CONFIGURACIÓN EFÍMERA · ~US$ 8/mes
//
// Este entorno no se mantiene encendido de forma permanente. Se crea con
// infra/pipelines/entorno-efimero.yml cuando hay un ciclo de cambio y se
// destruye al terminar. La infraestructura como código es idempotente y no hay
// dato persistente que perder: los insumos son sintéticos y se regeneran.
//
// Si R-12 resulta restrictiva —si MINSUR prohíbe tratar información financiera
// fuera de su tenant—, este entorno pasa a ser el único lugar donde se ejecuta
// el contraste con datos reales, debe adelantarse al 31/08 y deja de ser
// efímero.

using '../main.bicep'

param entorno = 'minsur-dev'
param prefijoNombre = 'invaminsur'
param ubicacion = 'eastus2'

param crearRedVirtual = true
param espacioDirecciones = '10.60.0.0/22'

// Sin borde. A este entorno solo acceden el equipo de INVA y los homologadores,
// no usuarios finales. El WAF se evalúa en calidad, que es donde corre el
// ethical hacking.
param patronPublicacion = 'ninguno'

param skuApim = 'Consumption'
param skuFunciones = 'FC1'

param skuBaseDatos = 'GP_S_Gen5_1'
param minutosPausaSql = 60

param skuBorde = 'Standard_AzureFrontDoor' // sin efecto: no hay borde
param skuSwa = 'Free'
param redundanciaAlmacenamiento = 'Standard_LRS'

param habilitarInmutabilidad = false
param diasRetencion = 1825
param diasRetencionLogs = 30
param topeDiarioLogsGb = 1
param muestreoApim = 100 // volumen mínimo; conviene ver todo durante el desarrollo

param objetoAdminSql = '00000000-0000-0000-0000-000000000000'
param nombreAdminSql = 'MINSUR-Plataforma-DBA'
param correoAlertas = 'daniel.robles@invaglobal.com'

param origenesCarga = [
  'https://invaminsur-dev-swa.azurestaticapps.net'
  'http://localhost:5173'
]

param etiquetasAdicionales = {
  Titularidad: 'MINSUR'
  Responsable: 'Fernando Parodi'
  Vigencia: 'Efimero · recreado bajo demanda'
}
