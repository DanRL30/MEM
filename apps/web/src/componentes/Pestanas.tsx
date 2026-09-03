// Pestañas al estilo de las hojas de un libro de Excel.
//
// MINSUR pidió esta navegación el 25/08/2026 y el motivo es de aprendizaje, no
// de estética: cambiar de pestaña equivale a cambiar de hoja, y el orden es el
// del libro corporativo. Quien lleva años trabajando en ese archivo encuentra
// cada bloque donde espera encontrarlo.
//
// El patrón sigue el de una lista de pestañas accesible: una sola parada de
// tabulación en el grupo y las flechas mueven entre pestañas, que es como se
// comporta el propio Excel.

import { useRef } from "react";

export interface Pestana {
  clave: string;
  titulo: string;
  hoja?: string;
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
    contenedor.current?.querySelector<HTMLButtonElement>(`#pestana-${siguiente.clave}`)?.focus();
  }

  return (
    <div
      aria-label="Hojas del modelo"
      className="vidrio vidrio-tenue"
      onKeyDown={alPulsarTecla}
      ref={contenedor}
      role="tablist"
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "var(--espacio-1)",
        padding: "var(--espacio-2)",
      }}
    >
      {pestanas.map((pestana) => {
        const seleccionada = pestana.clave === activa;
        return (
          <button
            aria-controls={`panel-${pestana.clave}`}
            aria-selected={seleccionada}
            id={`pestana-${pestana.clave}`}
            key={pestana.clave}
            onClick={() => {
              alCambiar(pestana.clave);
            }}
            role="tab"
            tabIndex={seleccionada ? 0 : -1}
            title={pestana.titulo}
            type="button"
            style={{
              background: seleccionada ? "var(--texto-enfasis)" : "transparent",
              border: "1px solid",
              borderColor: seleccionada ? "var(--texto-enfasis)" : "transparent",
              borderRadius: "var(--radio-control)",
              color: seleccionada ? "var(--marca-blanco)" : "var(--texto-principal)",
              cursor: "pointer",
              font: "inherit",
              padding: "var(--espacio-2) var(--espacio-3)",
            }}
          >
            <span style={{ display: "block", fontWeight: "var(--peso-encabezado)" }}>
              {pestana.hoja ?? pestana.titulo}
            </span>
            {pestana.hoja ? (
              <span style={{ display: "block", fontSize: "var(--texto-etiqueta)" }}>
                {pestana.titulo}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
