// Lo que jsdom no implementa y el navegador si.
//
// jsdom no tiene modelo de scroll: `Element.prototype.scrollIntoView` no
// existe, y llamarlo revienta con un `TypeError` que vitest reporta como error
// no controlado. Las pruebas pasan y el proceso termina en 1 igual, de modo que
// la puerta falla sin una sola asercion rota.
//
// El sustituto no hace nada a proposito. Que una pestaña quede a la vista al
// avanzar con las flechas es comportamiento de navegador y se verifica en el
// navegador; guardarlo en el componente seria adaptar el codigo de produccion a
// una limitacion del entorno de prueba.

Element.prototype.scrollIntoView = function scrollIntoView() {
  return undefined;
};
