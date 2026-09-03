// Cliente HTTP de la plataforma.
//
// Los tipos no se escriben aquí: salen de `@minsur/contracts`, que se genera
// con `pnpm contracts` desde el esquema OpenAPI que emite FastAPI. Un tipo
// escrito a mano que duplique uno del esquema es una divergencia esperando
// ocurrir, y se nota tarde: cuando la API cambia y la pantalla sigue
// compilando.
//
// En desarrollo, Vite redirige `/api` a `http://localhost:8000`.

import type { components } from "@minsur/contracts";

type Esquemas = components["schemas"];

export type ResumenCaso = Esquemas["ResumenCaso"];
export type DetalleCaso = Esquemas["DetalleCaso"];
export type NuevoCaso = Esquemas["NuevoCaso"];
export type ResultadoEvaluacion = Esquemas["ResultadoEvaluacion"];
export type ResultadoValidacion = Esquemas["ResultadoValidacion"];
export type IncidenciaDePlantilla = Esquemas["IncidenciaDePlantilla"];
export type BloquesDeCorrida = Esquemas["BloquesDeCorrida"];
export type BloqueDeCorrida = Esquemas["BloqueDeCorrida"];
export type SerieAnual = Esquemas["SerieAnual"];
export type GrupoDelBloque = Esquemas["GrupoDelBloque"];
export type SeccionDelBloque = Esquemas["SeccionDelBloque"];
export type Tablero = Esquemas["Tablero"];
export type Indicadores = Esquemas["Indicadores"];

const BASE = "/api";

// Identidad de conveniencia del entorno local. No es un secreto ni una
// credencial: fuera de local la API rechaza cualquier solicitud autenticada
// hasta que exista el registro de aplicación en Entra ID (`R-26`), y entonces
// este encabezado lo emite MSAL con el token real del usuario.
const CABECERA_LOCAL = "Bearer desarrollo-local";

export class ErrorDeApi extends Error {
  constructor(
    readonly estado: number,
    readonly detalle: string,
    readonly restriccion: string | null,
  ) {
    super(detalle);
    this.name = "ErrorDeApi";
  }
}

function autorizacion(): HeadersInit {
  return { Authorization: CABECERA_LOCAL };
}

async function fallo(respuesta: Response): Promise<ErrorDeApi> {
  // Un 501 de esta API no es una laguna: señala una operación bloqueada por un
  // insumo del cliente que aún no llega, y el cuerpo trae la restricción `R-xx`
  // responsable. La pantalla la muestra en lugar de un error genérico.
  let detalle = `La API respondió ${String(respuesta.status)}.`;
  let restriccion: string | null = null;
  try {
    const cuerpo: unknown = await respuesta.json();
    const problema = (cuerpo as { detail?: unknown }).detail ?? cuerpo;
    if (problema && typeof problema === "object") {
      const p = problema as { detalle?: unknown; restriccion?: unknown };
      if (typeof p.detalle === "string") detalle = p.detalle;
      if (typeof p.restriccion === "string") restriccion = p.restriccion;
    }
  } catch {
    // Un cuerpo que no es JSON no cambia lo que hay que contarle al usuario.
  }
  return new ErrorDeApi(respuesta.status, detalle, restriccion);
}

async function pedir<T>(ruta: string, init: RequestInit = {}): Promise<T> {
  const respuesta = await fetch(`${BASE}${ruta}`, {
    ...init,
    headers: { ...autorizacion(), ...init.headers },
  });
  if (!respuesta.ok) throw await fallo(respuesta);
  return (await respuesta.json()) as T;
}

export function listarCasos(): Promise<ResumenCaso[]> {
  return pedir<ResumenCaso[]>("/casos");
}

export function obtenerCaso(idCaso: string): Promise<DetalleCaso> {
  return pedir<DetalleCaso>(`/casos/${idCaso}`);
}

export function crearCaso(caso: NuevoCaso): Promise<DetalleCaso> {
  return pedir<DetalleCaso>("/casos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(caso),
  });
}

/**
 * Sube las plantillas del caso y devuelve las incidencias de lectura.
 *
 * La ruta oficial de carga no pasa por la API: el navegador pide una
 * autorización temporal y sube el archivo directamente al almacenamiento. Esa
 * ruta depende del contenedor del tenant (`R-23`) y de la plantilla definitiva
 * de MINSUR (`R-07`), así que mientras tanto se usa la de desarrollo, que solo
 * existe cuando la API corre en local.
 */
export interface LibrosDelCaso {
  caso: File;
  opex?: File;
  capex?: File;
  supuestos?: File;
  comite?: File;
}

export function cargarInsumos(
  idCaso: string,
  archivos: LibrosDelCaso,
): Promise<ResultadoValidacion> {
  const cuerpo = new FormData();
  cuerpo.append("caso", archivos.caso);
  for (const nombre of ["opex", "capex", "supuestos", "comite"] as const) {
    const archivo = archivos[nombre];
    if (archivo) cuerpo.append(nombre, archivo);
  }
  return pedir<ResultadoValidacion>(`/desarrollo/casos/${idCaso}/insumos`, {
    method: "POST",
    body: cuerpo,
  });
}

export function evaluar(idCaso: string): Promise<ResultadoEvaluacion> {
  return pedir<ResultadoEvaluacion>(`/casos/${idCaso}/evaluar`, { method: "POST" });
}

export function tableroDelCaso(idCaso: string): Promise<Tablero> {
  return pedir<Tablero>(`/tablero?caso=${encodeURIComponent(idCaso)}`);
}

export function bloquesDeLaCorrida(idCaso: string): Promise<BloquesDeCorrida> {
  return pedir<BloquesDeCorrida>(`/casos/${idCaso}/corrida/bloques`);
}
