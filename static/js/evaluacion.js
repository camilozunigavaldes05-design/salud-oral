/* Vista previa de la foto y estado de espera mientras corre el modelo.
   Sin este archivo el formulario funciona igual: solo se pierde el aviso. */
(function () {
  "use strict";

  var formulario = document.querySelector("[data-formulario-evaluacion]");
  if (!formulario) return;

  var entrada = formulario.querySelector('input[type="file"]');
  var vista = document.getElementById("vista-previa");
  var boton = document.getElementById("boton-enviar");
  var analizando = document.getElementById("analizando");

  if (entrada && vista) {
    entrada.addEventListener("change", function () {
      var archivo = entrada.files && entrada.files[0];
      if (!archivo) {
        vista.hidden = true;
        return;
      }
      vista.querySelector("img").src = URL.createObjectURL(archivo);
      vista.hidden = false;
    });
  }

  formulario.addEventListener("submit", function () {
    if (boton) {
      boton.disabled = true;
      boton.textContent = "Analizando la fotografía…";
    }
    if (analizando) {
      // El formulario se va y queda el aviso: el paciente ve que algo ocurre.
      formulario.hidden = true;
      analizando.hidden = false;
    }
  });
})();
