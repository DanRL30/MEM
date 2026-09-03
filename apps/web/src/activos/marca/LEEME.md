# Activos de marca

Logotipos de MINSUR que la interfaz usa. Es material de identidad del cliente,
no un activo intercambiable: se sustituye por el archivo que MINSUR entregue,
nunca por uno recuperado de una web o exportado de una captura.

## Qué va aquí

| Archivo | Uso | Estado |
|---|---|---|
| `minsur-horizontal-color.png` | Cabecera de la aplicación, sobre superficie clara | **Colocado** |
| `minsur-horizontal-blanco.*` | Sobre fondo oscuro o imagen | No entregado |

Preferible en vectorial. El archivo que hay es un PNG de 820 × 208 con canal
alfa, que a la altura de la cabecera —28 px— tiene resolución de sobra: la
fuente es siete veces más alta de lo que se dibuja. La conveniencia del SVG
llegaría el día que el logotipo se use en grande, en una portada o un reporte
impreso; para la interfaz, este archivo basta.

## Cómo lo toma la interfaz

`Encabezado.tsx` no importa el archivo por su ruta: recoge lo que haya en esta
carpeta, en SVG, PNG o WEBP. Colocarlo con el nombre de la tabla es todo lo que
hace falta, sin tocar una línea de código. Si algún día conviven la versión a
color y una en blanco, la cabecera elige la de color: la otra quedaría invisible
sobre el vidrio. Mientras no haya ninguna, dibuja el nombre del servicio en
tipografía corporativa y la aplicación funciona igual.

La política de seguridad de contenido declara `img-src 'self' data:`, de modo
que el archivo tiene que vivir aquí y servirse desde el propio origen. Un
logotipo enlazado desde un CDN no carga, y no deja error visible.

## Procedencia y autorización de uso

| Archivo | Origen | Entrega | Autorización |
|---|---|---|---|
| `minsur-horizontal-color.png` | MINSUR, logotipo horizontal a color | 03/09/2026 | Uso en la plataforma del servicio INVA-01-2026-182 |

Identidad del archivo, para poder afirmar después que es el que se recibió:

- Nombre con el que llegó: `Minsur_idgzuysS7o_0.png`, renombrado al entrar para
  que la carpeta se lea sola. Su procedencia la fija esta tabla, no su nombre.
- 820 × 208, RGBA con transparencia real, 14 242 bytes.
- SHA-256 `f6c340959a1a3dbcdf25f339f20c65cfa67ff55304806c4ea693608dd7c77794`.

Composición: el símbolo en gris claro y la palabra MINSUR en el azul
corporativo, sobre fondo transparente. Es la versión para superficie clara.

**Falta la autorización de uso por escrito.** El logotipo se usa en la
plataforma que INVA construye para MINSUR, de modo que el uso es el previsto;
pero el registro de identidad visual quedó en revisión tras retirarse el paquete
del 24/08/2026, y esta fila debe confirmarse con la misma formalidad que la de
[las tipografías](../fuentes/LEEME.md), que citan su comprobante de licencia.

Contexto que conviene tener presente al rellenarla: el paquete de identidad
visual que circuló el 24/08/2026 era una reconstrucción propia y **se eliminó
el 31/08/2026**, logotipos incluidos. Lo que MINSUR sí entregó es el manual de
marca del 26/08/2026 y un logotipo horizontal a color. El archivo que entre aquí
tiene que venir de esa entrega, y de ninguna otra parte.

## Al reemplazar un archivo

1. Parte del original que MINSUR entregó, no de una versión ya optimizada: cada
   conversión encadenada pierde precisión del trazado, y un PNG reescalado desde
   otro PNG pierde además definición sin avisar.
2. No recolorees ni recompongas el logotipo. El manual fija sus versiones, sus
   márgenes de respeto y sus usos prohibidos.
3. Actualiza la tabla de procedencia en el mismo commit.
