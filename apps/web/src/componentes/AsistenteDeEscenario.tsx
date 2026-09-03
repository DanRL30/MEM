// Creación de un escenario dentro de un FEL.
//
// **Ni el proyecto ni la fase FEL se preguntan aquí.** Se llega a esta pantalla
// entrando a un proyecto, después a uno de sus FEL, y dentro de ese FEL están
// todos sus escenarios: los dos son contexto de navegación, y volver a
// preguntarlos abriría la puerta a que la respuesta contradiga el sitio desde
// el que se está creando.
//
// Lo que sí se elige es de qué lado de la comparación está el escenario. Una
// evaluación de inversión son dos corridas —la operación sin el proyecto y la
// operación con él— y el indicador que sustenta la decisión es la diferencia
// entre ambas. Por eso el tipo tiene dos valores y no una lista de metales:
// que el concentrado sea monometálico o polimetálico se deduce de las unidades
// que el caso declare, y no es algo que nadie deba teclear al abrirlo.
//
// El modelo de cálculo sigue en el formulario porque es lo primero que el
// cliente describió el 25/08/2026. **Marcobre y Energías Renovables se muestran
// y no se pueden elegir**: ocultarlos perdería la señal de que están previstos,
// y habilitarlos produciría un caso que no calcula.
//
// La abreviatura va antes del nombre y es obligatoria. Es el rótulo con el que
// el escenario aparece donde el nombre completo no cabe: la cabecera, la lista,
// y sobre todo una comparación, que enfrenta dos escenarios columna contra
// columna. Un campo opcional acabaría vacío en la mitad de los casos y esas
// tablas tendrían que caer al nombre largo justo donde menos sitio hay.

import { useState } from "react";

import type { NuevoCaso } from "../api/cliente";

const MODELOS = [
  { clave: "minsur", nombre: "Minsur", disponible: true },
  { clave: "marcobre", nombre: "Marcobre", disponible: false },
  { clave: "renovables", nombre: "Energías Renovables", disponible: false },
] as const;

type TipoDeCaso = NuevoCaso["tipo"];

const TIPOS: { clave: TipoDeCaso; nombre: string; ayuda: string }[] = [
  {
    clave: "con-proyecto",
    nombre: "Con proyecto",
    ayuda: "La operación incluyendo la inversión que se evalúa",
  },
  {
    clave: "sin-proyecto",
    nombre: "Sin proyecto",
    ayuda: "La operación como seguiría sin ella, que es la base de comparación",
  },
];

interface Props {
  creando: boolean;
  alCrear: (caso: NuevoCaso) => void;
}

export function AsistenteDeEscenario({ creando, alCrear }: Props) {
  const [abreviatura, setAbreviatura] = useState("");
  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [tipo, setTipo] = useState<TipoDeCaso>("con-proyecto");

  function enviar(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    alCrear({
      abreviatura: abreviatura.trim(),
      nombre: nombre.trim(),
      tipo,
      descripcion: descripcion.trim(),
    });
  }

  return (
    <form onSubmit={enviar}>
      <fieldset style={{ border: "none", margin: 0, padding: 0 }}>
        <legend style={{ padding: 0 }}>Modelo de cálculo</legend>
        {/* Envuelve en vez de estrujarse: la etiqueta mas larga no cabe junto a
            las otras dos en la columna del formulario, y sin `wrap` partia su
            texto en dos lineas dentro de la pildora. */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "var(--espacio-2)",
            marginBottom: "var(--espacio-4)",
          }}
        >
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
        <span>Abreviatura</span>
        <input
          maxLength={16}
          onChange={(e) => {
            setAbreviatura(e.target.value);
          }}
          placeholder="SD Fase III"
          required
          type="text"
          value={abreviatura}
        />
      </label>

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

      <fieldset style={{ border: "none", margin: "0 0 var(--espacio-4)", padding: 0 }}>
        <legend style={{ padding: 0 }}>Tipo de caso</legend>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--espacio-4)" }}>
          {TIPOS.map((opcion) => (
            <label className="pildora" key={opcion.clave} title={opcion.ayuda}>
              <input
                checked={tipo === opcion.clave}
                name="tipo"
                onChange={() => {
                  setTipo(opcion.clave);
                }}
                type="radio"
                value={opcion.clave}
              />{" "}
              {opcion.nombre}
            </label>
          ))}
        </div>
      </fieldset>

      <label style={{ display: "block", marginBottom: "var(--espacio-4)" }}>
        <span>Descripción (opcional)</span>
        <input
          onChange={(e) => {
            setDescripcion(e.target.value);
          }}
          type="text"
          value={descripcion}
        />
      </label>

      <button
        className="pildora"
        disabled={creando || nombre.trim() === "" || abreviatura.trim().length < 2}
        type="submit"
      >
        {creando ? "Creando…" : "Crear escenario"}
      </button>
    </form>
  );
}
