import re

from django.core.exceptions import ValidationError


class LetrasYNumerosValidator:
    def validate(self, password, user=None):
        if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            raise ValidationError(
                "La contraseña debe incluir letras y números.",
                code="password_sin_letras_o_numeros",
            )

    def get_help_text(self):
        return "Tu contraseña debe incluir letras y números."
