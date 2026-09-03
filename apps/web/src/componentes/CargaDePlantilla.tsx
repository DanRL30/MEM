// Carga de las plantillas del caso.
//
// Son cinco libros con dueños distintos y no se mezclan a propósito. El comité
// de precios lo aprueba y lo sube Finanzas, y lleva el nombre y la fecha de
// quien lo aprobó; los supuestos son del caso. Juntarlos en un solo archivo
// dejaría a cualquiera cambiando un precio aprobado sin que nadie lo advierta.
//
// Solo el libro del caso es obligatorio: sin los demás el caso se lee y se
// calcula igual, con los bloques que falten en cero. Es lo que permite empezar
// por producción y añadir el resto después.

import { useState } from "react";

import type { LibrosDelCaso } from "../api/cliente";

interface Props {
  cargando: boolean;
  alEnviar: (archivos: LibrosDelCaso) => void;
}

type Opcional = Exclude<keyof LibrosDelCaso, "caso">;

const OPCIONALES: { clave: Opcional; etiqueta: string }[] = [
  { clave: "opex", etiqueta: "Cash cost y gastos, una pestaña por unidad" },
  { clave: "capex", etiqueta: "Capital, una pestaña por unidad" },
  { clave: "supuestos", etiqueta: "Supuestos del caso" },
  { clave: "comite", etiqueta: "Comité de precios aprobado" },
];

export function CargaDePlantilla({ cargando, alEnviar }: Props) {
  const [caso, setCaso] = useState<File | null>(null);
  const [otros, setOtros] = useState<Partial<Record<Opcional, File>>>({});

  function enviar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!caso) return;
    alEnviar({ caso, ...otros });
  }

  return (
    <form onSubmit={enviar}>
      <label style={{ display: "block", marginBottom: "var(--espacio-4)" }}>
        <span>Libro del caso: hoja Caso, producción por unidad y precios</span>
        <input
          accept=".xlsx"
          onChange={(e) => {
            setCaso(e.target.files?.[0] ?? null);
          }}
          required
          type="file"
        />
      </label>

      {OPCIONALES.map(({ clave, etiqueta }) => (
        <label key={clave} style={{ display: "block", marginBottom: "var(--espacio-4)" }}>
          <span>{etiqueta} (opcional)</span>
          <input
            accept=".xlsx"
            onChange={(e) => {
              const archivo = e.target.files?.[0];
              setOtros((previos) =>
                archivo ? { ...previos, [clave]: archivo } : omitir(previos, clave),
              );
            }}
            type="file"
          />
        </label>
      ))}

      <button className="pildora" disabled={!caso || cargando} type="submit">
        {cargando ? "Leyendo y calculando…" : "Cargar y calcular"}
      </button>
    </form>
  );
}

function omitir(
  archivos: Partial<Record<Opcional, File>>,
  clave: Opcional,
): Partial<Record<Opcional, File>> {
  const resto = { ...archivos };
  delete resto[clave];
  return resto;
}
