/* Cuenta regresiva del bloqueo temporal de una hora.
   Sin este archivo el servidor igual libera la hora al vencer el plazo. */
(function () {
  "use strict";

  var contador = document.getElementById("contador");
  var boton = document.getElementById("boton-confirmar");
  if (!contador || !boton) return;

  var restante = parseInt(contador.dataset.segundos, 10);
  if (isNaN(restante)) return;

  function mostrar() {
    if (restante <= 0) {
      contador.textContent = "0:00";
      boton.disabled = true;
      boton.textContent = "El tiempo terminó: elige otra hora";
      return;
    }
    var minutos = Math.floor(restante / 60);
    var segundos = restante % 60;
    contador.textContent = minutos + ":" + (segundos < 10 ? "0" : "") + segundos;
    restante -= 1;
    window.setTimeout(mostrar, 1000);
  }
  mostrar();
})();
