// La lista de escenarios abiertos, como tabla.
//
// Es la pantalla a la que se vuelve, de modo que lo que se pregunta ante ella no
// es «cual es este» sino «cual toco yo el ultimo» y «quien movio este». Por eso
// lleva las dos parejas de fecha y autor: la creacion dice de donde viene el
// escenario y la modificacion, en que estado quedo.
//
// **Ocho columnas no caben en una pantalla estrecha**, y la tabla se desplaza en
// horizontal dentro de su panel en vez de estirar la pagina. La abreviatura se
// queda fija a la izquierda porque es lo que identifica la fila: con siete
// columnas a la derecha, una fecha suelta no dice de que escenario es.

import type { ResumenCaso } from "../api/cliente";

interface Props {
  casos: ResumenCaso[];
  alAbrir: (idCaso: string) => void;
}

const TIPOS: Record<string, string> = {
  "con-proyecto": "Con proyecto",
  "sin-proyecto": "Sin proyecto",
};

/**
 * Fecha y hora en el formato del cliente, `DD/MM/AAAA` y veinticuatro horas.
 *
 * Con la hora, y no solo el dia: dos corridas del mismo escenario en la misma
 * jornada son lo normal mientras se ajusta un caso, y sin ella la columna de
 * modificacion no ordena nada.
 */
function fecha(iso: string | undefined): string {
  const cuando = new Date(iso ?? "");
  if (Number.isNaN(cuando.getTime())) return "";
  return cuando.toLocaleString("es-PE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    // A veinticuatro horas: `es-PE` escribe `04:31 p. m.`, que ocupa casi el
    // doble que `16:31` y saca la columna de estado fuera de la tabla.
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
  });
}

/**
 * El correo sin su dominio: la columna es de personas, no de buzones.
 *
 * Tolera que el campo falte, aunque el contrato lo declare. Un caso guardado
 * por una version anterior de la API no lo trae, y una pantalla que se cae
 * entera por una celda vacia es peor que una celda vacia.
 */
function persona(correo: string | undefined): string {
  return correo ? (correo.split("@")[0] ?? correo) : "";
}

export function TablaDeEscenarios({ casos, alAbrir }: Props) {
  return (
    <div className="tabla-de-escenarios">
      <table>
        <thead>
          <tr>
            <th className="columna-abreviatura" scope="col">
              Abreviatura
            </th>
            <th scope="col">Nombre</th>
            <th scope="col">Tipo de caso</th>
            <th scope="col">Creado</th>
            <th scope="col">Creado por</th>
            <th scope="col">Modificado</th>
            <th scope="col">Modificado por</th>
            <th scope="col">Estado</th>
          </tr>
        </thead>
        <tbody>
          {casos.map((caso) => (
            <tr key={caso.id_caso}>
              <th className="columna-abreviatura" scope="row">
                <button
                  className="enlace"
                  onClick={() => {
                    alAbrir(caso.id_caso);
                  }}
                  title={caso.id_caso}
                  type="button"
                >
                  {caso.abreviatura || caso.nombre}
                </button>
              </th>
              <td>{caso.nombre}</td>
              <td>{TIPOS[caso.tipo] ?? caso.tipo}</td>
              <td className="columna-fecha">{fecha(caso.creado_en)}</td>
              <td>{persona(caso.creado_por)}</td>
              <td className="columna-fecha">{fecha(caso.actualizado_en)}</td>
              <td>{persona(caso.actualizado_por)}</td>
              <td>
                <span className={`pildora estado-${caso.estado}`}>{caso.estado}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
