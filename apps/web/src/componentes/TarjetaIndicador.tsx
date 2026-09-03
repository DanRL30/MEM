// Tarjeta de indicador.
//
// El valor puede ser nulo, y eso no es un fallo de carga: un caso que abre en
// positivo no tiene una tasa que describa su rentabilidad, y el libro escribe
// un guion en esa celda. La tarjeta dice por qué en lugar de mostrar un cero
// que se leería como un resultado calculado.

interface Props {
  titulo: string;
  valor: number | null | undefined;
  unidad: string;
  decimales?: number;
  nota?: string;
  motivoSiFalta?: string;
}

export function TarjetaIndicador({
  titulo,
  valor,
  unidad,
  decimales = 1,
  nota,
  motivoSiFalta = "El caso no la define",
}: Props) {
  const hayValor = valor !== null && valor !== undefined && Number.isFinite(valor);
  return (
    <article className="vidrio" style={{ padding: "var(--espacio-4)" }}>
      <h3
        style={{
          fontSize: "var(--texto-etiqueta)",
          letterSpacing: "var(--interletrado-etiqueta)",
          margin: 0,
          textTransform: "uppercase",
        }}
      >
        {titulo}
      </h3>
      {hayValor ? (
        <p className="cifra-grande" style={{ margin: "var(--espacio-2) 0 0" }}>
          {valor.toLocaleString("es-PE", {
            maximumFractionDigits: decimales,
            minimumFractionDigits: decimales,
          })}
          <span style={{ fontSize: "var(--texto-cuerpo)", marginLeft: "var(--espacio-2)" }}>
            {unidad}
          </span>
        </p>
      ) : (
        <p style={{ margin: "var(--espacio-2) 0 0" }}>
          <span aria-hidden="true" className="cifra-grande">
            &mdash;
          </span>
          <span style={{ display: "block", fontSize: "var(--texto-etiqueta)" }}>
            {motivoSiFalta}
          </span>
        </p>
      )}
      {nota ? (
        <p style={{ fontSize: "var(--texto-etiqueta)", margin: "var(--espacio-2) 0 0" }}>{nota}</p>
      ) : null}
    </article>
  );
}
