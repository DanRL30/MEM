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
import { TablaAnual } from "../src/componentes/TablaAnual";
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

  it("no permite crear un escenario sin nombre", () => {
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

describe("La tabla anual", () => {
  const anios = [2027, 2028, 2029];

  it("pone el recalculo justo debajo de la fila que audita", () => {
    render(
      <TablaAnual
        anios={anios}
        series={[
          {
            concepto: "toneladas_finas",
            origen: "dato",
            recalculada: [0, 13, 13],
            unidad: "Mina Alfa",
            valores: [0, 13.5, 13.5],
          },
        ]}
      />,
    );
    const filas = screen.getAllByRole("row");
    // Cabecera, la fila cargada y su recalculo inmediatamente despues.
    expect(filas).toHaveLength(3);
    expect(filas[1]?.textContent).toContain("Mina Alfa");
    expect(filas[2]?.textContent).toContain("Esperado por el sistema");
  });

  it("avisa cuando el bloque no tiene ninguna linea con dato", () => {
    render(<TablaAnual anios={anios} series={[]} />);
    expect(screen.getByText(/no tiene ninguna línea con dato/)).toBeDefined();
  });
});

describe("Las pestanas", () => {
  const pestanas = [
    { clave: "produccion", titulo: "Producción", hoja: "InputsProd" },
    { clave: "ventas", titulo: "Ventas", hoja: "Ventas" },
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

  it("deja una sola parada de tabulacion en el grupo", () => {
    render(<Pestanas activa="produccion" alCambiar={() => undefined} pestanas={pestanas} />);
    const enfocables = screen
      .getAllByRole("tab")
      .filter((tab) => tab.getAttribute("tabindex") === "0");
    expect(enfocables).toHaveLength(1);
  });
});
