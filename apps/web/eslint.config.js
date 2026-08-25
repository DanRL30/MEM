// Configuracion plana de ESLint 9. `pnpm lint` la aplica sobre src/ con
// --max-warnings 0: en integracion continua una advertencia no revisada acaba
// siendo permanente, asi que aqui no hay diferencia entre aviso y error.

import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules"] },
  js.configs.recommended,
  tseslint.configs.recommended,
);
