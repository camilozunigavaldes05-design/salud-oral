from .models import Notificacion


def avisos(request):
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {}
    return {
        "avisos_sin_leer": Notificacion.objects.filter(
            destinatario=usuario,
            canal=Notificacion.Canal.INTERNA,
            leida_en__isnull=True,
        ).count()
    }
