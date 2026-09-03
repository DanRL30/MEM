// Pestañas al estilo de las hojas de un libro de Excel.
//
// MINSUR pidió esta navegación el 25/08/2026 y el motivo es de aprendizaje, no
// de estética: cambiar de pestaña equivale a cambiar de hoja, y el orden es el
// del libro corporativo. Quien lleva años trabajando en ese archivo encuentra
// cada bloque donde espera encontrarlo.
//
// **Una sola fila, y solo el nombre de la hoja.** Una pestaña de Excel no lleva
// descripción, y con dos líneas la tira ocupaba tres filas y dejaba de leerse
// como lo que imita. La descripción viaja en el `title`, que es donde no estorba.
// Si las hojas no caben, la tira se desplaza en horizontal: envolver a una
// segunda fila rompe la metáfora y mueve las pestañas de sitio cada vez que
// cambia el ancho.
//
// El patrón sigue el de una lista de pestañas accesible: una sola parada de
// tabulación en el grupo y las flechas mueven entre pestañas, que es como se
// comporta el propio Excel.

import { useRef } from "react";

export interface Pestana {
  clave: string;
  /** Rótulo corto: el nombre de la hoja. Lo decide la API, no esta pantalla. */
  etiqueta: string;
  /** Qué contiene la hoja. Va en el `title`, no en el rótulo. */
  titulo: string;
}

interface Props {
  pestanas: Pestana[];
  activa: string;
  alCambiar: (clave: string) => void;
}

export function Pestanas({ pestanas, activa, alCambiar }: Props) {
  const contenedor = useRef<HTMLDivElement>(null);

  function alPulsarTecla(evento: React.KeyboardEvent<HTMLDivElement>) {
    const paso = evento.key === "ArrowRight" ? 1 : evento.key === "ArrowLeft" ? -1 : 0;
    if (paso === 0) return;
    evento.preventDefault();
    const indice = pestanas.findIndex((p) => p.clave === activa);
    const siguiente = pestanas[(indice + paso + pestanas.length) % pestanas.length];
    if (!siguiente) return;
    alCambiar(siguiente.clave);
    const boton = contenedor.current?.querySelector<HTMLButtonElement>(
      `#pestana-${siguiente.clave}`,
    );
    boton?.focus();
    // Sin esto, avanzar con las flechas hasta una hoja que quedó fuera del
    // ancho visible la enfoca sin traerla a la vista.
    boton?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }

  return (
    <div
      aria-label="Hojas del modelo"
      className="vidrio vidrio-tenue tira-de-pestanas"
      onKeyDown={alPulsarTecla}
      ref={contenedor}
      role="tablist"
    >
      {pestanas.map((pestana) => {
        const seleccionada = pestana.clave === activa;
        return (
          <button
            aria-controls={`panel-${pestana.clave}`}
            aria-selected={seleccionada}
            className={seleccionada ? "pestana pestana-activa" : "pestana"}
            id={`pestana-${pestana.clave}`}
            key={pestana.clave}
            onClick={() => {
              alCambiar(pestana.clave);
            }}
            role="tab"
            tabIndex={seleccionada ? 0 : -1}
            title={pestana.titulo}
            type="button"
          >
            {pestana.etiqueta}
          </button>
        );
      })}
    </div>
  );
}
