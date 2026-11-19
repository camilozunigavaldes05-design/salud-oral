from django.contrib import admin

from .models import Notificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ["destinatario", "tipo", "canal", "estado_envio", "enviada_en", "leida_en"]
    list_filter = ["tipo", "canal", "estado_envio"]
