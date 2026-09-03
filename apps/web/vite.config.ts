import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// La interfaz se publica en Azure Static Web Apps y consume la API a través de
// Azure API Management. En desarrollo, el proxy apunta al backend local.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@minsur/contracts": fileURLToPath(new URL("../../packages/contracts/src/index.ts", import.meta.url)),
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_ORIGIN ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
  test: {
    // Los componentes se prueban contra un DOM real, no contra cadenas: una
    // asercion sobre marcado renderizado a texto no distingue un encabezado de
    // un parrafo que se le parece.
    environment: "jsdom",
    include: ["tests/**/*.test.{ts,tsx}"],
    setupFiles: ["./tests/entorno.ts"],
  },
});
