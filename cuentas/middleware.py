from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from .models import Usuario


class CerrarSesionCuentaSuspendida:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario is not None and usuario.is_authenticated and usuario.estado == Usuario.Estado.SUSPENDIDA:
            logout(request)
            messages.error(request, "Tu cuenta está suspendida. Contacta al administrador.")
            return redirect("cuentas:login")
        return self.get_response(request)
