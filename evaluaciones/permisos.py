from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from cuentas.models import Usuario


def solo_pacientes(vista):
    @wraps(vista)
    @login_required
    def envoltura(request, *args, **kwargs):
        if request.user.rol != Usuario.Rol.PACIENTE:
            raise PermissionDenied
        return vista(request, *args, **kwargs)

    return envoltura
