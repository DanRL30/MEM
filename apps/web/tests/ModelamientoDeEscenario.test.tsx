// Pruebas de la vista de modelamiento y de las piezas que la componen.
//
// Van juntas en un archivo a proposito: el montaje del entorno jsdom domina el
// tiempo de la suite en Windows, y repartir cuatro casos en cuatro archivos lo
// paga cuatro veces sin ganar nada.
//
// Lo que se fija aqui son decisiones, no apariencia: que la ausencia de TIR se
// diga en vez de mostrarse como cero, que el recalculo aparezca debajo de la
// fila que audita, y que los dos modelos de calculo previstos se vean sin poder
// elegirse.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import App from "../src/App";
import { Pestanas } from "../src/componentes/Pestanas";
import { TablaDelLibro } from "../src/componentes/TablaDelLibro";
import type { SerieAnual } from "../src/api/cliente";
import { TarjetaIndicador } from "../src/componentes/TarjetaIndicador";

afterEach(cleanup);

describe("La vista de modelamiento", () => {
  it("arranca en la creacion del escenario", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "Nuevo escenario" })).toBeDefined();
    expect(screen.getByRole("button", { name: /Crear escenario/ })).toBeDefined();
  });

  it("muestra los modelos previstos sin permitir elegirlos", () => {
    // El cliente pidio que Marcobre y Energias Renovables estuvieran a la
    // vista. Ocultarlos perderia la senal de que estan previstos; habilitarlos
    // produciria un caso que no calcula.
    render(<App />);
    expect(screen.getByRole("radio", { name: /Minsur/ })).not.toHaveProperty("disabled", true);
    for (const nombre of [/Marcobre/, /Energías Renovables/]) {
      expect(screen.getByRole("radio", { name: nombre })).toHaveProperty("disabled", true);
    }
  });

  it("no pregunta el proyecto ni la fase FEL", () => {
    // Se llega a esta pantalla entrando a un proyecto, despues a uno de sus
    // FEL, y dentro estan sus escenarios: los dos son contexto de navegacion.
    // Volver a preguntarlos abriria la puerta a que la respuesta contradiga el
    // sitio desde el que se esta creando.
    render(<App />);
    expect(screen.queryByText(/Proyecto/)).toBeNull();
    expect(screen.queryByText(/Fase/)).toBeNull();
  });

  it("ofrece los dos lados de la comparacion y solo esos", () => {
    // Una evaluacion de inversion son dos corridas y el indicador que sustenta
    // la decision es la diferencia. Que el concentrado sea monometalico o
    // polimetalico se deduce de las unidades, no se teclea al abrir el caso.
    render(<App />);
    const tipos = screen
      .getAllByRole("radio")
      .filter((radio) => radio.getAttribute("name") === "tipo");
    expect(tipos.map((radio) => radio.getAttribute("value"))).toEqual([
      "con-proyecto",
      "sin-proyecto",
    ]);
  });

  it("pide la abreviatura antes que el nombre", () => {
    // El cliente ya trabaja con ese campo. Va delante porque es el rotulo
    // corto con el que el escenario se identifica en tablas y comparaciones.
    render(<App />);
    const campos = screen
      .getAllByRole("textbox")
      .map((campo) => campo.closest("label")?.textContent ?? "");
    expect(campos[0]).toContain("Abreviatura");
    expect(campos[1]).toContain("Nombre del escenario");
  });

  it("no permite crear un escenario sin nombre ni abreviatura", () => {
    render(<App />);
    expect(screen.getByRole("button", { name: /Crear escenario/ })).toHaveProperty(
      "disabled",
      true,
    );
  });
});

describe("La tarjeta de indicador", () => {
  it("declara que no hay TIR en vez de mostrar un cero", () => {
    // Un caso que abre en positivo no tiene una tasa que describa su
    // rentabilidad, y el libro escribe un guion. Un cero se leeria como un
    // resultado calculado. Lo decide el ADR 0011.
    render(
      <TarjetaIndicador
        motivoSiFalta="El caso no abre con desembolso"
        titulo="Tasa interna de retorno"
        unidad="%"
        valor={null}
      />,
    );
    expect(screen.getByText("El caso no abre con desembolso")).toBeDefined();
    expect(screen.queryByText("0,0")).toBeNull();
  });

  it("muestra el valor con la convencion numerica peruana", () => {
    // Punto decimal y coma de millares, que es lo que el usuario ve en su
    // propio Excel. La documentacion del servicio usa la convencion contraria
    // y esa diferencia es deliberada: un documento se lee, una cifra se
    // compara contra la celda de al lado.
    render(<TarjetaIndicador titulo="Valor actual neto" unidad="MM US$" valor={1284.5} />);
    expect(screen.getByText("1,284.5")).toBeDefined();
  });
});

describe("La hoja del libro", () => {
  const anios = [2027, 2028, 2029];

  const grupo = (series: SerieAnual[]) => [
    { titulo: "San Rafael", secciones: [{ titulo: "Mina", series }] },
  ];

  it("no intercala el recalculo salvo que se pida", () => {
    // En `InputsProd` la hoja es para leer la cadena del proyecto. Duplicar
    // cada fila calculada la alarga al doble; el contraste tiene otro sitio.
    render(
      <TablaDelLibro
        anios={anios}
        grupos={grupo([
          {
            etiqueta: "Toneladas finas",
            medida: "t",
            concepto: "toneladas_finas",
            origen: "dato",
            total: false,
            recalculada: [0, 13, 13],
            valores: [0, 13.5, 13.5],
          },
        ])}
      />,
    );
    expect(screen.queryByText("Esperado por el sistema")).toBeNull();
  });

  it("pone el recalculo justo debajo de la fila que audita cuando se pide", () => {
    render(
      <TablaDelLibro
        anios={anios}
        mostrarRecalculo
        grupos={grupo([
          {
            etiqueta: "Toneladas finas",
            medida: "t",
            concepto: "toneladas_finas",
            origen: "dato",
            total: false,
            recalculada: [0, 13, 13],
            valores: [0, 13.5, 13.5],
          },
        ])}
      />,
    );
    const filas = screen.getAllByRole("row");
    // Cabecera, banda de unidad, banda de seccion, la fila y su recalculo.
    expect(filas).toHaveLength(5);
    expect(filas[1]?.textContent).toContain("San Rafael");
    expect(filas[2]?.textContent).toContain("Mina");
    expect(filas[3]?.textContent).toContain("Toneladas finas");
    expect(filas[4]?.textContent).toContain("Esperado por el sistema");
  });

  it("muestra un cero con guion en un tonelaje y como 0.0% en una ley", () => {
    // Es el formato del libro: `#,##0;-#,##0;-;-` para los tonelajes, que
    // convierte el cero en guion, y `0.0%` para las leyes, que si lo escribe.
    render(
      <TablaDelLibro
        anios={anios}
        grupos={grupo([
          {
            etiqueta: "Mineral extraído",
            medida: "t",
            concepto: "mineral_extraido",
            origen: "dato",
            total: false,
            valores: [1404922, 0, 0],
          },
          {
            etiqueta: "Ley Sn",
            medida: "%",
            concepto: "ley_de_cabeza",
            origen: "dato",
            total: false,
            valores: [0.02, 0, 0],
          },
        ])}
      />,
    );
    const filas = screen.getAllByRole("row");
    const tonelaje = filas[3]?.textContent ?? "";
    const ley = filas[4]?.textContent ?? "";

    expect(tonelaje).toContain("1,404,922");
    expect(tonelaje).toContain("-");
    expect(ley).toContain("2.0%");
    expect(ley).toContain("0.0%");
  });

  it("muestra los miles como el libro, no como los guarda el motor", () => {
    // La ingesta multiplica por mil al leer la hoja de opex, que viene en `$k`.
    // La pantalla lo deshace: la columna dice `$k` y la cifra es la que el
    // usuario tecleo.
    render(
      <TablaDelLibro
        anios={anios}
        grupos={grupo([
          {
            acumulado: 90_000_000,
            etiqueta: "Mina",
            medida: "$k",
            concepto: "",
            origen: "dato",
            total: false,
            valores: [90_000_000, 0, 0],
          },
        ])}
      />,
    );
    // Sale dos veces: en su ejercicio y en la columna del acumulado, que la API
    // resuelve y la pantalla solo pinta.
    expect(screen.getAllByText("90,000")).toHaveLength(2);
  });

  it("lleva la unidad de medida en su propia columna", () => {
    render(
      <TablaDelLibro
        anios={anios}
        grupos={grupo([
          {
            etiqueta: "Ley Ag",
            medida: "oz/t",
            concepto: "ley_ag",
            origen: "dato",
            total: false,
            valores: [1.5, 1.5, 1.5],
          },
        ])}
      />,
    );
    expect(screen.getByRole("columnheader", { name: "Unidad" })).toBeDefined();
    expect(screen.getByText("oz/t")).toBeDefined();
  });

  it("sombrea la fila que cierra un bloque", () => {
    // Es la que el ojo busca al recorrer la hoja. Quien decide cual es la API,
    // no la pantalla: aqui solo se pinta lo que viene marcado.
    render(
      <TablaDelLibro
        anios={anios}
        grupos={grupo([
          {
            etiqueta: "Mina",
            medida: "$k",
            concepto: "",
            origen: "dato",
            total: false,
            valores: [1, 1, 1],
          },
          {
            etiqueta: "Total San Rafael",
            medida: "$k",
            concepto: "",
            origen: "calculada",
            total: true,
            valores: [1, 1, 1],
          },
        ])}
      />,
    );
    const filas = screen.getAllByRole("row");
    expect(filas[3]?.className).toBe("");
    expect(filas[4]?.className).toBe("fila-total");
  });

  it("avisa cuando el bloque no tiene ninguna linea con dato", () => {
    render(<TablaDelLibro anios={anios} grupos={[]} />);
    expect(screen.getByText(/no tiene ninguna línea con dato/)).toBeDefined();
  });
});

describe("Las pestanas", () => {
  const pestanas = [
    { clave: "produccion", etiqueta: "InputsProd", titulo: "Producción por unidad" },
    { clave: "ventas", etiqueta: "Ventas", titulo: "Los tres caminos de ingreso" },
  ];

  it("cambia de hoja con las flechas, como el propio Excel", () => {
    let activa = "produccion";
    render(
      <Pestanas
        activa={activa}
        alCambiar={(clave) => {
          activa = clave;
        }}
        pestanas={pestanas}
      />,
    );
    fireEvent.keyDown(screen.getByRole("tablist"), { key: "ArrowRight" });
    expect(activa).toBe("ventas");
  });

  it("rotula con el nombre de la hoja y deja la descripcion en el title", () => {
    // Una pestana de Excel no lleva descripcion. Con dos lineas la tira ocupaba
    // tres filas y dejaba de leerse como lo que imita.
    render(<Pestanas activa="produccion" alCambiar={() => undefined} pestanas={pestanas} />);
    const primera = screen.getAllByRole("tab")[0];
    expect(primera?.textContent).toBe("InputsProd");
    expect(primera?.getAttribute("title")).toBe("Producción por unidad");
  });

  it("deja una sola parada de tabulacion en el grupo", () => {
    render(<Pestanas activa="produccion" alCambiar={() => undefined} pestanas={pestanas} />);
    const enfocables = screen
      .getAllByRole("tab")
      .filter((tab) => tab.getAttribute("tabindex") === "0");
    expect(enfocables).toHaveLength(1);
  });
});
