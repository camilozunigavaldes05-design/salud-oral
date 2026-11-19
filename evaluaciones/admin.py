from django.contrib import admin

from .models import Consentimiento, Evaluacion


@admin.register(Consentimiento)
class ConsentimientoAdmin(admin.ModelAdmin):
    list_display = ["paciente", "version_texto", "aceptado_en"]


@admin.register(Evaluacion)
class EvaluacionAdmin(admin.ModelAdmin):
    list_display = ["id", "paciente", "fecha", "estado", "riesgo", "calidad_aprobada"]
    list_filter = ["estado", "riesgo", "calidad_aprobada"]
