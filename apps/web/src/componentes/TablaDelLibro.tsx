// Una hoja del libro, con su forma.
//
// Reproduce la disposición del modelo corporativo: el concepto en la primera
// columna, su unidad de medida en la segunda, y un ejercicio por columna a
// partir de la tercera. Las bandas de unidad productiva y de sección van a todo
// el ancho, como en la hoja, y entre un activo y el siguiente queda una fila de
// aire: en sesenta filas es lo que separa una mina de la siguiente sin obligar
// a leer el rótulo.
//
// **Las dos primeras columnas quedan fijas.** Es el `freeze_panes` de la propia
// plantilla: con treinta y seis ejercicios, una cifra del extremo derecho no
// diría de qué concepto es.
//
// **La última columna no lleva datos.** Absorbe el ancho que sobra cuando el
// horizonte es corto, para que ninguna columna real se estire: sin ella, la de
// unidad de medida crecía hasta igualar a las de año y la hoja desbordaba su
// contenedor.
//
// **La fila que cierra un bloque va sombreada**, como en el libro: es la que el
// ojo busca al recorrer la hoja, y sin ella todas las lineas pesan igual.
//
// **Las demas cifras van sobre blanco**, sin relleno de color. El vidrio se queda en
// el cromo: un fondo translúcido cambia el contraste de la cifra según lo que
// pase por debajo al desplazarse, y un contraste que depende del scroll no es
// un contraste.
//
// Donde la plataforma se aparta del libro, la fila lo dice en su `title` y no en
// una nota al pie: la hoja es para leer cifras, y un párrafo debajo de sesenta
// filas no lo lee nadie.

import { Fragment } from "react";

import type { GrupoDelBloque, SerieAnual } from "../api/cliente";

interface Props {
  anios: number[];
  grupos: GrupoDelBloque[];
  /**
   * Si se intercala, debajo de cada fila que el sistema rehace, lo que esperaba.
   *
   * Apagado en `InputsProd`: allí la hoja es para leer la cadena del proyecto y
   * duplicar cada fila calculada la alarga al doble. El contraste entre lo
   * cargado y lo recalculado tiene su propio sitio. El dato viaja igual en el
   * contrato, así que encenderlo es pasar la propiedad.
   */
  mostrarRecalculo?: boolean;
}

// Las escrituras que el libro alterna para lo mismo. `plantilla.py` las reconoce
// todas al leer, así que la pantalla también.
const TONELAJES = new Set(["t", "tt", "tmf"]);
const MONEDAS = new Set([
  "$",
  "$/t",
  "$/tt",
  "$/oz",
  "$/lb",
  "$/t conc",
  "$/tmf",
  "us$",
  "us$/t",
]);

// El motor guarda dolares porque la ingesta multiplica al leer: la hoja de opex
// del libro viene en miles. Al mostrarla se deshace esa conversion, para que la
// columna de unidad diga `$k` y la cifra sea la que el usuario tecleo.
const MILES = new Map([
  ["$k", 1000],
  ["k$", 1000],
  ["mus$", 1000],
  ["miles de us$", 1000],
  ["kt", 1000],
]);
const CON_DECIMALES = new Set(["oz/t", "g/t"]);

/**
 * Formatea como el libro.
 *
 * Un tonelaje va con separador de miles y sin decimales, y **un cero se muestra
 * como un guion**: es el formato `#,##0;-#,##0;-;-` de la hoja. Una ley va con
 * un decimal y su signo, y ahí el cero sí se escribe, `0.0%`, porque su formato
 * no declara sección de cero.
 *
 * El motor guarda las fracciones en tanto por uno y los importes en dólares. El
 * por ciento y los miles son de presentación: se convierten aquí y no en el
 * cálculo, deshaciendo lo que la ingesta hizo al leer la plantilla.
 */
function formatear(valor: number | undefined, medida: string): string {
  if (valor === undefined || !Number.isFinite(valor)) return "";
  const unidad = medida.trim().toLowerCase();

  if (unidad === "%") {
    return `${(valor * 100).toLocaleString("es-PE", {
      maximumFractionDigits: 1,
      minimumFractionDigits: 1,
    })}%`;
  }
  if (valor === 0) return "-";

  const escala = MILES.get(unidad);
  if (escala !== undefined) {
    return (valor / escala).toLocaleString("es-PE", { maximumFractionDigits: 0 });
  }
  if (CON_DECIMALES.has(unidad)) {
    return valor.toLocaleString("es-PE", {
      maximumFractionDigits: 3,
      minimumFractionDigits: 3,
    });
  }
  if (TONELAJES.has(unidad) || MONEDAS.has(unidad) || unidad === "dias") {
    return valor.toLocaleString("es-PE", { maximumFractionDigits: 0 });
  }
  return valor.toLocaleString("es-PE", { maximumFractionDigits: 2 });
}

/**
 * El acumulado del horizonte.
 *
 * Lo resuelve la API y aquí solo se pinta: no siempre es una suma. Una ley es el
 * promedio ponderado por el tonelaje de su fila, y esa relación —qué tonelaje
 * pondera a qué ley— vive en la estructura del libro, no en la pantalla.
 */
function totalDeLaFila(serie: SerieAnual): string {
  if (serie.acumulado === null || serie.acumulado === undefined) return "";
  return formatear(serie.acumulado, serie.medida);
}

export function TablaDelLibro({ anios, grupos, mostrarRecalculo = false }: Props) {
  const conFilas = grupos.filter((grupo) =>
    grupo.secciones.some((seccion) => seccion.series.length > 0),
  );
  if (conFilas.length === 0) {
    return <p>Este bloque no tiene ninguna línea con dato en el caso cargado.</p>;
  }

  // Las dos columnas fijas, los ejercicios, la del total y la sobrante.
  const columnas = anios.length + 4;

  return (
    <div className="hoja-del-libro">
      <table>
        <thead>
          <tr>
            <th className="columna-concepto" scope="col">
              Concepto
            </th>
            <th className="columna-medida" scope="col">
              Unidad
            </th>
            {anios.map((anio) => (
              <th key={anio} scope="col">
                {anio}
              </th>
            ))}
            <th className="columna-total" scope="col">
              Total
            </th>
            <th className="columna-sobrante" scope="col" />
          </tr>
        </thead>
        <tbody>
          {conFilas.map((grupo, orden) => (
            <Fragment key={grupo.titulo || "caso"}>
              {orden > 0 ? (
                <tr className="fila-espaciadora">
                  <td colSpan={columnas} />
                </tr>
              ) : null}

              {grupo.titulo ? (
                <tr className="banda-unidad">
                  <th className="banda-rotulo" colSpan={2} scope="colgroup">
                    {grupo.titulo}
                  </th>
                  <td colSpan={columnas - 2} />
                </tr>
              ) : null}

              {grupo.secciones
                .filter((seccion) => seccion.series.length > 0)
                .map((seccion) => (
                  <Fragment key={`${grupo.titulo}-${seccion.titulo ?? ""}`}>
                    {seccion.titulo ? (
                      <tr className="banda-seccion">
                        <th className="banda-rotulo" colSpan={2} scope="colgroup">
                          {seccion.titulo}
                        </th>
                        <td colSpan={columnas - 2} />
                      </tr>
                    ) : null}

                    {seccion.series.map((serie, indice) => (
                      <Fragment key={`${serie.etiqueta}-${String(indice)}`}>
                        <tr className={serie.total ? "fila-total" : undefined}>
                          <th className="columna-concepto" scope="row" title={serie.nota ?? ""}>
                            {serie.etiqueta}
                          </th>
                          <td className="columna-medida">{serie.medida}</td>
                          {anios.map((anio, columna) => (
                            <td key={anio}>{formatear(serie.valores[columna], serie.medida)}</td>
                          ))}
                          <td className="columna-total">{totalDeLaFila(serie)}</td>
                          <td className="columna-sobrante" />
                        </tr>

                        {mostrarRecalculo && serie.recalculada ? (
                          <tr className="fila-recalculo">
                            <th className="columna-concepto" scope="row">
                              Esperado por el sistema
                            </th>
                            <td className="columna-medida">{serie.medida}</td>
                            {anios.map((anio, columna) => (
                              <td key={anio}>
                                {formatear(serie.recalculada?.[columna], serie.medida)}
                              </td>
                            ))}
                            <td className="columna-total" />
                            <td className="columna-sobrante" />
                          </tr>
                        ) : null}
                      </Fragment>
                    ))}
                  </Fragment>
                ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
