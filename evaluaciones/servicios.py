from django.db import transaction

from .advertencias import generar_reporte
from .almacenamiento import eliminar_imagen, guardar_imagen, leer_imagen
from .calidad import evaluar_calidad
from .clasificador import ClasificacionNoCompletada, probabilidad_de_riesgo
from .models import Consentimiento, Evaluacion
from .riesgo import nivel_de_riesgo

VERSION_CONSENTIMIENTO = "1.0"


class ImagenNoProcesable(Exception):
    pass


def _cambiar_estado(evaluacion, estado):
    evaluacion.estado = estado
    evaluacion.save(update_fields=["estado"])


def crear_evaluacion(paciente, contenido, extension, mime):
    with transaction.atomic():
        consentimiento = Consentimiento.objects.create(
            paciente=paciente,
            version_texto=VERSION_CONSENTIMIENTO,
        )
        evaluacion = Evaluacion.objects.create(
            paciente=paciente,
            consentimiento=consentimiento,
            imagen_uri=guardar_imagen(paciente.pk, contenido, extension),
            mime=mime,
            tamano=len(contenido),
        )

    _cambiar_estado(evaluacion, Evaluacion.Estado.EN_VALIDACION)
    try:
        calidad = evaluar_calidad(contenido)
    except Exception as error:
        eliminar_imagen(evaluacion.imagen_uri)
        evaluacion.imagen_uri = ""
        evaluacion.motivo_rechazo = "Imagen no procesable"
        evaluacion.estado = Evaluacion.Estado.RECHAZADA_POR_CALIDAD
        evaluacion.save(update_fields=["imagen_uri", "motivo_rechazo", "estado"])
        raise ImagenNoProcesable from error

    if not calidad.aprobada:
        eliminar_imagen(evaluacion.imagen_uri)
        evaluacion.imagen_uri = ""
        evaluacion.motivo_rechazo = calidad.motivo
        evaluacion.estado = Evaluacion.Estado.RECHAZADA_POR_CALIDAD
        evaluacion.save(update_fields=["imagen_uri", "motivo_rechazo", "estado"])
        return evaluacion, calidad

    evaluacion.calidad_aprobada = True
    evaluacion.estado = Evaluacion.Estado.IMAGEN_APROBADA
    evaluacion.save(update_fields=["calidad_aprobada", "estado"])
    analizar(evaluacion, contenido)
    return evaluacion, calidad


def analizar(evaluacion, contenido=None):
    if contenido is None:
        contenido = leer_imagen(evaluacion.imagen_uri)

    _cambiar_estado(evaluacion, Evaluacion.Estado.EN_INFERENCIA)
    try:
        probabilidad = probabilidad_de_riesgo(contenido)
    except ClasificacionNoCompletada:
        _cambiar_estado(evaluacion, Evaluacion.Estado.NO_COMPLETADA)
        return evaluacion

    _cambiar_estado(evaluacion, Evaluacion.Estado.GENERANDO_ADVERTENCIAS)
    evaluacion.riesgo = nivel_de_riesgo(probabilidad)
    evaluacion.reporte = generar_reporte(evaluacion.riesgo)
    evaluacion.estado = Evaluacion.Estado.REPORTE_DISPONIBLE
    evaluacion.save(update_fields=["riesgo", "reporte", "estado"])
    return evaluacion


def puede_reintentarse(evaluacion):
    return (
        evaluacion.estado == Evaluacion.Estado.NO_COMPLETADA
        and evaluacion.calidad_aprobada
        and bool(evaluacion.imagen_uri)
    )
