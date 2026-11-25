from datetime import timedelta

from django.contrib.auth import authenticate
from django.utils import timezone

from administracion.auditoria import BLOQUEADO, FALLIDO, RECHAZADO, registrar

from .models import Usuario

MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 15
MENSAJE_CREDENCIALES = "Correo o contraseña incorrectos."


def _mensaje_bloqueo(usuario):
    hora = timezone.localtime(usuario.bloqueado_hasta).strftime("%H:%M")
    return (
        f"Tu cuenta está bloqueada por {MAX_INTENTOS} intentos fallidos. "
        f"Podrás intentarlo de nuevo después de las {hora}."
    )


def _registrar_intento_fallido(usuario, ahora):
    usuario.intentos_fallidos += 1
    if usuario.intentos_fallidos >= MAX_INTENTOS:
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = ahora + timedelta(minutes=MINUTOS_BLOQUEO)
    usuario.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])


def verificar_credenciales(request, email, password):
    ahora = timezone.now()
    usuario = Usuario.objects.filter(email__iexact=email).first()

    if usuario and usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
        registrar(usuario, "INICIO_SESION", "cuenta", BLOQUEADO)
        return None, _mensaje_bloqueo(usuario)

    autenticado = authenticate(
        request,
        username=usuario.email if usuario else email,
        password=password,
    )

    if autenticado is None:
        if usuario:
            _registrar_intento_fallido(usuario, ahora)
            if usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
                registrar(usuario, "INICIO_SESION", "cuenta", BLOQUEADO)
                return None, _mensaje_bloqueo(usuario)
            registrar(usuario, "INICIO_SESION", "cuenta", FALLIDO)
        return None, MENSAJE_CREDENCIALES

    if autenticado.estado == Usuario.Estado.PENDIENTE_VERIFICACION:
        registrar(autenticado, "INICIO_SESION", "cuenta", RECHAZADO)
        return None, (
            "Tu cuenta de profesional está pendiente de verificación. "
            "Podrás ingresar cuando un administrador la apruebe."
        )

    if autenticado.estado == Usuario.Estado.SUSPENDIDA:
        registrar(autenticado, "INICIO_SESION", "cuenta", RECHAZADO)
        return None, "Tu cuenta está suspendida. Contacta al administrador."

    if autenticado.intentos_fallidos or autenticado.bloqueado_hasta:
        autenticado.intentos_fallidos = 0
        autenticado.bloqueado_hasta = None
        autenticado.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])

    registrar(autenticado, "INICIO_SESION", "cuenta")
    return autenticado, None
