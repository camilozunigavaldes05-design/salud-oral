from django.db import transaction

from cuentas.models import Usuario
from notificaciones.models import Notificacion
from notificaciones.servicios import notificar

from .auditoria import RECHAZADO, registrar


class AdministracionError(Exception):
    pass


def avisar_nuevo_profesional(profesional):
    usuario = profesional.usuario
    for administrador in Usuario.objects.filter(
        rol=Usuario.Rol.ADMINISTRADOR,
        estado=Usuario.Estado.ACTIVA,
    ):
        notificar(
            administrador,
            Notificacion.Tipo.VERIFICACION,
            "Nuevo profesional por verificar",
            f"{usuario.first_name} {usuario.last_name} ({profesional.especialidad}, "
            f"registro {profesional.registro}) espera la verificación de su perfil.",
        )


def verificar_profesional(administrador, profesional):
    usuario = profesional.usuario
    with transaction.atomic():
        profesional.verificado = True
        profesional.save(update_fields=["verificado"])
        usuario.estado = Usuario.Estado.ACTIVA
        usuario.save(update_fields=["estado"])
        notificar(
            usuario,
            Notificacion.Tipo.VERIFICACION,
            "Tu perfil profesional fue verificado",
            "Un administrador verificó tu registro. Ya puedes ingresar a Salud Oral, "
            "publicar tus horarios de atención y recibir solicitudes de citas.",
        )
    registrar(administrador, "VERIFICAR_PROFESIONAL", f"usuario:{usuario.pk}")


def rechazar_profesional(administrador, profesional):
    usuario = profesional.usuario
    with transaction.atomic():
        profesional.verificado = False
        profesional.save(update_fields=["verificado"])
        usuario.estado = Usuario.Estado.SUSPENDIDA
        usuario.save(update_fields=["estado"])
        notificar(
            usuario,
            Notificacion.Tipo.VERIFICACION,
            "Tu registro profesional no fue aprobado",
            "No pudimos verificar tus datos en el Registro Nacional de Prestadores Individuales "
            "de Salud. Si crees que es un error, contacta al administrador de Salud Oral.",
        )
    registrar(administrador, "RECHAZAR_PROFESIONAL", f"usuario:{usuario.pk}")


def cambiar_estado_cuenta(administrador, usuario, activar):
    accion = "ACTIVAR_CUENTA" if activar else "SUSPENDER_CUENTA"
    if usuario.pk == administrador.pk:
        registrar(administrador, accion, f"usuario:{usuario.pk}", RECHAZADO)
        raise AdministracionError("No puedes cambiar el estado de tu propia cuenta.")
    if activar and usuario.rol == Usuario.Rol.PROFESIONAL and not usuario.profesional.verificado:
        registrar(administrador, accion, f"usuario:{usuario.pk}", RECHAZADO)
        raise AdministracionError(
            "Este profesional aún no está verificado. Usa la opción Verificar en la lista de profesionales."
        )
    nuevo = Usuario.Estado.ACTIVA if activar else Usuario.Estado.SUSPENDIDA
    with transaction.atomic():
        usuario.estado = nuevo
        usuario.save(update_fields=["estado"])
        if activar:
            notificar(
                usuario,
                Notificacion.Tipo.CUENTA,
                "Tu cuenta fue reactivada",
                "Un administrador reactivó tu cuenta. Ya puedes volver a ingresar a Salud Oral.",
            )
        else:
            notificar(
                usuario,
                Notificacion.Tipo.CUENTA,
                "Tu cuenta fue suspendida",
                "Un administrador suspendió tu cuenta de Salud Oral. Si crees que es un error, "
                "contacta al administrador.",
            )
    registrar(administrador, accion, f"usuario:{usuario.pk}")
