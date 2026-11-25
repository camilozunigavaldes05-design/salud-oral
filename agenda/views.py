from itertools import groupby

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from cuentas.models import Profesional, Usuario
from cuentas.permisos import profesional_verificado, requiere_rol

from .forms import CancelarCitaForm, HorarioForm, ReprogramarCitaForm
from .models import BloqueoTemporal, Cita, Horario
from .servicios import (
    ESTADOS_VIGENTES,
    AgendaError,
    bloquear_horario,
    cancelar_cita,
    confirmar_cita,
    confirmar_solicitud,
    crear_horarios,
    eliminar_horario,
    horarios_disponibles,
    liberar_bloqueo,
    profesionales_disponibles,
    puede_ver_historial,
    reprogramar_cita,
)

solo_pacientes = requiere_rol(Usuario.Rol.PACIENTE)


def _por_dia(horarios):
    return [
        (dia, list(grupo))
        for dia, grupo in groupby(horarios, key=lambda h: timezone.localtime(h.inicio).date())
    ]


@solo_pacientes
def directorio(request):
    return render(
        request,
        "agenda/directorio.html",
        {"profesionales": profesionales_disponibles()},
    )


@solo_pacientes
def horarios_profesional(request, pk):
    profesional = get_object_or_404(
        Profesional.objects.select_related("usuario"),
        pk=pk,
        verificado=True,
        usuario__estado=Usuario.Estado.ACTIVA,
    )
    return render(
        request,
        "agenda/horarios_profesional.html",
        {"profesional": profesional, "dias": _por_dia(horarios_disponibles(profesional))},
    )


@require_POST
@solo_pacientes
def reservar(request, pk):
    horario = get_object_or_404(Horario, pk=pk)
    try:
        bloqueo = bloquear_horario(request.user, horario.pk)
    except AgendaError as error:
        messages.error(request, str(error))
        return redirect("agenda:horarios_profesional", pk=horario.profesional_id)
    return redirect("agenda:resumen", pk=bloqueo.pk)


@solo_pacientes
def resumen(request, pk):
    bloqueo = get_object_or_404(
        BloqueoTemporal.objects.select_related("horario__profesional__usuario"),
        pk=pk,
        paciente=request.user,
    )
    if request.method == "POST":
        try:
            cita = confirmar_solicitud(bloqueo)
        except AgendaError as error:
            messages.error(request, str(error))
            return redirect("agenda:horarios_profesional", pk=bloqueo.horario.profesional_id)
        messages.success(
            request,
            "Tu solicitud fue enviada. Te avisaremos cuando el profesional la confirme.",
        )
        return redirect("agenda:mis_citas")

    vigente = (
        bloqueo.estado == BloqueoTemporal.Estado.VIGENTE and bloqueo.expira_en > timezone.now()
    )
    if not vigente:
        messages.error(
            request,
            "Pasaron más de 15 minutos y el horario se liberó. Vuelve a elegir un horario.",
        )
        return redirect("agenda:horarios_profesional", pk=bloqueo.horario.profesional_id)
    segundos = int((bloqueo.expira_en - timezone.now()).total_seconds())
    return render(request, "agenda/resumen.html", {"bloqueo": bloqueo, "segundos": segundos})


@require_POST
@solo_pacientes
def soltar(request, pk):
    bloqueo = get_object_or_404(BloqueoTemporal, pk=pk, paciente=request.user)
    liberar_bloqueo(bloqueo)
    messages.info(request, "Liberaste el horario.")
    return redirect("agenda:horarios_profesional", pk=bloqueo.horario.profesional_id)


@solo_pacientes
def mis_citas(request):
    citas = Cita.objects.filter(paciente=request.user).select_related(
        "horario__profesional__usuario"
    ).order_by("-horario__inicio")
    return render(request, "agenda/mis_citas.html", {"citas": citas})


@profesional_verificado
def mis_horarios(request):
    profesional = request.user.profesional
    form = HorarioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            creados = crear_horarios(profesional, form.bloques)
        except AgendaError as error:
            form.add_error(None, str(error))
        else:
            cantidad = len(creados)
            messages.success(
                request,
                "Se publicó 1 bloque." if cantidad == 1 else f"Se publicaron {cantidad} bloques.",
            )
            return redirect("agenda:mis_horarios")

    horarios = (
        Horario.objects.filter(profesional=profesional, fin__gt=timezone.now())
        .prefetch_related("citas__paciente")
        .order_by("inicio")
    )
    for horario in horarios:
        horario.cita_vigente = next(
            (cita for cita in horario.citas.all() if cita.estado in ESTADOS_VIGENTES),
            None,
        )
    return render(
        request,
        "agenda/mis_horarios.html",
        {"form": form, "dias": _por_dia(horarios)},
    )


@require_POST
@profesional_verificado
def borrar_horario(request, pk):
    horario = get_object_or_404(Horario, pk=pk, profesional=request.user.profesional)
    try:
        eliminar_horario(horario, request.user)
    except AgendaError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "El bloque fue eliminado.")
    return redirect("agenda:mis_horarios")


@profesional_verificado
def citas_profesional(request):
    citas = Cita.objects.filter(horario__profesional=request.user.profesional).select_related(
        "paciente", "horario"
    )
    ver = request.GET.get("ver", "proximas")
    if ver == "todas":
        citas = citas.order_by("-horario__inicio")
    else:
        citas = citas.filter(
            estado__in=ESTADOS_VIGENTES,
            horario__fin__gte=timezone.now(),
        ).order_by("horario__inicio")
    return render(request, "agenda/citas_profesional.html", {"citas": citas, "ver": ver})


def _cita_del_profesional(request, pk):
    return get_object_or_404(
        Cita.objects.select_related("paciente", "horario__profesional__usuario"),
        pk=pk,
        horario__profesional=request.user.profesional,
    )


@profesional_verificado
def detalle_cita(request, pk):
    cita = _cita_del_profesional(request, pk)
    return render(
        request,
        "agenda/detalle_cita.html",
        {
            "cita": cita,
            "cancelar_form": CancelarCitaForm(),
            "reprogramar_form": ReprogramarCitaForm(
                horarios=horarios_disponibles(request.user.profesional)
            ),
            "ver_historial": puede_ver_historial(request.user, cita.paciente),
        },
    )


@require_POST
@profesional_verificado
def accion_cita(request, pk, accion):
    if accion not in ("confirmar", "reprogramar", "cancelar"):
        raise Http404
    cita = _cita_del_profesional(request, pk)
    profesional = request.user.profesional
    try:
        if accion == "confirmar":
            confirmar_cita(cita, profesional)
            messages.success(request, "La cita fue confirmada y se avisó al paciente.")
        elif accion == "reprogramar":
            form = ReprogramarCitaForm(
                request.POST,
                horarios=horarios_disponibles(profesional),
            )
            if not form.is_valid():
                raise AgendaError("El nuevo bloque no está disponible. Elige otro bloque de tu agenda.")
            reprogramar_cita(cita, profesional, int(form.cleaned_data["nuevo_horario"]))
            messages.success(request, "La cita fue reprogramada y se avisó al paciente.")
        elif accion == "cancelar":
            form = CancelarCitaForm(request.POST)
            if not form.is_valid():
                raise AgendaError("Escribe el motivo de la cancelación.")
            cancelar_cita(cita, profesional, form.cleaned_data["motivo"])
            messages.success(request, "La cita fue cancelada y el bloque quedó disponible.")
    except AgendaError as error:
        messages.error(request, str(error))
    return redirect("agenda:detalle_cita", pk=cita.pk)
