import logging
from functools import partial

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Notificacion

logger = logging.getLogger(__name__)


def _enviar_correo(notificacion_id):
    notificacion = Notificacion.objects.select_related("destinatario").get(pk=notificacion_id)
    try:
        send_mail(
            subject=notificacion.asunto,
            message=notificacion.mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notificacion.destinatario.email],
            fail_silently=False,
        )
    except Exception as error:
        logger.exception("No se pudo enviar el correo de la notificación %s", notificacion_id)
        notificacion.estado_envio = Notificacion.EstadoEnvio.FALLIDA
        notificacion.error = str(error)[:200]
        notificacion.save(update_fields=["estado_envio", "error"])
        return
    notificacion.estado_envio = Notificacion.EstadoEnvio.ENVIADA
    notificacion.enviada_en = timezone.now()
    notificacion.save(update_fields=["estado_envio", "enviada_en"])


def notificar(destinatario, tipo, asunto, mensaje, cita=None):
    ahora = timezone.now()
    Notificacion.objects.create(
        destinatario=destinatario,
        cita=cita,
        tipo=tipo,
        canal=Notificacion.Canal.INTERNA,
        asunto=asunto,
        mensaje=mensaje,
        estado_envio=Notificacion.EstadoEnvio.ENVIADA,
        enviada_en=ahora,
    )
    correo = Notificacion.objects.create(
        destinatario=destinatario,
        cita=cita,
        tipo=tipo,
        canal=Notificacion.Canal.CORREO,
        asunto=asunto,
        mensaje=mensaje,
    )
    transaction.on_commit(partial(_enviar_correo, correo.pk))
