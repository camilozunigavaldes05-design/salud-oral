from django.urls import path

from . import views

app_name = "cuentas"

urlpatterns = [
    path("", views.bienvenida, name="bienvenida"),
    path("ingresar/", views.iniciar_sesion, name="login"),
    path("salir/", views.cerrar_sesion, name="logout"),
    path("registro/", views.registro_paciente, name="registro_paciente"),
    path("registro/profesional/", views.registro_profesional, name="registro_profesional"),
    path("inicio/", views.inicio, name="inicio"),
    path("mis-datos/", views.mi_ficha, name="mi_ficha"),
    path("mi-consulta/", views.mi_consulta, name="mi_consulta"),
]
