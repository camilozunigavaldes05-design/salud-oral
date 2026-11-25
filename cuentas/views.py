from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from administracion.auditoria import registrar
from administracion.servicios import avisar_nuevo_profesional

from .autenticacion import verificar_credenciales
from .forms import InicioSesionForm, RegistroPacienteForm, RegistroProfesionalForm
from .models import Usuario

PLANTILLAS_INICIO = {
    Usuario.Rol.PACIENTE: "cuentas/inicio_paciente.html",
    Usuario.Rol.PROFESIONAL: "cuentas/inicio_profesional.html",
    Usuario.Rol.ADMINISTRADOR: "cuentas/inicio_administrador.html",
}


def bienvenida(request):
    if request.user.is_authenticated:
        return redirect("cuentas:inicio")
    return render(request, "cuentas/bienvenida.html")


def iniciar_sesion(request):
    if request.user.is_authenticated:
        return redirect("cuentas:inicio")

    form = InicioSesionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario, error = verificar_credenciales(
            request,
            form.cleaned_data["email"],
            form.cleaned_data["password"],
        )
        if usuario:
            login(request, usuario)
            siguiente = request.POST.get("next") or request.GET.get("next")
            if siguiente and url_has_allowed_host_and_scheme(siguiente, {request.get_host()}):
                return redirect(siguiente)
            return redirect("cuentas:inicio")
        form.add_error(None, error)

    return render(
        request,
        "cuentas/login.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


def registro_paciente(request):
    if request.user.is_authenticated:
        return redirect("cuentas:inicio")

    form = RegistroPacienteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        registrar(usuario, "REGISTRO", "cuenta")
        login(request, usuario)
        messages.success(request, "¡Tu cuenta fue creada con éxito!")
        return redirect("cuentas:inicio")

    return render(request, "cuentas/registro_paciente.html", {"form": form})


def registro_profesional(request):
    if request.user.is_authenticated:
        return redirect("cuentas:inicio")

    form = RegistroProfesionalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        registrar(usuario, "REGISTRO", "cuenta")
        avisar_nuevo_profesional(usuario.profesional)
        messages.info(
            request,
            "Tu cuenta fue creada y quedó pendiente de verificación. "
            "Podrás ingresar cuando un administrador la apruebe.",
        )
        return redirect("cuentas:login")

    return render(request, "cuentas/registro_profesional.html", {"form": form})


@login_required
def inicio(request):
    plantilla = PLANTILLAS_INICIO.get(request.user.rol, "cuentas/inicio_paciente.html")
    return render(request, plantilla)


@require_POST
def cerrar_sesion(request):
    registrar(request.user if request.user.is_authenticated else None, "CIERRE_SESION", "cuenta")
    logout(request)
    messages.info(request, "Cerraste sesión correctamente.")
    return redirect("cuentas:bienvenida")
