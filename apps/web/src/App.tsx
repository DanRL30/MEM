// Armazon de la interfaz. Monta la vista de modelamiento de escenario, que es
// la primera de PT3; el tablero, el historial y el comparador entran detras,
// con el enrutador, cuando existan.
//
// Se mantiene separado del punto de entrada para que las pruebas puedan
// renderizarlo sin tocar el DOM del documento.

import { ModelamientoDeEscenario } from "./vistas/ModelamientoDeEscenario";

export default function App() {
  return <ModelamientoDeEscenario />;
}
