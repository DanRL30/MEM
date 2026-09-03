# Perfiles, accesos y permisos

Quién entra a la plataforma, qué ve y qué puede hacer. Es el insumo de la actividad H3
—autenticación y control de acceso por perfiles, 14/09/2026— y lo que TI de MINSUR necesita para
crear los grupos de seguridad (`R-21`) y el registro de aplicación (`R-26`).

**Los cinco perfiles los fija MINSUR y están cerrados.** Este documento no los discute: propone
cómo se traducen a permisos concretos sobre los objetos que la plataforma administra.

---

## 1. Los cinco perfiles

| Perfil | Grupo de seguridad en Entra ID | Qué sustenta |
|---|---|---|
| Administrador | `SG-MINSUR-EVALECO-ADMIN` | Configuración de la plataforma y datos maestros |
| Finanzas | `SG-MINSUR-EVALECO-FINANZAS` | Comité de Precios, parámetros corporativos y certificación de fidelidad |
| Líder de Estudio | `SG-MINSUR-EVALECO-LIDER` | La evaluación que respalda una decisión de inversión |
| Ingeniero de Proyecto | `SG-MINSUR-EVALECO-INGENIERO` | La carga de insumos y la ejecución del cálculo |
| Vicepresidencia y Gerentes Funcionales | `SG-MINSUR-EVALECO-EJECUTIVO` | Lectura de resultados para decidir |

El perfil no se elige ni se guarda en la plataforma: se deriva de la pertenencia al grupo, que
viaja firmada dentro del token de Entra ID. Un usuario que pertenece a varios grupos recibe el de
mayor alcance, en el orden de la tabla.

**El alta y la baja de usuarios ocurren en Entra ID, no en la plataforma.** No hay pantalla de
usuarios que administrar: quitarle el acceso a alguien es sacarlo del grupo, y eso lo hace TI de
MINSUR con sus procedimientos y su trazabilidad. Es deliberado —una segunda lista de usuarios sería
una segunda cosa que mantener y desincronizar— y conviene decirlo así en la homologación.

---

## 2. La matriz

Los objetos van en filas porque son los que crecen: los perfiles están cerrados y las
funcionalidades no.

| Objeto | Administrador | Finanzas | Líder de Estudio | Ingeniero de Proyecto | Vicepresidencia |
|---|---|---|---|---|---|
| Proyectos y casos de evaluación | V C E B | V | V C E B | V C E | V |
| Insumos del caso (producción, opex, capex) | V C E | V C E | V C E | V C E | V |
| Supuestos del caso | V C E | V C E | V C E | V C E | V |
| Comité de Precios | V | V C E A | V | V | V |
| Parámetros corporativos | V | V C E A | V | V | V |
| Evaluación: ejecutar y recalcular | V X | V | V X | V X | V |
| Congelamiento de una corrida | S | — | S | — | — |
| Tablero y estados financieros | V P | V P | V P | V P | V P |
| Historial de evaluaciones | V | V | V | V | V |
| Bitácora de auditoría | V | V | — | — | — |

**V** Ver · **C** Crear · **E** Editar · **B** Borrar · **X** Ejecutar el cálculo ·
**S** Sellar, es decir congelar · **A** Aprobar una versión de dato maestro ·
**P** Publicar, es decir exportar a Excel, PDF o SharePoint

---

## 3. Las siete reglas que explican la matriz

**1. Borrar solo alcanza a lo que aún es borrador.** Una corrida congelada no se borra, y no por
política sino por tecnología: es una imagen sellada con su resumen SHA-256 en un contenedor con
política de inmutabilidad. Prometer un permiso de borrado universal al Administrador sería prometer
algo que la plataforma no puede cumplir, y que no debe.

**2. La bitácora no se borra ni se edita, tampoco por el Administrador.** Es de solo escritura y
encadenada: cada entrada lleva el resumen de la anterior, de modo que suprimir una intermedia rompe
la cadena y la verificación lo detecta. Una bitácora que admite correcciones no sirve como
evidencia, que es justamente para lo que existe.

**3. Congelar es de quien sustenta la decisión, no de quien opera la plataforma.** El Ingeniero de
Proyecto carga y ejecuta; el Líder de Estudio es quien declara que una evaluación respalda una
decisión de inversión. Por eso el sellado está restringido a Líder de Estudio y Administrador.

**4. Finanzas gobierna el dato maestro, no la evaluación del área de Proyectos.** Aprueba el Comité
de Precios y los parámetros corporativos, y esa aprobación es un control real: una versión sin
nombre y fecha de quien la aprobó se rechaza al cargarla. Por el mismo motivo Finanzas no congela
evaluaciones de Proyectos ni las ejecuta.

**5. El Administrador no edita el dato maestro que Finanzas aprueba.** Si el perfil que administra
la plataforma puede cambiar un precio aprobado, la aprobación deja de ser un control. Es el cambio
que este documento propone frente al borrador inicial, donde el Administrador podía crear, editar y
borrar en las seis columnas.

**6. Recalcular nunca sobrescribe.** Volver a calcular una corrida congelada produce una corrida
nueva que apunta a la anterior. La evidencia que sustentó una decisión no deja de existir, así que
recalcular no necesita un permiso más restrictivo que ejecutar.

**7. Ver es transversal y no se recorta por proyecto.** Los cinco perfiles ven todos los casos. Si
MINSUR necesita que un Ingeniero vea solo los suyos, es una restricción por proyecto que hoy no
está en el alcance y cambia el modelo de datos: se decide antes de H3, no después.

---

## 4. Lo que falta decidir

| # | Pregunta | Por qué bloquea | Quién decide |
|---|---|---|---|
| 1 | La etapa FEL, ¿es un atributo del caso o un objeto con permisos propios? | Si es objeto, entra como fila de la matriz y como entidad del modelo de datos | Vicepresidencia de Proyectos |
| 2 | Con el perfil Auditor descartado, ¿quién lee la bitácora además del Administrador? | La propuesta es Finanzas, por ser quien certifica la fidelidad y sustenta ante una auditoría externa. Sin decisión, la bitácora queda con un solo lector | MINSUR |
| 3 | ¿Los escenarios de sensibilidad heredan los permisos del caso? | Sensibilidad y Montecarlo llegan en PT5 y hoy no tienen fila propia | Líder de Estudio |
| 4 | ¿La exportación a SharePoint la puede lanzar cualquier perfil que vea el tablero? | Publicar en la biblioteca documental del proyecto deja rastro fuera de la plataforma | TI de MINSUR |

---

## 5. Cómo se verifica

El control de acceso no se declara: se prueba. La comprobación de aceptación de H3 es autenticar
con una cuenta de cada uno de los cinco perfiles y verificar que cada una ve lo que le corresponde
y recibe un rechazo explícito en lo que no.

El rechazo es del servidor, no de la interfaz. Que un botón no aparezca es comodidad de uso, no un
control: la plataforma vuelve a verificar el perfil en cada operación aunque la puerta de enlace ya
haya validado el token.
