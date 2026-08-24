// Punto de entrada de los tipos compartidos entre la API y la interfaz.
//
// `api.d.ts` se genera con `pnpm contracts` desde el esquema OpenAPI que produce
// FastAPI. No lo edites a mano: cualquier cambio se pierde en la siguiente
// generación. Si un tipo del frontend ya existe en el esquema Pydantic, regenera.

export type * from "./api";
