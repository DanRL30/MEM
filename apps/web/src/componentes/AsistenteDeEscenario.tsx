// Creación de un escenario, según el acuerdo del 25/08/2026.
//
// El orden de las tres decisiones es el que MINSUR describió: primero el modelo
// de cálculo, después el proyecto y por último la fase del estudio.
//
// **Marcobre y Energías Renovables se muestran y no se pueden elegir.** Es
// deliberado: el cliente pidió que estuvieran a la vista como proyección. Un
// modelo que se pudiera seleccionar sin que exista detrás produciría un caso
// que no calcula, y ocultarlos perdería la señal de que están previstos.
//
// El catálogo de proyectos es provisional. Lo definitivo lo mantiene MINSUR
// como dato maestro; hasta entonces estas son las unidades del modelo vigente.

import { useState } from "react";

import type { NuevoCaso } from "../api/cliente";

const MODELOS = [
  { clave: "minsur", nombre: "Minsur", disponible: true },
  { clave: "marcobre", nombre: "Marcobre", disponible: false },
  { clave: "renovables", nombre: "Energías Renovables", disponible: false },
] as const;

const PROYECTOS = [
  { clave: "SD", nombre: "Santo Domingo" },
  { clave: "NZ", nombre: "Nazareth" },
  { clave: "SR", nombre: "San Rafael" },
] as const;

const FASES = ["Identificación", "Selección", "Definición"] as const;

// Los tipos son los que acepta el esquema de la API, y de ellos sale el prefijo
// del identificador del caso. El tipo viene del contrato y no se escribe aquí:
// si la API admitiera uno nuevo, esta lista deja de compilar hasta recogerlo.
type TipoDeCaso = NuevoCaso["tipo"];

const TIPOS: { clave: TipoDeCaso; nombre: string }[] = [
  { clave: "monometalico", nombre: "Monometálico" },
  { clave: "polimetalico", nombre: "Polimetálico" },
  { clave: "sin-proyecto", nombre: "Sin proyecto" },
];

interface Props {
  creando: boolean;
  alCrear: (caso: NuevoCaso) => void;
}

export function AsistenteDeEscenario({ creando, alCrear }: Props) {
  const [nombre, setNombre] = useState("");
  const [proyecto, setProyecto] = useState<string>(PROYECTOS[0].clave);
  const [fase, setFase] = useState<string>(FASES[0]);
  const [tipo, setTipo] = useState<TipoDeCaso>("monometalico");

  function enviar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const proyectoElegido = PROYECTOS.find((p) => p.clave === proyecto);
    alCrear({
      nombre: nombre.trim(),
      tipo,
      descripcion: `Proyecto ${proyectoElegido?.nombre ?? proyecto} · fase de ${fase}`,
    });
  }

  return (
    <form onSubmit={enviar}>
      <fieldset style={{ border: "none", margin: 0, padding: 0 }}>
        <legend style={{ padding: 0 }}>Modelo de cálculo</legend>
        <div style={{ display: "flex", gap: "var(--espacio-2)", marginBottom: "var(--espacio-4)" }}>
          {MODELOS.map((modelo) => (
            <label
              className="pildora"
              key={modelo.clave}
              style={{ opacity: modelo.disponible ? 1 : 0.45 }}
              title={modelo.disponible ? undefined : "Previsto, todavía no disponible"}
            >
              <input
                defaultChecked={modelo.disponible}
                disabled={!modelo.disponible}
                name="modelo"
                type="radio"
                value={modelo.clave}
              />{" "}
              {modelo.nombre}
            </label>
          ))}
        </div>
      </fieldset>

      <label style={{ display: "block", marginBottom: "var(--espacio-4)" }}>
        <span>Nombre del escenario</span>
        <input
          onChange={(e) => {
            setNombre(e.target.value);
          }}
          required
          type="text"
          value={nombre}
        />
      </label>

      <div style={{ display: "flex", gap: "var(--espacio-4)", marginBottom: "var(--espacio-4)" }}>
        <label>
          <span>Proyecto</span>
          <select
            onChange={(e) => {
              setProyecto(e.target.value);
            }}
            value={proyecto}
          >
            {PROYECTOS.map((p) => (
              <option key={p.clave} value={p.clave}>
                {p.nombre}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Fase</span>
          <select
            onChange={(e) => {
              setFase(e.target.value);
            }}
            value={fase}
          >
            {FASES.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Tipo de caso</span>
          <select
            onChange={(e) => {
              setTipo(e.target.value as TipoDeCaso);
            }}
            value={tipo}
          >
            {TIPOS.map((t) => (
              <option key={t.clave} value={t.clave}>
                {t.nombre}
              </option>
            ))}
          </select>
        </label>
      </div>

      <button className="pildora" disabled={creando || nombre.trim() === ""} type="submit">
        {creando ? "Creando…" : "Crear escenario"}
      </button>
    </form>
  );
}
