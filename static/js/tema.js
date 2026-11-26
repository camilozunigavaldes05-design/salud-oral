/* Selector de tema: automático, claro u oscuro.
   Sin este archivo la aplicación sigue el tema del sistema, que es el
   comportamiento por defecto y el correcto. */
(function () {
  "use strict";

  var CLAVE = "salud-oral-tema";
  var raiz = document.documentElement;

  function aplicar(valor) {
    if (valor === "auto") {
      raiz.removeAttribute("data-tema");
    } else {
      raiz.setAttribute("data-tema", valor);
    }
  }

  function guardado() {
    try {
      return window.localStorage.getItem(CLAVE) || "auto";
    } catch (e) {
      return "auto";  // modo privado o almacenamiento bloqueado
    }
  }

  // Se aplica cuanto antes para no mostrar un parpadeo del tema contrario.
  aplicar(guardado());

  document.addEventListener("DOMContentLoaded", function () {
    var grupo = document.querySelector("[data-tema-selector]");
    if (!grupo) return;
    grupo.hidden = false;

    function marcar(valor) {
      grupo.querySelectorAll("button[data-valor]").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b.dataset.valor === valor));
      });
    }
    marcar(guardado());

    grupo.addEventListener("click", function (evento) {
      var boton = evento.target.closest("button[data-valor]");
      if (!boton) return;
      var valor = boton.dataset.valor;
      aplicar(valor);
      marcar(valor);
      try {
        window.localStorage.setItem(CLAVE, valor);
      } catch (e) {
        /* sin almacenamiento: el cambio dura solo esta visita */
      }
    });
  });
})();
