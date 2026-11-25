from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone

from .models import Notificacion


@login_required
def lista(request):
    avisos = Notificacion.objects.filter(
        destinatario=request.user,
        canal=Notificacion.Canal.INTERNA,
    ).select_related("cita")
    pagina = Paginator(avisos, 20).get_page(request.GET.get("pagina"))
    sin_leer = [aviso.pk for aviso in pagina if aviso.leida_en is None]
    if sin_leer:
        Notificacion.objects.filter(pk__in=sin_leer).update(leida_en=timezone.now())
    return render(
        request,
        "notificaciones/lista.html",
        {"pagina": pagina, "sin_leer": sin_leer},
    )
