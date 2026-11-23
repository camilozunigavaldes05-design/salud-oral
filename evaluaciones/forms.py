import io

from django import forms
from django.core.exceptions import ValidationError
from PIL import Image

TAMANO_MAXIMO = 10 * 1024 * 1024
FORMATOS_PERMITIDOS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
}


class NuevaEvaluacionForm(forms.Form):
    acepta = forms.BooleanField(
        label=(
            "Entiendo que el resultado es orientativo y no reemplaza el diagnóstico "
            "de un profesional de la salud oral."
        ),
        error_messages={"required": "Debes aceptar este aviso para iniciar la evaluación."},
    )
    imagen = forms.FileField(
        label="Fotografía de tu boca",
        help_text="Formato JPEG o PNG, de hasta 10 MB.",
        error_messages={
            "required": "Toma o elige una fotografía para continuar.",
            "empty": "El archivo está vacío. Toma o elige otra fotografía.",
        },
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png"}),
    )

    def clean_imagen(self):
        archivo = self.cleaned_data["imagen"]
        if archivo.size > TAMANO_MAXIMO:
            raise ValidationError("La imagen pesa más de 10 MB. Elige una foto más liviana.")

        contenido = archivo.read()
        try:
            with Image.open(io.BytesIO(contenido)) as imagen:
                formato = imagen.format
                imagen.verify()
        except Exception:
            raise ValidationError(
                "El archivo no es una imagen válida. Usa una foto en formato JPEG o PNG."
            )

        if formato not in FORMATOS_PERMITIDOS:
            raise ValidationError("Formato no permitido. Usa una foto en formato JPEG o PNG.")

        self.contenido = contenido
        self.extension, self.mime = FORMATOS_PERMITIDOS[formato]
        return archivo
