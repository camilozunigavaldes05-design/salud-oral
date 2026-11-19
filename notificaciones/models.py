from django.conf import settings
from django.db import models

from agenda.models import Cita


class Notificacion(models.Model):
    class Tipo(models.TextChoices):
        CITA = "CITA", "Cita"
        VERIFICACION = "VERIFICACION", "Verificación"
        CUENTA = "CUENTA", "Cuenta"

    class Canal(models.TextChoices):
        CORREO = "CORREO", "Correo"
        INTERNA = "INTERNA", "Alerta interna"

    class EstadoEnvio(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ENVIADA = "ENVIADA", "Enviada"
        FALLIDA = "FALLIDA", "Fallida"

    cita = models.ForeignKey(
        Cita,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notificaciones",
    )
    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificaciones",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    canal = models.CharField(max_length=20, choices=Canal.choices)
    estado_envio = models.CharField(
        max_length=20,
        choices=EstadoEnvio.choices,
        default=EstadoEnvio.PENDIENTE,
    )
    enviada_en = models.DateTimeField(null=True, blank=True)
    leida_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notificacion"
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"

    def __str__(self):
        return f"{self.get_tipo_display()} para {self.destinatario}"
