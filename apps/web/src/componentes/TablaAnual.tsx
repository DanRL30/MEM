// La tabla de un bloque: conceptos en filas, ejercicios en columnas.
//
// Es la única superficie de la interfaz que **no** lleva vidrio. Una cifra a
// 14 px sobre fondo translúcido cambia de contraste según lo que pase por
// debajo al desplazarse, y un contraste que depende del scroll no es un
// contraste. El efecto se queda en el cromo.
//
// Dos reglas heredadas de la vista con la que se revisó el cálculo:
//
// El color señala el origen del dato, y nunca se colorea el texto: ni el
// celeste ni el naranja alcanzan 4,5 a 1 sobre blanco, así que van de relleno
// con la cifra en el color de texto de siempre.
//
// Justo debajo de una fila que el usuario carga y el sistema sabe rehacer va lo
// que el sistema esperaba. Sin ese valor al lado, una diferencia no dice qué se
// esperaba, y la alerta no sirve de nada.

import { Fragment } from "react";

import type { SerieAnual } from "../api/cliente";

interface Props {
  anios: number[];
  series: SerieAnual[];
}

function formatear(valor: number | undefined): string {
  if (valor === undefined || !Number.isFinite(valor)) return "";
  if (valor === 0) return "0";
  const magnitud = Math.abs(valor);
  const decimales = magnitud >= 1000 ? 0 : magnitud >= 1 ? 1 : 4;
  return valor.toLocaleString("es-PE", {
    maximumFractionDigits: decimales,
    minimumFractionDigits: decimales,
  });
}

function etiqueta(serie: SerieAnual): string {
  const concepto = serie.concepto.replace(/_/g, " ");
  return serie.unidad ? `${serie.unidad} · ${concepto}` : concepto;
}

export function TablaAnual({ anios, series }: Props) {
  if (series.length === 0) {
    return <p>Este bloque no tiene ninguna línea con dato en el caso cargado.</p>;
  }

  return (
    <div className="tabla-solida" style={{ maxHeight: "60vh" }}>
      <table>
        <thead>
          <tr>
            <th scope="col">Concepto</th>
            {anios.map((anio) => (
              <th key={anio} scope="col" style={{ textAlign: "right" }}>
                {anio}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {series.map((serie, indice) => {
            const clave = `${serie.unidad ?? ""}-${serie.concepto}-${String(indice)}`;
            const relleno =
              serie.recalculada !== null && serie.recalculada !== undefined
                ? "origen-recalculada"
                : serie.origen === "dato"
                  ? "origen-dato"
                  : undefined;
            return (
              <Fragment key={clave}>
                <tr>
                  <th className={relleno} scope="row">
                    {etiqueta(serie)}
                  </th>
                  {anios.map((anio, columna) => (
                    <td className={relleno} key={anio}>
                      {formatear(serie.valores[columna])}
                    </td>
                  ))}
                </tr>
                {serie.recalculada ? (
                  <tr className="fila-recalculo">
                    <th scope="row">Esperado por el sistema</th>
                    {anios.map((anio, columna) => (
                      <td key={anio}>{formatear(serie.recalculada?.[columna])}</td>
                    ))}
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
