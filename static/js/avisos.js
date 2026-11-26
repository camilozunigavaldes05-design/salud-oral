/* Centro de notificaciones del encabezado.
   Sin este archivo la campana sigue siendo un enlace a la lista completa. */
(function () {
  "use strict";

  var centro = document.querySelector("[data-centro-avisos]");
  if (!centro) return;

  var disparador = centro.querySelector("[data-disparador]");
  var panel = centro.querySelector("[data-panel]");
  if (!disparador || !panel) return;

  // Con JavaScript el enlace pasa a ser un boton que despliega.
  disparador.setAttribute("role", "button");

  var abierto = false;

  function abrir() {
    if (abierto) return;
    abierto = true;
    panel.hidden = false;
    // Un cuadro en el siguiente fotograma para que la transicion corra.
    requestAnimationFrame(function () {
      panel.classList.add("abierto");
    });
    disparador.setAttribute("aria-expanded", "true");
    document.addEventListener("click", alClicFuera, true);
    document.addEventListener("keydown", alPresionarTecla);
  }

  function cerrar(devolverFoco) {
    if (!abierto) return;
    abierto = false;
    panel.classList.remove("abierto");
    disparador.setAttribute("aria-expanded", "false");
    document.removeEventListener("click", alClicFuera, true);
    document.removeEventListener("keydown", alPresionarTecla);

    var ocultar = function () {
      if (!abierto) panel.hidden = true;
    };
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      ocultar();
    } else {
      window.setTimeout(ocultar, 300);
    }

    if (devolverFoco) disparador.focus();
  }

  function alClicFuera(evento) {
    if (!centro.contains(evento.target)) cerrar(false);
  }

  function alPresionarTecla(evento) {
    if (evento.key === "Escape") {
      evento.preventDefault();
      cerrar(true);
    }
  }

  disparador.addEventListener("click", function (evento) {
    evento.preventDefault();
    if (abierto) {
      cerrar(true);
    } else {
      abrir();
    }
  });

  disparador.addEventListener("keydown", function (evento) {
    if (evento.key === "Enter" || evento.key === " ") {
      evento.preventDefault();
      if (!abierto) {
        abrir();
        var primero = panel.querySelector("a");
        if (primero) primero.focus();
      }
    }
  });
})();
