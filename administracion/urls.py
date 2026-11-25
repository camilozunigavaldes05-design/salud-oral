from django.urls import path

from . import views

app_name = "administracion"

urlpatterns = [
    path("", views.profesionales, name="profesionales"),
    path("profesionales/<int:pk>/<str:decision>/", views.decidir_profesional, name="decidir_profesional"),
    path("usuarios/", views.usuarios, name="usuarios"),
    path("usuarios/<int:pk>/estado/", views.estado_usuario, name="estado_usuario"),
    path("auditoria/", views.auditoria, name="auditoria"),
]
