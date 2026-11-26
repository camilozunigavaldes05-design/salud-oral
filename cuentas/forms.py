from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import FichaClinica, Profesional, Usuario


class InicioSesionForm(forms.Form):
    email = forms.EmailField(
        label="Correo",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class RegistroPacienteForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Mínimo 8 caracteres, con letras y números.",
    )
    password2 = forms.CharField(
        label="Repite la contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise ValidationError("Ya existe una cuenta con este correo.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        return cleaned_data

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get("password1")
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except ValidationError as error:
                self.add_error("password1", error)

    def _preparar_usuario(self, rol, estado):
        usuario = super().save(commit=False)
        usuario.rol = rol
        usuario.estado = estado
        usuario.set_password(self.cleaned_data["password1"])
        return usuario

    def save(self, commit=True):
        usuario = self._preparar_usuario(Usuario.Rol.PACIENTE, Usuario.Estado.ACTIVA)
        if commit:
            usuario.save()
        return usuario


class RegistroProfesionalForm(RegistroPacienteForm):
    registro = forms.CharField(
        label="N.º de registro (Superintendencia de Salud)",
        max_length=20,
    )
    especialidad = forms.CharField(label="Especialidad", max_length=80)
    centro = forms.CharField(label="Centro de atención", max_length=120)
    comuna = forms.CharField(label="Comuna", max_length=60)

    def clean_registro(self):
        registro = self.cleaned_data["registro"].strip()
        if Profesional.objects.filter(registro__iexact=registro).exists():
            raise ValidationError("Ya existe un profesional con este número de registro.")
        return registro

    @transaction.atomic
    def save(self, commit=True):
        usuario = self._preparar_usuario(
            Usuario.Rol.PROFESIONAL,
            Usuario.Estado.PENDIENTE_VERIFICACION,
        )
        usuario.save()
        Profesional.objects.create(
            usuario=usuario,
            registro=self.cleaned_data["registro"],
            especialidad=self.cleaned_data["especialidad"],
            centro=self.cleaned_data["centro"],
            comuna=self.cleaned_data["comuna"],
        )
        return usuario


class FichaClinicaForm(forms.ModelForm):
    """Lo que el paciente declara para que el profesional lo tenga a la vista."""

    class Meta:
        model = FichaClinica
        fields = ["estatura_cm", "peso_kg", "molestias", "desde_cuando"]
        labels = {
            "estatura_cm": "Estatura en centímetros",
            "peso_kg": "Peso en kilos",
            "molestias": "¿Qué molestia o síntoma tienes?",
            "desde_cuando": "¿Desde cuándo?",
        }
        help_texts = {
            "estatura_cm": "Opcional. Por ejemplo: 170",
            "peso_kg": "Opcional. Por ejemplo: 68.5",
            "molestias": "Cuéntalo con tus palabras: dolor, una llaga que no cierra, "
                         "una mancha, dificultad para tragar.",
            "desde_cuando": "Opcional. Por ejemplo: hace tres semanas",
        }
        widgets = {
            "molestias": forms.Textarea(attrs={"rows": 5, "maxlength": 1000}),
            "desde_cuando": forms.TextInput(attrs={"placeholder": "hace tres semanas"}),
        }
