# Tipografias de la plataforma

Procedencia y situacion de licencia de cada archivo. Los originales entregados
por MINSUR estan fuera de este repositorio, en la biblioteca de gestion del
servicio; aqui viven solo las conversiones a WOFF2 que la interfaz sirve.

| Archivo | Familia | Fundicion | Licencia |
|---|---|---|---|
| `Rationell-Light.woff2` | Rationell | PeGGO Fonts | Adquirida por MINSUR |
| `Rationell-Regular.woff2` | Rationell | PeGGO Fonts | Adquirida por MINSUR |
| `Rationell-Bold.woff2` | Rationell | PeGGO Fonts | Adquirida por MINSUR |
| `Rationell-ExtraBold.woff2` | Rationell | PeGGO Fonts | Adquirida por MINSUR |
| `Bagiora-Medium.woff2` | Bagiora | Casloop Studio | Adquirida por MINSUR |
| `NataSansVF.woff2` | Nata Sans | Daniel Uzquiano | SIL Open Font License 1.1 |

## Rationell y Bagiora

Tipografias comerciales, propiedad de sus fundiciones y licenciadas por MINSUR.
Los archivos OTF originales los entrego MINSUR el 31/08/2026 junto con el
comprobante de compra a traves de Monotype, pedido 1270.

Verificacion realizada sobre los archivos entregados:

- Nombre de familia `Rationell`, version 4.060, sin el prefijo de demostracion.
- 944 caracteres por peso, con castellano completo: vocales acentuadas, ene,
  dieresis y signos de apertura.
- `fsType` en 0x0000, que es la declaracion del fabricante de que la fuente
  admite incrustacion sin restriccion tecnica.
- Bagiora Medium, de Casloop Studio, 563 caracteres, castellano completo.

Los WOFF2 de esta carpeta se generaron con `fontTools` a partir de esos OTF, sin
alterar el juego de caracteres ni las tablas de la fuente. La conversion cambia
el contenedor, no el diseno.

**Se usan por instruccion de MINSUR, propietario de las licencias y de la
plataforma.** El expediente del servicio registra la trazabilidad de esa
instruccion en la restriccion `R-61`.

## Nata Sans

Tipografia de soporte que el Manual de Marca Minsur designa para cuando
Rationell no esta disponible. Se distribuye bajo SIL Open Font License 1.1, que
autoriza uso comercial, incrustacion, modificacion y redistribucion.

Su licencia acompana al archivo en `LICENSE-nata-sans.txt`, como exige la
clausula 2 de la OFL. **No retires ese archivo**: sin el, la redistribucion
incumple la licencia.

La interfaz la declara como segunda familia de la pila. El navegador solo la
descarga si Rationell no resuelve, de modo que su presencia no cuesta
transferencia en el caso normal.

## Al reemplazar un archivo

Regenerar el WOFF2 desde el OTF original de la biblioteca de gestion, no desde
otro WOFF2: cada conversion en cadena es una oportunidad de perder tablas de la
fuente. Y actualizar la tabla de arriba, que es lo que permite a quien reciba el
repositorio saber que puede y que no puede hacer con cada archivo.
