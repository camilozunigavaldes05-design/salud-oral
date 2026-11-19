from django.contrib import admin

from .models import BloqueoTemporal, Cita, Horario


@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ["profesional", "inicio", "fin", "estado"]
    list_filter = ["estado"]


@admin.register(BloqueoTemporal)
class BloqueoTemporalAdmin(admin.ModelAdmin):
    list_display = ["paciente", "horario", "creado_en", "expira_en", "estado"]
    list_filter = ["estado"]


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ["id", "paciente", "horario", "estado", "creada_en"]
    list_filter = ["estado"]
