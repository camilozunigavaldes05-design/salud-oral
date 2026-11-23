import io

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .advertencias import AVISO_ORIENTATIVO, advertencias_para
from .almacenamiento import leer_imagen
from .forms import NuevaEvaluacionForm
from .models import Evaluacion
from .permisos import solo_pacientes
from .servicios import ImagenNoProcesable, analizar, crear_evaluacion, puede_reintentarse

ESTADOS_EN_HISTORIAL = [
    Evaluacion.Estado.REPORTE_DISPONIBLE,
    Evaluacion.Estado.NO_COMPLETADA,
]


def _evaluacion_propia(request, pk):
    return get_object_or_404(Evaluacion, pk=pk, paciente=request.user)


@solo_pacientes
def nueva(request):
    form = NuevaEvaluacionForm(request.POST or None, request.FILES or None)
    calidad = None

    if request.method == "POST" and form.is_valid():
        try:
            evaluacion, calidad = crear_evaluacion(
                request.user,
                form.contenido,
                form.extension,
                form.mime,
            )
        except ImagenNoProcesable:
            form.add_error(
                "imagen",
                "No pudimos procesar la imagen. Intenta con otra fotografía.",
            )
        else:
            if calidad.aprobada:
                return redirect("evaluaciones:detalle", pk=evaluacion.pk)
            form = NuevaEvaluacionForm(initial={"acepta": True})

    return render(
        request,
        "evaluaciones/nueva.html",
        {"form": form, "calidad": calidad},
    )


@solo_pacientes
def detalle(request, pk):
    evaluacion = _evaluacion_propia(request, pk)
    contexto = {
        "evaluacion": evaluacion,
        "aviso": AVISO_ORIENTATIVO,
        "puede_reintentarse": puede_reintentarse(evaluacion),
    }
    if evaluacion.estado == Evaluacion.Estado.REPORTE_DISPONIBLE:
        contexto["advertencias"] = advertencias_para(evaluacion.riesgo)
    return render(request, "evaluaciones/detalle.html", contexto)


@require_POST
@solo_pacientes
def reintentar(request, pk):
    evaluacion = _evaluacion_propia(request, pk)
    if puede_reintentarse(evaluacion):
        analizar(evaluacion)
    return redirect("evaluaciones:detalle", pk=evaluacion.pk)


@solo_pacientes
def historial(request):
    evaluaciones = Evaluacion.objects.filter(
        paciente=request.user,
        estado__in=ESTADOS_EN_HISTORIAL,
    )
    return render(request, "evaluaciones/historial.html", {"evaluaciones": evaluaciones})


@solo_pacientes
def imagen(request, pk):
    evaluacion = _evaluacion_propia(request, pk)
    if not evaluacion.imagen_uri:
        raise Http404
    try:
        contenido = leer_imagen(evaluacion.imagen_uri)
    except FileNotFoundError:
        raise Http404
    respuesta = FileResponse(io.BytesIO(contenido), content_type=evaluacion.mime)
    respuesta["Cache-Control"] = "private, no-store"
    return respuesta
