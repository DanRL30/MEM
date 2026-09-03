# Activos de marca

Logotipos de MINSUR que la interfaz usa. Es material de identidad del cliente,
no un activo intercambiable: se sustituye por el archivo que MINSUR entregue,
nunca por uno recuperado de una web o exportado de una captura.

## Qué va aquí

| Archivo | Uso | Estado |
|---|---|---|
| `minsur-horizontal-color.svg` | Cabecera de la aplicación, sobre superficie clara | **Pendiente de colocar** |
| `minsur-horizontal-blanco.svg` | Sobre fondo oscuro o imagen | Opcional |

Vectorial y no mapa de bits: la cabecera lo dibuja a distintas alturas según el
ancho de pantalla, y un PNG se ve blando en pantallas de densidad alta. Si solo
existe en PNG, sirve, pero anótalo abajo con su resolución.

## Cómo lo toma la interfaz

`Encabezado.tsx` no importa el archivo por su ruta: recoge lo que haya en esta
carpeta. Colocar el SVG con el nombre de la tabla es todo lo que hace falta, sin
tocar una línea de código. Mientras no esté, la cabecera dibuja el nombre del
servicio en tipografía corporativa y la aplicación funciona igual.

La política de seguridad de contenido declara `img-src 'self' data:`, de modo
que el archivo tiene que vivir aquí y servirse desde el propio origen. Un
logotipo enlazado desde un CDN no carga, y no deja error visible.

## Procedencia y autorización de uso

| Archivo | Origen | Entrega | Autorización |
|---|---|---|---|
| | | | |

Rellena la fila **en el mismo commit** en el que entra el archivo, con la misma
disciplina que [las tipografías](../fuentes/LEEME.md): de quién viene, cuándo se
recibió y con qué autorización se usa.

Contexto que conviene tener presente al rellenarla: el paquete de identidad
visual que circuló el 24/08/2026 era una reconstrucción propia y **se eliminó
el 31/08/2026**, logotipos incluidos. Lo que MINSUR sí entregó es el manual de
marca del 26/08/2026 y un logotipo horizontal a color. El archivo que entre aquí
tiene que venir de esa entrega, y de ninguna otra parte.

## Al reemplazar un archivo

1. Parte del original que MINSUR entregó, no de una versión ya optimizada: cada
   conversión encadenada pierde precisión del trazado.
2. No recolorees ni recompongas el logotipo. El manual fija sus versiones, sus
   márgenes de respeto y sus usos prohibidos.
3. Actualiza la tabla de procedencia en el mismo commit.
