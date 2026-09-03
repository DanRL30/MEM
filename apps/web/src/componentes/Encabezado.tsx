// Cabecera de la aplicación.
//
// El logotipo no se importa por su ruta: se recoge lo que haya en
// `activos/marca/`. Colocar ahí el SVG que MINSUR entregó es todo lo que hace
// falta para que aparezca, sin tocar este archivo. Mientras no esté, la
// cabecera dibuja el nombre del servicio en tipografía corporativa, que es una
// ausencia legible y no un hueco roto.
//
// La política de seguridad de contenido declara `img-src 'self' data:`, así que
// el archivo tiene que servirse del propio origen. Vite lo empaqueta con su
// huella desde `src/`, que es la razón de que viva ahí y no en `public/`.

const LOGOTIPOS = import.meta.glob<string>("../activos/marca/*.svg", {
  eager: true,
  import: "default",
  query: "?url",
});

function logotipo(): string | undefined {
  const rutas = Object.keys(LOGOTIPOS).sort();
  const color = rutas.find((r) => r.includes("color"));
  return LOGOTIPOS[color ?? rutas[0] ?? ""];
}

interface Props {
  caso?: { nombre: string; chips: string[] };
}

export function Encabezado({ caso }: Props) {
  const marca = logotipo();
  return (
    <header
      className="vidrio"
      style={{
        alignItems: "center",
        borderRadius: 0,
        display: "flex",
        gap: "var(--espacio-4)",
        padding: "var(--espacio-3) var(--espacio-5)",
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}
    >
      {marca ? (
        <img src={marca} alt="MINSUR" style={{ height: "1.75rem" }} />
      ) : (
        <span style={{ fontWeight: "var(--peso-titular)" }}>MINSUR</span>
      )}

      <span aria-hidden="true" style={{ color: "var(--borde-sutil)" }}>
        |
      </span>

      <h1 style={{ fontSize: "var(--texto-subtitulo)", margin: 0 }}>
        Plataforma de Evaluación Económica
      </h1>

      {caso ? (
        <div
          style={{
            alignItems: "center",
            display: "flex",
            gap: "var(--espacio-2)",
            marginLeft: "auto",
          }}
        >
          <strong>{caso.nombre}</strong>
          {caso.chips.map((chip) => (
            <span className="pildora" key={chip}>
              {chip}
            </span>
          ))}
        </div>
      ) : null}
    </header>
  );
}
