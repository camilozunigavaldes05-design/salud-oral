from django.urls import path

from . import views

app_name = "evaluaciones"

urlpatterns = [
    path("", views.historial, name="historial"),
    path("nueva/", views.nueva, name="nueva"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/reintentar/", views.reintentar, name="reintentar"),
    path("<int:pk>/imagen/", views.imagen, name="imagen"),
]
