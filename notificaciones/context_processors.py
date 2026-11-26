from .models import Notificacion

# Cuantos avisos muestra el panel desplegable del encabezado.
AVISOS_EN_PANEL = 5


def avisos(request):
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {}

    internos = Notificacion.objects.filter(
        destinatario=usuario,
        canal=Notificacion.Canal.INTERNA,
    )
    return {
        "avisos_sin_leer": internos.filter(leida_en__isnull=True).count(),
        # El panel del encabezado muestra los ultimos, leidos o no.
        "avisos_recientes": internos.order_by("-creada_en")[:AVISOS_EN_PANEL],
    }
