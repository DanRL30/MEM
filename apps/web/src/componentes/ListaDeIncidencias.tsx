// Las incidencias de lectura de una plantilla.
//
// Llegan con su hoja y su celda separadas, no como una cadena ya compuesta, y
// por eso la lista puede llevar al usuario al sitio exacto en lugar de decirle
// que "hubo un problema".
//
// Se muestran todas. La ingesta acumula y no se detiene en la primera porque
// una plantilla llenada a mano llega con varias a la vez, y devolverlas de una
// en una obliga a corregir y reenviar tantas veces como errores tenga.

import type { IncidenciaDePlantilla } from "../api/cliente";

interface Props {
  incidencias: IncidenciaDePlantilla[];
}

export function ListaDeIncidencias({ incidencias }: Props) {
  if (incidencias.length === 0) return null;

  return (
    <div
      role="alert"
      style={{
        border: "1px solid var(--estado-alerta)",
        borderRadius: "var(--radio-control)",
        marginTop: "var(--espacio-4)",
        padding: "var(--espacio-3)",
      }}
    >
      <h3 style={{ fontSize: "var(--texto-cuerpo)", margin: "0 0 var(--espacio-2)" }}>
        {incidencias.length === 1
          ? "1 incidencia de lectura"
          : `${String(incidencias.length)} incidencias de lectura`}
      </h3>
      <ul style={{ margin: 0, paddingLeft: "var(--espacio-5)" }}>
        {incidencias.map((incidencia, indice) => (
          <li key={`${incidencia.hoja}-${incidencia.celda}-${String(indice)}`}>
            <code>
              {incidencia.hoja}!{incidencia.celda}
            </code>{" "}
            {incidencia.mensaje}
          </li>
        ))}
      </ul>
    </div>
  );
}
