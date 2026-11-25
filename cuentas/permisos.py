from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import Usuario


def requiere_rol(rol):
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            if request.user.rol != rol:
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


def profesional_verificado(vista):
    @wraps(vista)
    @requiere_rol(Usuario.Rol.PROFESIONAL)
    def envoltura(request, *args, **kwargs):
        perfil = getattr(request.user, "profesional", None)
        if perfil is None or not perfil.verificado:
            messages.error(
                request,
                "Tu perfil profesional aún no ha sido verificado por un administrador.",
            )
            return redirect("cuentas:inicio")
        return vista(request, *args, **kwargs)

    return envoltura
