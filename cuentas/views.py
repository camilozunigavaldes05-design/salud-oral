from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from administracion.auditoria import registrar
from administracion.servicios import avisar_nuevo_profesional

from .autenticacion import verificar_credenciales
from .forms import (
    FichaClinicaForm,
    InicioSesionForm,
    RegistroPacienteForm,
    RegistroProfesionalForm,
)
from .models import FichaClinica, Usuario

PLANTILLAS_INICIO = {
    Usuario.Rol.PACIENTE: "cuentas/inicio_paciente.html",
    Usuario.Rol.PROFESIONAL: "cuentas/inicio_profesional.html",
    Usuario.Rol.ADMINISTRADOR: "cuentas/inicio_administrador.html",
}


def bienvenida(request):
    """La raiz del sitio nunca muestra contenido: lleva al login o al panel."""
    if request.user.is_authenticated:
        return redirect("cuentas:inicio")
    return redirect("cuentas:login")


def iniciar_sesion(request):
    if request.user.is_authenticated:
        return redirect("cuentas:inicio")

    # Solo cambia el mensaje lateral y el enlace de registro.
    # La autenticacion es identica: el rol lo define la cuenta, no esta pestana.
    tipo = request.GET.get("tipo", "paciente")
    if tipo not in ("paciente", "profesional"):
        tipo = "paciente"

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
        {"form": form, "next": request.GET.get("next", ""), "tipo": tipo},
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
    return render(request, plantilla, _datos_del_panel(request.user))


def _datos_del_panel(usuario):
    """Resumen que alimenta el panel de cada rol. Solo lecturas.

    Las importaciones van dentro para no crear un ciclo:
    agenda.models ya importa cuentas.models.
    """
    from agenda.models import Cita, Horario
    from agenda.servicios import ESTADOS_VIGENTES, puede_ver_historial
    from evaluaciones.models import Evaluacion

    ahora = timezone.now()

    if usuario.rol == Usuario.Rol.PACIENTE:
        evaluaciones = Evaluacion.objects.filter(paciente=usuario)
        citas = Cita.objects.filter(paciente=usuario).select_related(
            "horario__profesional__usuario"
        )
        proxima = citas.filter(
            estado__in=ESTADOS_VIGENTES, horario__inicio__gte=ahora
        ).order_by("horario__inicio").first()
        return {
            "hoy": timezone.localdate(),
            "ultima_evaluacion": evaluaciones.first(),
            "total_evaluaciones": evaluaciones.count(),
            "proxima_cita": proxima,
            "profesional_de_turno": proxima.horario.profesional if proxima else None,
            # Columna derecha: lo que el paciente declara para su profesional.
            "ficha": FichaClinica.objects.filter(paciente=usuario).first(),
        }

    if usuario.rol == Usuario.Rol.PROFESIONAL:
        profesional = getattr(usuario, "profesional", None)
        if profesional is None:
            return {}
        citas = Cita.objects.filter(horario__profesional=profesional).select_related(
            "paciente", "horario"
        )
        vigentes = citas.filter(estado__in=ESTADOS_VIGENTES, horario__fin__gte=ahora)
        proxima = vigentes.order_by("horario__inicio").first()

        # Columna derecha: el paciente de la proxima cita.
        # El acceso al historial lo decide agenda.servicios, no esta vista.
        paciente = proxima.paciente if proxima else None
        evaluacion_del_paciente = None
        ficha_del_paciente = None
        acceso = bool(paciente) and puede_ver_historial(usuario, paciente)
        if acceso:
            evaluacion_del_paciente = Evaluacion.objects.filter(
                paciente=paciente,
                estado=Evaluacion.Estado.REPORTE_DISPONIBLE,
            ).first()
            # La ficha sigue la misma regla que el historial: sin cita vigente, no se ve.
            ficha_del_paciente = FichaClinica.objects.filter(paciente=paciente).first()

        return {
            "hoy": timezone.localdate(),
            "profesional": profesional,
            "por_confirmar": citas.filter(
                estado=Cita.Estado.PENDIENTE_CONFIRMACION, horario__fin__gte=ahora
            ).count(),
            "citas_proximas": vigentes.count(),
            "proxima_cita": proxima,
            "horas_libres": Horario.objects.filter(
                profesional=profesional,
                estado=Horario.Estado.DISPONIBLE,
                inicio__gte=ahora,
            ).count(),
            "paciente_de_turno": paciente,
            "evaluacion_del_paciente": evaluacion_del_paciente,
            "ficha_del_paciente": ficha_del_paciente,
            "puede_ver_historial": acceso,
        }

    return {}


@login_required
def mi_ficha(request):
    """El paciente declara sus datos. Nadie mas los edita."""
    if request.user.rol != Usuario.Rol.PACIENTE:
        return redirect("cuentas:inicio")

    ficha, _ = FichaClinica.objects.get_or_create(paciente=request.user)
    form = FichaClinicaForm(request.POST or None, instance=ficha)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tus datos quedaron guardados.")
        return redirect("cuentas:inicio")

    return render(request, "cuentas/mi_ficha.html", {"form": form})


@require_POST
def cerrar_sesion(request):
    registrar(request.user if request.user.is_authenticated else None, "CIERRE_SESION", "cuenta")
    logout(request)
    messages.info(request, "Cerraste sesión correctamente.")
    return redirect("cuentas:login")
