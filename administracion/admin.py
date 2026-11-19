from django.contrib import admin

from .models import Auditoria


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ["fecha", "usuario", "accion", "recurso", "resultado"]
    list_filter = ["resultado"]
    search_fields = ["accion", "recurso"]
