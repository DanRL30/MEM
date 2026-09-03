import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./estilos/color.css";
import "./estilos/tipografia.css";
import "./estilos/superficie.css";

const raiz = document.getElementById("raiz");

if (!raiz) {
  throw new Error(
    "Falta el elemento con id 'raiz' en index.html. Sin el no hay donde montar la interfaz.",
  );
}

createRoot(raiz).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
