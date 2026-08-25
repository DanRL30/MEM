import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import App from "../src/App";

// Sin los globales de vitest, la limpieza automatica de testing-library no se
// registra y el segundo render acumularia un armazon sobre el anterior.
afterEach(cleanup);

describe("Armazon de la interfaz", () => {
  it("identifica el servicio en el encabezado", () => {
    render(<App />);

    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Plataforma de Evaluación Económica",
    );
  });

  it("expone la region principal donde se montan las vistas", () => {
    render(<App />);

    expect(screen.getByRole("main")).toBeDefined();
  });
});
