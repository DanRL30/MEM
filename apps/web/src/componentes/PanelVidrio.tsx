// Lámina de vidrio: la superficie de cromo de la interfaz.
//
// El efecto vive en `estilos/superficie.css`, con sus dos reservas por si el
// navegador no lo soporta o el usuario ha pedido menos transparencia. Aquí solo
// se compone la estructura.

import type { ReactNode } from "react";

interface Props {
  titulo?: string;
  acciones?: ReactNode;
  tenue?: boolean;
  children: ReactNode;
}

export function PanelVidrio({ titulo, acciones, tenue = false, children }: Props) {
  return (
    <section className={tenue ? "vidrio vidrio-tenue" : "vidrio"} style={{ padding: "var(--espacio-5)" }}>
      {(titulo ?? acciones) ? (
        <header
          style={{
            alignItems: "baseline",
            display: "flex",
            gap: "var(--espacio-4)",
            justifyContent: "space-between",
            marginBottom: "var(--espacio-4)",
          }}
        >
          {titulo ? <h2 style={{ margin: 0 }}>{titulo}</h2> : <span />}
          {acciones}
        </header>
      ) : null}
      {children}
    </section>
  );
}
