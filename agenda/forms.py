from datetime import datetime, timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

DURACIONES = [
    ("", "Un solo bloque"),
    ("30", "Bloques de 30 minutos"),
    ("45", "Bloques de 45 minutos"),
    ("60", "Bloques de 1 hora"),
]


class HorarioForm(forms.Form):
    fecha = forms.DateField(label="Fecha", widget=forms.DateInput(attrs={"type": "date"}))
    hora_inicio = forms.TimeField(label="Hora de inicio", widget=forms.TimeInput(attrs={"type": "time"}))
    hora_fin = forms.TimeField(label="Hora de término", widget=forms.TimeInput(attrs={"type": "time"}))
    duracion = forms.ChoiceField(
        label="Dividir en",
        choices=DURACIONES,
        required=False,
    )

    def clean(self):
        datos = super().clean()
        fecha = datos.get("fecha")
        hora_inicio = datos.get("hora_inicio")
        hora_fin = datos.get("hora_fin")
        if not (fecha and hora_inicio and hora_fin):
            return datos

        inicio = timezone.make_aware(datetime.combine(fecha, hora_inicio))
        fin = timezone.make_aware(datetime.combine(fecha, hora_fin))
        if fin <= inicio:
            raise ValidationError("La hora de término debe ser posterior a la hora de inicio.")
        if inicio <= timezone.now():
            raise ValidationError("No puedes registrar bloques en una fecha u hora pasada.")

        minutos = int(datos.get("duracion") or 0)
        if not minutos:
            self.bloques = [(inicio, fin)]
            return datos

        paso = timedelta(minutes=minutos)
        bloques = []
        actual = inicio
        while actual + paso <= fin:
            bloques.append((actual, actual + paso))
            actual += paso
        if not bloques:
            raise ValidationError("El rango es más corto que la duración elegida.")
        self.bloques = bloques
        return datos


class CancelarCitaForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo de la cancelación",
        max_length=200,
        widget=forms.Textarea(attrs={"rows": 3}),
        error_messages={"required": "Escribe el motivo de la cancelación."},
    )


class ReprogramarCitaForm(forms.Form):
    nuevo_horario = forms.ChoiceField(
        label="Nuevo bloque",
        error_messages={"required": "Elige el nuevo bloque."},
    )

    def __init__(self, *args, horarios=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nuevo_horario"].choices = [("", "Elige un bloque disponible")] + [
            (
                horario.pk,
                f"{timezone.localtime(horario.inicio):%d/%m/%Y %H:%M} - "
                f"{timezone.localtime(horario.fin):%H:%M}",
            )
            for horario in horarios
        ]
