from django.conf import settings
from django.db import models


class Consentimiento(models.Model):
    paciente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consentimientos",
        limit_choices_to={"rol": "PACIENTE"},
    )
    version_texto = models.CharField(max_length=20)
    aceptado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "consentimiento"

    def __str__(self):
        return f"Consentimiento {self.version_texto} - {self.paciente}"


class Evaluacion(models.Model):
    class Estado(models.TextChoices):
        IMAGEN_RECIBIDA = "IMAGEN_RECIBIDA", "Imagen recibida"
        EN_VALIDACION = "EN_VALIDACION", "En validación"
        RECHAZADA_POR_CALIDAD = "RECHAZADA_POR_CALIDAD", "Rechazada por calidad"
        IMAGEN_APROBADA = "IMAGEN_APROBADA", "Imagen aprobada"
        EN_INFERENCIA = "EN_INFERENCIA", "En inferencia"
        GENERANDO_ADVERTENCIAS = "GENERANDO_ADVERTENCIAS", "Generando advertencias"
        REPORTE_DISPONIBLE = "REPORTE_DISPONIBLE", "Reporte disponible"
        NO_COMPLETADA = "NO_COMPLETADA", "No completada"

    class NivelRiesgo(models.TextChoices):
        BAJO = "BAJO", "Bajo"
        MODERADO = "MODERADO", "Moderado"
        ALTO = "ALTO", "Alto"

    paciente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="evaluaciones",
        limit_choices_to={"rol": "PACIENTE"},
    )
    consentimiento = models.ForeignKey(
        Consentimiento,
        on_delete=models.PROTECT,
        related_name="evaluaciones",
    )
    imagen_uri = models.CharField(max_length=255)
    mime = models.CharField(max_length=20)
    tamano = models.PositiveIntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    calidad_aprobada = models.BooleanField(default=False)
    motivo_rechazo = models.CharField(max_length=120, null=True, blank=True)
    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.IMAGEN_RECIBIDA)
    riesgo = models.CharField(max_length=10, choices=NivelRiesgo.choices, null=True, blank=True)
    reporte = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "evaluacion"
        verbose_name = "evaluación"
        verbose_name_plural = "evaluaciones"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Evaluación {self.pk} - {self.paciente}"
