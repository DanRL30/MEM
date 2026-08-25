// Armazon de la interfaz. El encabezado identifica el servicio y <main> es el
// punto donde el enrutador monta las vistas de PT3: casos, tablero, historial y
// comparador. Se mantiene separado del punto de entrada para que las pruebas
// puedan renderizarlo sin tocar el DOM del documento.

export default function App() {
  return (
    <>
      <header>
        <h1>Plataforma de Evaluación Económica</h1>
      </header>
      <main aria-label="Contenido principal" />
    </>
  );
}
