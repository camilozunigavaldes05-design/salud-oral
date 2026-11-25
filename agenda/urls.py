from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("profesionales/", views.directorio, name="directorio"),
    path("profesionales/<int:pk>/", views.horarios_profesional, name="horarios_profesional"),
    path("horarios/<int:pk>/reservar/", views.reservar, name="reservar"),
    path("reservas/<int:pk>/", views.resumen, name="resumen"),
    path("reservas/<int:pk>/soltar/", views.soltar, name="soltar"),
    path("mis-citas/", views.mis_citas, name="mis_citas"),
    path("horarios/", views.mis_horarios, name="mis_horarios"),
    path("horarios/<int:pk>/eliminar/", views.borrar_horario, name="borrar_horario"),
    path("citas/", views.citas_profesional, name="citas_profesional"),
    path("citas/<int:pk>/", views.detalle_cita, name="detalle_cita"),
    path(
        "citas/<int:pk>/<str:accion>/",
        views.accion_cita,
        name="accion_cita",
    ),
]
