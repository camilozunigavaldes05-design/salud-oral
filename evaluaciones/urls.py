from django.urls import path

from . import views

app_name = "evaluaciones"

urlpatterns = [
    path("", views.historial, name="historial"),
    path("nueva/", views.nueva, name="nueva"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/reintentar/", views.reintentar, name="reintentar"),
    path("<int:pk>/imagen/", views.imagen, name="imagen"),
    path("pacientes/<int:paciente_id>/", views.historial_paciente, name="historial_paciente"),
    path(
        "pacientes/<int:paciente_id>/<int:pk>/imagen/",
        views.imagen_paciente,
        name="imagen_paciente",
    ),
]
