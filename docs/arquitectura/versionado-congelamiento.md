# Versionado, congelamiento y auditoría

**Actividad** PT1.8 · **Servicio** `INVA-01-2026-182` · **Rev. A** · 24/08/2026

Diseño del mecanismo que sostiene dos requisitos del alcance situados por encima de los demás: que
cada evaluación sea **reproducible indefinidamente** con la información exacta que la generó, y que
una evaluación usada como sustento de decisión quede **preservada de forma permanente e inmutable**.

Del primero depende que los resultados puedan sustentar decisiones de inversión ante auditoría. Del
segundo, que esa evidencia siga existiendo cuando alguien la pida años después.

> Este es el punto del diseño con mayor costo de reversión. El Plan de Trabajo advierte que el
> congelamiento y los perfiles de acceso **estructuran directamente el modelo de datos**, y que un
> ajuste posterior exigiría reconfigurar la capa de persistencia.

---

## 1. Versionado en tres ejes

Una evaluación queda definida por tres versiones que cambian a ritmos distintos y por decisión de
actores distintos.

| Eje | Cambia cuando | Decide | Tipo |
|---|---|---|---|
| Motor de cálculo | Finanzas modifica el modelo corporativo | Finanzas | `VersionMotor` |
| Datos maestros | Se publica un Comité de Precios | Finanzas | `VersionDatosMaestros` |
| Inputs del caso | El Líder de Estudio itera sobre el caso | Proyectos | `VersionInputs` |

Registrarlas por separado no es refinamiento de trazabilidad: es lo que permite cumplir el requisito
de que **los cambios que Finanzas introduzca en el modelo no alteren evaluaciones previas**. Si la
corrida guardara solo «la versión vigente», publicar una versión nueva reescribiría la historia.

De ahí se derivan tres reglas que el código hace cumplir:

1. Una corrida guarda **la terna exacta** con la que se calculó, nunca una referencia a lo vigente.
2. Las versiones del motor **coexisten en producción**. Una corrida antigua se recalcula con su
   propio motor.
3. Recalcular **nunca sobrescribe**: produce una corrida nueva que apunta a la anterior como origen.

### Semántica de la versión del motor

El significado de cada componente está atado a lo que cambió en el modelo, no a conveniencias de
desarrollo:

| Componente | Significado | Consecuencia |
|---|---|---|
| `mayor` | Cambia una regla de cálculo; los resultados difieren | Los casos certificados deben recontrastarse antes de desplegar |
| `menor` | Se añade una línea o un indicador, sin alterar los existentes | Los casos certificados siguen válidos |
| `parche` | Corrección de un defecto de implementación de INVA | Se documenta en la bitácora de discrepancias |

`TernaVersion.comparable_con` usa esa semántica para advertir antes de mostrar el comparador:
contrastar un caso base calculado con el motor 1.x contra un caso con proyecto calculado con 2.x
produce una diferencia que no es atribuible al proyecto.

---

## 2. Máquina de estados

```
    ┌───────────┐  ejecutar   ┌────────────┐  congelar   ┌───────────┐
    │ BORRADOR  │────────────▶│ CALCULADA  │────────────▶│ CONGELADA │
    └───────────┘             └────────────┘             └───────────┘
          ▲   editar insumos        │                          │
          └─────────────────────────┘                     (terminal)
```

| Desde | Acción | Hasta | Perfiles autorizados |
|---|---|---|---|
| Borrador | Ejecutar | Calculada | Administrador · Líder de Estudio · Ingeniero de Proyecto |
| Calculada | Editar insumos | Borrador | Administrador · Líder de Estudio · Ingeniero de Proyecto |
| Calculada | **Congelar** | **Congelada** | Administrador · Líder de Estudio |
| Congelada | *(ninguna)* | — | — |

**Congelar corresponde a quien sustenta la decisión, no a quien opera la plataforma.** El Ingeniero
de Proyecto carga y ejecuta; el Líder de Estudio es quien declara que una evaluación respalda una
decisión de inversión.

**Finanzas no aparece en la tabla a propósito.** Gobierna los parámetros maestros y la versión del
motor —eso vive en otra máquina de estados— pero no congela evaluaciones del área de Proyectos.

Consulta Ejecutiva y Auditor no tienen ninguna acción disponible en ningún estado.

### Recalcular no es una transición

Desde el estado congelado el usuario puede **recalcular**, que crea una corrida nueva en estado
Calculada apuntando a la anterior como origen. La corrida congelada permanece intacta.

Es la única forma de que el usuario vea el efecto de un cambio del modelo sin que la evidencia que
sustentó una decisión deje de existir. El mensaje de error de la transición prohibida lo indica de
forma explícita, para que nadie concluya que la plataforma se lo impide todo.

---

## 3. La imagen sellada

Paquete autocontenido que se deposita en el contenedor con política de inmutabilidad.

### Contenido

Lo que hace falta para reproducir el cálculo, y nada más. Si algo no está dentro, el recálculo
dependería de leerlo de otro sitio, y ese otro sitio puede haber cambiado.

```
id_caso · terna de versiones · inputs · parámetros · resultados
```

**Los parámetros se guardan por valor, no por referencia al Comité de Precios.** El comité es un
registro maestro que se consulta; la imagen es evidencia que se conserva.

### Dos resúmenes, no uno

| Resumen | Cubre | Responde |
|---|---|---|
| `huella_contenido` | Lo necesario para reproducir | ¿El recálculo da lo mismo? |
| `huella_sello` | La imagen completa, metadatos incluidos | ¿Alguien tocó la imagen? |

Confundirlos haría que un cambio de metadato pareciera una divergencia de cálculo.

### Por qué la serialización canónica es el punto delicado

Un SHA-256 sobre `json.dumps(datos)` parece suficiente y no lo es. El mismo contenido produce
resúmenes distintos si cambia el orden de las claves, si el separador lleva espacio, si un flotante
se escribe `0.1` en una versión de Python y `0.10000000000000001` en otra, o si una fecha se
serializa en zona local en un servidor y en UTC en otro.

Nada de eso es hipotético a cinco años vista. La verificación programada reportaría incidentes que
no son incidentes, y el mecanismo perdería credibilidad justo cuando hace falta.

`canonicalizar` fija cuatro decisiones de forma explícita:

| Decisión | Valor |
|---|---|
| Orden de claves | Alfabético, en todos los niveles |
| Separadores | Sin espacios |
| Codificación | UTF-8, sin escapar caracteres no ASCII |
| Flotantes | Normalizados a 12 decimales; `-0.0` se convierte en `0.0` |
| Marcas de tiempo | UTC explícito; una marca sin zona se **rechaza** en lugar de suponerse |
| `NaN` e infinito | Se rechazan: una evaluación con valores indefinidos no puede sustentar una decisión |

Doce decimales exceden con holgura la precisión significativa de una evaluación económica y quedan
muy por debajo del límite donde el doble precisión pierde exactitud, de modo que la normalización
nunca altera un resultado que importe.

### Verificación de reproducibilidad

El alcance pide que la reproducibilidad **se verifique de forma activa y no se presuma**. Una
función programada recalcula una muestra de corridas congeladas desde su imagen y compara.

La comparación es de **igualdad exacta sobre la forma canónica**, no por tolerancia. La tolerancia
tiene sentido al contrastar contra el modelo de referencia, donde hay dos implementaciones
distintas; aquí es la misma implementación con las mismas entradas, y cualquier diferencia es un
hallazgo.

Cuando hay divergencia, el veredicto localiza **las líneas concretas** que difieren, para que el
incidente sea accionable y no un aviso genérico.

---

## 4. Bitácora de auditoría

De solo escritura y encadenada.

**Solo escritura.** La clase `Bitacora` no expone operación de modificación ni de borrado, y en el
almacenamiento la tabla se protege con la misma política de anexado que el contenedor de imágenes
selladas. Una bitácora que admite correcciones no sirve como evidencia.

**Encadenada.** Cada entrada incluye el resumen de la anterior. Suprimir una entrada intermedia
rompe la cadena y `verificar` lo detecta. Sin encadenamiento, un actor con acceso al almacenamiento
podría eliminar el rastro de una acción en lugar de alterarlo, que es bastante más difícil de notar.

La consulta no se registra: con diecisiete usuarios abriendo un tablero, registrarla ahogaría lo que
importa.

### Cobertura de los ocho requisitos de gobierno del alcance

| # | Requisito | Dónde se cumple |
|---|---|---|
| 1 | Versionado de insumos | `Entrada.valor_anterior` / `valor_posterior` + `VersionInputs.revision` |
| 2 | Parámetros efectivamente empleados | `Contenido.parametros` de la imagen sellada, por valor |
| 3 | Responsable de la carga | `Entrada.usuario` + `Entrada.perfil` |
| 4 | Fecha y hora de creación y ejecución | `Entrada.marca_tiempo` en UTC |
| 5 | Documentación de respaldo y aprobaciones | `ImagenSellada.respaldos` + `Accion.RESPALDO_ASOCIADO` |
| 6 | Historial de cambios | `Bitacora.historial_de_cambios` |
| 7 | Origen de la información | `Entrada.origen` |
| 8 | Reproducir con los mismos datos | `sellado.verificar_reproducibilidad` |

`auditoria.informe_cobertura()` genera esta tabla para el manual técnico y el paquete de evidencia
que se entrega a Seguridad de la Información.

---

## 5. Implementación

| Módulo | Responsabilidad |
|---|---|
| `packages/domain/src/minsur_domain/versionado.py` | Los tres ejes y la terna |
| `packages/domain/src/minsur_domain/estados.py` | Máquina de estados y permisos por perfil |
| `packages/domain/src/minsur_domain/sellado.py` | Canonicalización, imagen sellada y verificación |
| `packages/domain/src/minsur_domain/auditoria.py` | Bitácora encadenada y cobertura del alcance |

**50 pruebas**, con el peso en canonicalización: orden de claves, cero negativo, zonas horarias,
valores indefinidos, estabilidad entre invocaciones y el umbral de precisión por arriba y por abajo.

---

## 6. Lo que este diseño asume y aún no está confirmado

| Supuesto | Restricción | Efecto si cambia |
|---|---|---|
| Tres estados bastan; no hay anulación ni archivado | `R-08` | Un estado adicional altera la máquina y la interfaz, no la persistencia |
| Congelar corresponde al Líder de Estudio y al Administrador | `R-09` | Cambiar el perfil autorizado es una constante |
| El identificador de Comité de Precios sigue el formato `CP-AAAA-NN` | `R-18` | Ajustar la validación; sin efecto estructural |
| Los respaldos se referencian por ruta y huella, no se embeben | `R-45` | Embeberlos aumentaría el tamaño de la imagen sin beneficio |

Ninguno de los cuatro afecta la capa de persistencia. La decisión estructural —tres ejes de
versionado, congelamiento irreversible, bitácora encadenada— es la que no admite ajuste barato, y es
la que este documento fija.
