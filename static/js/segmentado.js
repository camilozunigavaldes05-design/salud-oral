/* Control segmentado del login.
   Sin este archivo los enlaces siguen funcionando: recargan la pagina
   con ?tipo=... y el servidor arma el estado correcto. Con el archivo,
   el cambio ocurre en el sitio y se anima. */
(function () {
  "use strict";

  var grupo = document.querySelector("[data-segmentado]");
  if (!grupo) return;

  function activar(valor, href) {
    if (grupo.dataset.tipo === valor) return;

    grupo.dataset.tipo = valor;

    grupo.querySelectorAll("a[data-valor]").forEach(function (enlace) {
      enlace.setAttribute("aria-selected", String(enlace.dataset.valor === valor));
    });

    document.querySelectorAll("[data-variante]").forEach(function (bloque) {
      bloque.classList.toggle("activa", bloque.dataset.variante === valor);
    });

    if (href && window.history && window.history.replaceState) {
      window.history.replaceState(null, "", href);
    }
  }

  grupo.addEventListener("click", function (evento) {
    var enlace = evento.target.closest("a[data-valor]");
    if (!enlace) return;
    evento.preventDefault();
    activar(enlace.dataset.valor, enlace.getAttribute("href"));
  });

  // Flechas izquierda y derecha, como espera un grupo de pestanas.
  grupo.addEventListener("keydown", function (evento) {
    if (evento.key !== "ArrowLeft" && evento.key !== "ArrowRight") return;
    var enlaces = Array.prototype.slice.call(grupo.querySelectorAll("a[data-valor]"));
    var actual = enlaces.findIndex(function (e) {
      return e.getAttribute("aria-selected") === "true";
    });
    var siguiente = evento.key === "ArrowRight"
      ? (actual + 1) % enlaces.length
      : (actual - 1 + enlaces.length) % enlaces.length;
    evento.preventDefault();
    activar(enlaces[siguiente].dataset.valor, enlaces[siguiente].getAttribute("href"));
    enlaces[siguiente].focus();
  });
})();
