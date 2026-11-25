from datetime import datetime, time, timedelta

from django.contrib import messages
from django.http import Http404
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from cuentas.models import Profesional, Usuario
from cuentas.permisos import requiere_rol

from .forms import FiltroAuditoriaForm, FiltroUsuariosForm
from .models import Auditoria
from .servicios import (
    AdministracionError,
    cambiar_estado_cuenta,
    rechazar_profesional,
    verificar_profesional,
)

solo_administradores = requiere_rol(Usuario.Rol.ADMINISTRADOR)


@solo_administradores
def profesionales(request):
    pendientes = (
        Profesional.objects.filter(verificado=False)
        .exclude(usuario__estado=Usuario.Estado.SUSPENDIDA)
        .select_related("usuario")
        .order_by("usuario__date_joined")
    )
    verificados = (
        Profesional.objects.filter(verificado=True)
        .select_related("usuario")
        .order_by("usuario__last_name")
    )
    return render(
        request,
        "administracion/profesionales.html",
        {"pendientes": pendientes, "verificados": verificados},
    )


@require_POST
@solo_administradores
def decidir_profesional(request, pk, decision):
    if decision not in ("verificar", "rechazar"):
        raise Http404
    profesional = get_object_or_404(Profesional.objects.select_related("usuario"), pk=pk)
    if decision == "verificar":
        verificar_profesional(request.user, profesional)
        messages.success(request, f"{profesional.usuario.email} fue verificado y ya aparece en el directorio.")
    else:
        rechazar_profesional(request.user, profesional)
        messages.info(request, f"Se rechazó el registro de {profesional.usuario.email}.")
    return redirect("administracion:profesionales")


@solo_administradores
def usuarios(request):
    form = FiltroUsuariosForm(request.GET or None)
    lista = Usuario.objects.order_by("last_name", "first_name")
    if form.is_valid():
        if form.cleaned_data["buscar"]:
            texto = form.cleaned_data["buscar"]
            lista = lista.filter(
                Q(email__icontains=texto) | Q(first_name__icontains=texto) | Q(last_name__icontains=texto)
            )
        if form.cleaned_data["rol"]:
            lista = lista.filter(rol=form.cleaned_data["rol"])
        if form.cleaned_data["estado"]:
            lista = lista.filter(estado=form.cleaned_data["estado"])
    pagina = Paginator(lista, 25).get_page(request.GET.get("pagina"))
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    return render(
        request,
        "administracion/usuarios.html",
        {"form": form, "pagina": pagina, "parametros": parametros.urlencode()},
    )


@require_POST
@solo_administradores
def estado_usuario(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    activar = request.POST.get("estado") == "activar"
    try:
        cambiar_estado_cuenta(request.user, usuario, activar)
    except AdministracionError as error:
        messages.error(request, str(error))
    else:
        messages.success(
            request,
            f"La cuenta de {usuario.email} fue {'reactivada' if activar else 'suspendida'}.",
        )
    volver = request.POST.get("volver", "")
    if not url_has_allowed_host_and_scheme(volver, {request.get_host()}):
        volver = ""
    return redirect(volver or "administracion:usuarios")


@solo_administradores
def auditoria(request):
    acciones = Auditoria.objects.order_by("accion").values_list("accion", flat=True).distinct()
    form = FiltroAuditoriaForm(request.GET or None, acciones=acciones)
    registros = Auditoria.objects.select_related("usuario")
    if form.is_valid():
        datos = form.cleaned_data
        if datos["usuario"]:
            registros = registros.filter(usuario__email__icontains=datos["usuario"])
        if datos["accion"]:
            registros = registros.filter(accion=datos["accion"])
        if datos["desde"]:
            registros = registros.filter(fecha__gte=timezone.make_aware(datetime.combine(datos["desde"], time.min)))
        if datos["hasta"]:
            limite = timezone.make_aware(datetime.combine(datos["hasta"] + timedelta(days=1), time.min))
            registros = registros.filter(fecha__lt=limite)
    pagina = Paginator(registros, 50).get_page(request.GET.get("pagina"))
    parametros = request.GET.copy()
    parametros.pop("pagina", None)
    return render(
        request,
        "administracion/auditoria.html",
        {"form": form, "pagina": pagina, "parametros": parametros.urlencode()},
    )
