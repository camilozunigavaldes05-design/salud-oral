from django.conf import settings
from django.db import models


class Auditoria(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="registros_auditoria",
    )
    accion = models.CharField(max_length=60)
    fecha = models.DateTimeField(auto_now_add=True)
    recurso = models.CharField(max_length=120)
    resultado = models.CharField(max_length=20)

    class Meta:
        db_table = "auditoria"
        verbose_name = "registro de auditoría"
        verbose_name_plural = "auditoría"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.usuario} - {self.accion} - {self.fecha:%d/%m/%Y %H:%M}"
