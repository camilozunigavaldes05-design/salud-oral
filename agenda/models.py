from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from cuentas.models import Profesional


def expiracion_bloqueo():
    return timezone.now() + timedelta(minutes=15)


class Horario(models.Model):
    class Estado(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        RESERVADO = "RESERVADO", "Reservado"

    profesional = models.ForeignKey(
        Profesional,
        on_delete=models.CASCADE,
        related_name="horarios",
    )
    inicio = models.DateTimeField()
    fin = models.DateTimeField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.DISPONIBLE)

    class Meta:
        db_table = "horario"
        ordering = ["inicio"]
        constraints = [
            models.CheckConstraint(
                condition=Q(fin__gt=F("inicio")),
                name="horario_fin_despues_de_inicio",
            ),
        ]

    def __str__(self):
        return f"{self.profesional.usuario} - {timezone.localtime(self.inicio):%d/%m/%Y %H:%M}"


class BloqueoTemporal(models.Model):
    class Estado(models.TextChoices):
        VIGENTE = "VIGENTE", "Vigente"
        UTILIZADO = "UTILIZADO", "Utilizado"
        EXPIRADO = "EXPIRADO", "Expirado"

    paciente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bloqueos",
        limit_choices_to={"rol": "PACIENTE"},
    )
    horario = models.ForeignKey(
        Horario,
        on_delete=models.CASCADE,
        related_name="bloqueos",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField(default=expiracion_bloqueo)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.VIGENTE)

    class Meta:
        db_table = "bloqueo_temporal"
        verbose_name = "bloqueo temporal"
        verbose_name_plural = "bloqueos temporales"
        constraints = [
            models.UniqueConstraint(
                fields=["horario"],
                condition=Q(estado="VIGENTE"),
                name="un_bloqueo_vigente_por_horario",
            ),
        ]

    def __str__(self):
        return f"Bloqueo {self.pk} - {self.horario}"


class Cita(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE_CONFIRMACION = "PENDIENTE_CONFIRMACION", "Pendiente de confirmación"
        CONFIRMADA = "CONFIRMADA", "Confirmada"
        REPROGRAMADA = "REPROGRAMADA", "Reprogramada"
        CANCELADA = "CANCELADA", "Cancelada"

    paciente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="citas",
        limit_choices_to={"rol": "PACIENTE"},
    )
    horario = models.ForeignKey(
        Horario,
        on_delete=models.PROTECT,
        related_name="citas",
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.PENDIENTE_CONFIRMACION,
    )
    motivo_cancelacion = models.CharField(max_length=200, null=True, blank=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cita"
        ordering = ["-creada_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["horario"],
                condition=~Q(estado="CANCELADA"),
                name="una_cita_vigente_por_horario",
            ),
        ]

    def __str__(self):
        return f"Cita {self.pk} - {self.paciente} ({self.get_estado_display()})"
