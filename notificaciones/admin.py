from django.contrib import admin

from .models import Notificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ["creada_en", "destinatario", "tipo", "canal", "asunto", "estado_envio", "leida_en"]
    list_filter = ["tipo", "canal", "estado_envio"]
    search_fields = ["destinatario__email", "asunto"]
