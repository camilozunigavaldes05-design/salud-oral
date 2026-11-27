from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Profesional, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "rol", "estado"]
    list_filter = ["rol", "estado"]
    search_fields = ["email", "first_name", "last_name"]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Datos personales", {"fields": ["first_name", "last_name"]}),
        ("Perfil", {"fields": ["rol", "estado", "intentos_fallidos", "bloqueado_hasta"]}),
        ("Permisos", {"fields": ["is_active", "is_staff", "is_superuser"]}),
    ]
    add_fieldsets = [
        (None, {"fields": ["email", "first_name", "last_name", "rol", "password1", "password2"]}),
    ]


@admin.register(Profesional)
class ProfesionalAdmin(admin.ModelAdmin):
    list_display = ["usuario", "registro", "especialidad", "comuna", "verificado"]
    list_filter = ["verificado"]
    search_fields = ["registro", "centro", "comuna", "direccion"]
