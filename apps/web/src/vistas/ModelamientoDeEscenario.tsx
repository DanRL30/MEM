// Modelamiento de escenario: crear, cargar las plantillas y recorrer el cálculo.
//
// Las pestañas van en el orden del libro corporativo, no en el de la cadena de
// cálculo. `Depreciación` aparece antes que `Ventas` porque así está en el
// libro, aunque el cálculo no lo exija: el orden es el que el usuario tiene
// aprendido, y ese es el requisito.
//
// El orden de los bloques lo fija la API, no esta pantalla. Si mañana el libro
// cambiara, se corrige en un sitio y las once pestañas siguen.

import { useEffect, useState } from "react";

import {
  bloquesDeLaCorrida,
  cargarInsumos,
  crearCaso,
  evaluar,
  listarCasos,
  obtenerCaso,
  tableroDelCaso,
  ErrorDeApi,
  type BloquesDeCorrida,
  type DetalleCaso,
  type LibrosDelCaso,
  type NuevoCaso,
  type Indicadores,
  type ResultadoEvaluacion,
  type ResultadoValidacion,
  type ResumenCaso,
} from "../api/cliente";
import { AsistenteDeEscenario } from "../componentes/AsistenteDeEscenario";
import { CargaDePlantilla } from "../componentes/CargaDePlantilla";
import { Encabezado } from "../componentes/Encabezado";
import { ListaDeIncidencias } from "../componentes/ListaDeIncidencias";
import { PanelVidrio } from "../componentes/PanelVidrio";
import { Pestanas, type Pestana } from "../componentes/Pestanas";
import { TablaDelLibro } from "../componentes/TablaDelLibro";
import { TarjetaIndicador } from "../componentes/TarjetaIndicador";

const CONTROL = "control";
const RESUMEN = "resumen";

/** Una corrida se identifica por su terna, no por «lo vigente». */
function chipsDeLaTerna(
  terna: ResultadoEvaluacion["terna"] | null | undefined,
  estado: string,
): string[] {
  if (!terna) return [estado];
  return [
    estado,
    `Motor ${terna.motor}`,
    `Datos ${terna.datos_maestros}`,
    `Revisión r${String(terna.revision_inputs)}`,
  ];
}

export function ModelamientoDeEscenario() {
  const [caso, setCaso] = useState<DetalleCaso | null>(null);
  const [validacion, setValidacion] = useState<ResultadoValidacion | null>(null);
  const [evaluacion, setEvaluacion] = useState<ResultadoEvaluacion | null>(null);
  const [bloques, setBloques] = useState<BloquesDeCorrida | null>(null);
  const [indicadores, setIndicadores] = useState<Indicadores | null>(null);
  const [activa, setActiva] = useState(CONTROL);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<ErrorDeApi | null>(null);
  const [existentes, setExistentes] = useState<ResumenCaso[]>([]);

  // El almacen es en memoria mientras Azure SQL no exista (`R-23`), asi que la
  // lista se pierde al reiniciar la API. Mientras el proceso viva, permite
  // volver a un escenario sin rehacerlo: recargar la pagina no deberia costar
  // una carga de plantillas.
  useEffect(() => {
    void listarCasos()
      .then(setExistentes)
      .catch(() => {
        // Que la lista no cargue no impide crear un escenario nuevo.
      });
  }, [caso]);

  async function conError(trabajo: () => Promise<void>) {
    setOcupado(true);
    setError(null);
    try {
      await trabajo();
    } catch (fallo) {
      setError(
        fallo instanceof ErrorDeApi
          ? fallo
          : new ErrorDeApi(0, "No se pudo contactar con la API. ¿Está levantada?", null),
      );
    } finally {
      setOcupado(false);
    }
  }

  function alCrear(nuevo: NuevoCaso) {
    void conError(async () => {
      setCaso(await crearCaso(nuevo));
      setValidacion(null);
      setEvaluacion(null);
      setIndicadores(null);
      setBloques(null);
    });
  }

  function alAbrir(id: string) {
    void conError(async () => {
      setCaso(await obtenerCaso(id));
      setValidacion(null);
      setEvaluacion(null);
      try {
        setBloques(await bloquesDeLaCorrida(id));
        // La corrida ya existe: sus indicadores salen del tablero, sin volver
        // a calcular. Recalcular para mirar seria crear una corrida nueva.
        setIndicadores((await tableroDelCaso(id)).indicadores);
        setActiva("produccion");
      } catch {
        // Un caso sin corrida responde 409 y no es un error que mostrar: se
        // abre en Control, que es donde se cargan sus plantillas.
        setBloques(null);
        setIndicadores(null);
        setActiva(CONTROL);
      }
    });
  }

  function alCargar(archivos: LibrosDelCaso) {
    const actual = caso;
    if (!actual) return;
    void conError(async () => {
      const leido = await cargarInsumos(actual.id_caso, archivos);
      setValidacion(leido);
      if (!leido.valida) return;
      // Cargar y calcular son dos pasos, y el segundo es el endpoint de
      // evaluación de siempre: registra la terna y entra al historial.
      const resultado = await evaluar(actual.id_caso);
      setEvaluacion(resultado);
      setIndicadores(resultado.indicadores);
      setBloques(await bloquesDeLaCorrida(actual.id_caso));
      setActiva("produccion");
    });
  }

  const pestanas: Pestana[] = [
    { clave: CONTROL, etiqueta: "Control", titulo: "Caso, plantillas y control de calidad" },
    ...(bloques?.bloques ?? []).map((bloque) => ({
      clave: bloque.clave,
      etiqueta: bloque.etiqueta,
      titulo: bloque.titulo,
    })),
    ...(indicadores
      ? [{ clave: RESUMEN, etiqueta: "Resumen", titulo: "Indicadores del caso" }]
      : []),
  ];

  const bloqueActivo = bloques?.bloques.find((b) => b.clave === activa);
  // El esquema declara estas dos con valor por defecto, de modo que el tipo
  // generado las trae opcionales. Se normalizan aqui y no en cada uso.
  const incidencias = validacion?.incidencias ?? [];
  const discrepancias = bloques?.discrepancias ?? [];

  return (
    <>
      <Encabezado
        {...(caso
          ? {
              caso: {
                nombre: caso.abreviatura || caso.nombre,
                chips: chipsDeLaTerna(evaluacion?.terna ?? caso.terna, caso.estado),
              },
            }
          : {})}
      />

      <main
        aria-label="Contenido principal"
        style={{
          display: "grid",
          gap: "var(--espacio-5)",
          // Sin `minmax(0, 1fr)` un hijo de rejilla no se encoge por debajo de
          // su contenido, y la hoja -que mide lo que midan sus ejercicios-
          // desborda la ventana en vez de desplazarse por dentro.
          gridTemplateColumns: "minmax(0, 1fr)",
          padding: "var(--espacio-5)",
        }}
      >
        {error ? (
          <div
            className="vidrio"
            role="alert"
            style={{ borderColor: "var(--estado-error)", padding: "var(--espacio-4)" }}
          >
            <strong>{error.detalle}</strong>
            {error.restriccion ? (
              <p style={{ margin: "var(--espacio-2) 0 0" }}>
                Bloqueado por la restricción <code>{error.restriccion}</code>. No es un fallo de la
                plataforma: es un insumo del cliente que todavía no ha llegado.
              </p>
            ) : null}
          </div>
        ) : null}

        {caso === null ? (
          <>
            <div style={{ maxWidth: "48rem" }}>
              <PanelVidrio titulo="Nuevo escenario">
                <AsistenteDeEscenario alCrear={alCrear} creando={ocupado} />
              </PanelVidrio>
            </div>
            {existentes.length > 0 ? (
              <PanelVidrio tenue titulo="Escenarios abiertos">
                <ul style={{ margin: 0, paddingLeft: "var(--espacio-5)" }}>
                  {existentes.map((existente) => (
                    <li key={existente.id_caso}>
                      <button
                        className="enlace"
                        onClick={() => {
                          alAbrir(existente.id_caso);
                        }}
                        type="button"
                      >
                        {existente.abreviatura || existente.nombre}
                      </button>{" "}
                      · {existente.nombre} · {existente.id_caso} · {existente.estado}
                    </li>
                  ))}
                </ul>
              </PanelVidrio>
            ) : null}
          </>
        ) : (
          <>
            <Pestanas activa={activa} alCambiar={setActiva} pestanas={pestanas} />

            <div
              aria-labelledby={`pestana-${activa}`}
              id={`panel-${activa}`}
              role="tabpanel"
              tabIndex={0}
            >
              {activa === CONTROL ? (
                <PanelVidrio titulo="Control">
                  <p>
                    <strong>{caso.abreviatura}</strong> · {caso.nombre} · {caso.id_caso}
                    {caso.descripcion ? ` · ${caso.descripcion}` : ""}
                  </p>

                  <CargaDePlantilla alEnviar={alCargar} cargando={ocupado} />
                  {validacion ? (
                    <>
                      <p>
                        {validacion.filas_leidas} líneas con dato leídas.
                        {validacion.huella ? ` Huella ${validacion.huella.slice(0, 12)}…` : ""}
                      </p>
                      <ListaDeIncidencias incidencias={incidencias} />
                    </>
                  ) : null}

                  {discrepancias.length > 0 ? (
                    <div role="alert" style={{ marginTop: "var(--espacio-4)" }}>
                      <h3>Control de calidad</h3>
                      <p>
                        El recálculo no coincide con el dato cargado en{" "}
                        {discrepancias.length} celdas. El cálculo usa el dato del usuario:
                        corroborar audita y no sustituye nunca.
                      </p>
                      <ul>
                        {discrepancias.slice(0, 10).map((d) => (
                          <li key={`${d.unidad}-${d.concepto}-${String(d.ano)}`}>
                            {d.unidad} · {d.concepto} · {d.ano}: cargado {d.cargado}, esperado{" "}
                            {d.recalculado}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  <p style={{ fontSize: "var(--texto-etiqueta)", marginTop: "var(--espacio-5)" }}>
                    La hoja <code>Supuestos</code> todavía no tiene pestaña propia: sus series
                    llegan aplicadas al caso y el contrato aún no las publica por separado.
                  </p>
                </PanelVidrio>
              ) : null}

              {activa === RESUMEN && indicadores ? (
                <div
                  style={{
                    display: "grid",
                    gap: "var(--espacio-4)",
                    gridTemplateColumns: "repeat(auto-fit, minmax(14rem, 1fr))",
                  }}
                >
                  <TarjetaIndicador
                    nota="Descuento a fin de año"
                    titulo="Valor actual neto"
                    unidad="MM US$"
                    valor={indicadores.npv_musd}
                  />
                  <TarjetaIndicador
                    decimales={2}
                    motivoSiFalta="El caso no abre con desembolso"
                    nota="Solo con desembolso inicial y raíz no negativa"
                    titulo="Tasa interna de retorno"
                    unidad="%"
                    valor={
                      indicadores.tir === null || indicadores.tir === undefined
                        ? null
                        : indicadores.tir * 100
                    }
                  />
                  <TarjetaIndicador
                    titulo="Periodo de recuperación"
                    unidad="años"
                    valor={indicadores.payback_anios}
                  />
                  <TarjetaIndicador
                    decimales={0}
                    motivoSiFalta="El caso no declara capacidad"
                    titulo="Capital intensity"
                    unidad="US$/t"
                    valor={indicadores.capital_intensity}
                  />
                </div>
              ) : null}

              {bloqueActivo && bloques ? (
                <TablaDelLibro anios={bloques.anios} grupos={bloqueActivo.grupos} />
              ) : null}
            </div>
          </>
        )}
      </main>
    </>
  );
}
