from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from administracion.auditoria import registrar
from cuentas.models import Profesional, Usuario
from notificaciones.models import Notificacion
from notificaciones.servicios import notificar

from .models import BloqueoTemporal, Cita, Horario

DIAS_ACCESO_HISTORIAL = 30
ESTADOS_VIGENTES = [
    Cita.Estado.PENDIENTE_CONFIRMACION,
    Cita.Estado.CONFIRMADA,
    Cita.Estado.REPROGRAMADA,
]


class AgendaError(Exception):
    pass


def _fecha(horario):
    inicio = timezone.localtime(horario.inicio)
    fin = timezone.localtime(horario.fin)
    return f"{inicio:%d/%m/%Y} de {inicio:%H:%M} a {fin:%H:%M}"


def expirar_bloqueos():
    return BloqueoTemporal.objects.filter(
        estado=BloqueoTemporal.Estado.VIGENTE,
        expira_en__lte=timezone.now(),
    ).update(estado=BloqueoTemporal.Estado.EXPIRADO)


def horarios_disponibles(profesional=None):
    expirar_bloqueos()
    horarios = Horario.objects.filter(
        estado=Horario.Estado.DISPONIBLE,
        inicio__gt=timezone.now(),
    ).exclude(bloqueos__estado=BloqueoTemporal.Estado.VIGENTE)
    if profesional is not None:
        horarios = horarios.filter(profesional=profesional)
    return horarios.order_by("inicio")


def profesionales_disponibles():
    disponibles = horarios_disponibles().values("profesional")
    return (
        Profesional.objects.filter(
            verificado=True,
            usuario__estado=Usuario.Estado.ACTIVA,
            pk__in=disponibles,
        )
        .select_related("usuario")
        .order_by("usuario__last_name", "usuario__first_name")
    )


def crear_horarios(profesional, bloques):
    ahora = timezone.now()
    for inicio, fin in bloques:
        if fin <= inicio:
            raise AgendaError("La hora de término debe ser posterior a la hora de inicio.")
        if inicio <= ahora:
            raise AgendaError("No puedes registrar bloques en una fecha u hora pasada.")
    with transaction.atomic():
        Profesional.objects.select_for_update().get(pk=profesional.pk)
        for inicio, fin in bloques:
            choque = Horario.objects.filter(
                profesional=profesional,
                inicio__lt=fin,
                fin__gt=inicio,
            ).first()
            if choque:
                raise AgendaError(
                    f"El bloque se superpone con otro que ya tienes el {_fecha(choque)}."
                )
        creados = [
            Horario.objects.create(profesional=profesional, inicio=inicio, fin=fin)
            for inicio, fin in bloques
        ]
    for horario in creados:
        registrar(profesional.usuario, "CREAR_HORARIO", f"horario:{horario.pk}")
    return creados


def eliminar_horario(horario, usuario):
    expirar_bloqueos()
    if horario.citas.filter(estado__in=ESTADOS_VIGENTES).exists():
        registrar(usuario, "ELIMINAR_HORARIO", f"horario:{horario.pk}", "RECHAZADO")
        raise AgendaError("Este bloque tiene una cita vigente y no se puede eliminar.")
    if horario.citas.exists():
        registrar(usuario, "ELIMINAR_HORARIO", f"horario:{horario.pk}", "RECHAZADO")
        raise AgendaError("Este bloque tiene citas registradas y se conserva en el historial.")
    if horario.bloqueos.filter(estado=BloqueoTemporal.Estado.VIGENTE).exists():
        registrar(usuario, "ELIMINAR_HORARIO", f"horario:{horario.pk}", "RECHAZADO")
        raise AgendaError("Un paciente está reservando este bloque en este momento. Intenta más tarde.")
    pk = horario.pk
    horario.delete()
    registrar(usuario, "ELIMINAR_HORARIO", f"horario:{pk}")


def bloquear_horario(paciente, horario_id):
    expirar_bloqueos()
    try:
        with transaction.atomic():
            horario = Horario.objects.select_for_update().get(pk=horario_id)
            propio = horario.bloqueos.filter(
                paciente=paciente,
                estado=BloqueoTemporal.Estado.VIGENTE,
            ).first()
            if propio:
                return propio
            if (
                horario.estado != Horario.Estado.DISPONIBLE
                or horario.inicio <= timezone.now()
                or horario.bloqueos.filter(estado=BloqueoTemporal.Estado.VIGENTE).exists()
            ):
                raise AgendaError(
                    "Este horario ya no está disponible porque otro paciente lo eligió. "
                    "Elige otro horario."
                )
            BloqueoTemporal.objects.filter(
                paciente=paciente,
                estado=BloqueoTemporal.Estado.VIGENTE,
            ).update(estado=BloqueoTemporal.Estado.EXPIRADO)
            bloqueo = BloqueoTemporal.objects.create(paciente=paciente, horario=horario)
    except Horario.DoesNotExist:
        raise AgendaError("El horario no existe.")
    except IntegrityError:
        raise AgendaError(
            "Este horario ya no está disponible porque otro paciente lo eligió. Elige otro horario."
        )
    registrar(paciente, "BLOQUEAR_HORARIO", f"horario:{horario_id}")
    return bloqueo


def liberar_bloqueo(bloqueo):
    if bloqueo.estado == BloqueoTemporal.Estado.VIGENTE:
        bloqueo.estado = BloqueoTemporal.Estado.EXPIRADO
        bloqueo.save(update_fields=["estado"])


def confirmar_solicitud(bloqueo):
    with transaction.atomic():
        bloqueo = BloqueoTemporal.objects.select_for_update().get(pk=bloqueo.pk)
        horario = Horario.objects.select_for_update().get(pk=bloqueo.horario_id)
        if bloqueo.estado == BloqueoTemporal.Estado.VIGENTE and bloqueo.expira_en <= timezone.now():
            bloqueo.estado = BloqueoTemporal.Estado.EXPIRADO
            bloqueo.save(update_fields=["estado"])
        if bloqueo.estado != BloqueoTemporal.Estado.VIGENTE:
            raise AgendaError(
                "Pasaron más de 15 minutos y el horario se liberó. Vuelve a elegir un horario."
            )
        if horario.estado != Horario.Estado.DISPONIBLE:
            raise AgendaError("Este horario ya no está disponible. Elige otro horario.")
        cita = Cita.objects.create(paciente=bloqueo.paciente, horario=horario)
        bloqueo.estado = BloqueoTemporal.Estado.UTILIZADO
        bloqueo.save(update_fields=["estado"])
        horario.estado = Horario.Estado.RESERVADO
        horario.save(update_fields=["estado"])
        notificar_cita(cita, "registrada")
    registrar(bloqueo.paciente, "SOLICITAR_CITA", f"cita:{cita.pk}")
    return cita


def _validar_propietario(cita, profesional):
    if cita.horario.profesional_id != profesional.pk:
        raise AgendaError("Esta cita no pertenece a tu agenda.")


def confirmar_cita(cita, profesional):
    _validar_propietario(cita, profesional)
    if cita.estado not in (Cita.Estado.PENDIENTE_CONFIRMACION, Cita.Estado.REPROGRAMADA):
        raise AgendaError("Solo se pueden confirmar citas pendientes o reprogramadas.")
    with transaction.atomic():
        cita.estado = Cita.Estado.CONFIRMADA
        cita.save(update_fields=["estado", "actualizada_en"])
        notificar_cita(cita, "confirmada")
    registrar(profesional.usuario, "CONFIRMAR_CITA", f"cita:{cita.pk}")
    return cita


def reprogramar_cita(cita, profesional, nuevo_horario_id):
    _validar_propietario(cita, profesional)
    if cita.estado not in ESTADOS_VIGENTES:
        raise AgendaError("Una cita cancelada no se puede reprogramar.")
    expirar_bloqueos()
    with transaction.atomic():
        nuevo = (
            Horario.objects.select_for_update()
            .filter(pk=nuevo_horario_id, profesional=profesional)
            .first()
        )
        if (
            nuevo is None
            or nuevo.pk == cita.horario_id
            or nuevo.estado != Horario.Estado.DISPONIBLE
            or nuevo.inicio <= timezone.now()
            or nuevo.bloqueos.filter(estado=BloqueoTemporal.Estado.VIGENTE).exists()
        ):
            registrar(profesional.usuario, "REPROGRAMAR_CITA", f"cita:{cita.pk}", "RECHAZADO")
            raise AgendaError("El nuevo bloque no está disponible. Elige otro bloque de tu agenda.")
        anterior = Horario.objects.select_for_update().get(pk=cita.horario_id)
        anterior.estado = Horario.Estado.DISPONIBLE
        anterior.save(update_fields=["estado"])
        nuevo.estado = Horario.Estado.RESERVADO
        nuevo.save(update_fields=["estado"])
        cita.horario = nuevo
        cita.estado = Cita.Estado.REPROGRAMADA
        cita.save(update_fields=["horario", "estado", "actualizada_en"])
        notificar_cita(cita, "reprogramada")
    registrar(profesional.usuario, "REPROGRAMAR_CITA", f"cita:{cita.pk}")
    return cita


def cancelar_cita(cita, profesional, motivo):
    _validar_propietario(cita, profesional)
    if cita.estado == Cita.Estado.CANCELADA:
        raise AgendaError("Esta cita ya estaba cancelada.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise AgendaError("Escribe el motivo de la cancelación.")
    with transaction.atomic():
        horario = Horario.objects.select_for_update().get(pk=cita.horario_id)
        cita.estado = Cita.Estado.CANCELADA
        cita.motivo_cancelacion = motivo[:200]
        cita.save(update_fields=["estado", "motivo_cancelacion", "actualizada_en"])
        horario.estado = Horario.Estado.DISPONIBLE
        horario.save(update_fields=["estado"])
        notificar_cita(cita, "cancelada")
    registrar(profesional.usuario, "CANCELAR_CITA", f"cita:{cita.pk}")
    return cita


def puede_ver_historial(profesional_usuario, paciente):
    if profesional_usuario.rol != Usuario.Rol.PROFESIONAL:
        return False
    limite = timezone.now() - timedelta(days=DIAS_ACCESO_HISTORIAL)
    return Cita.objects.filter(
        paciente=paciente,
        horario__profesional__usuario=profesional_usuario,
        estado__in=ESTADOS_VIGENTES,
        horario__fin__gte=limite,
    ).exists()


def notificar_cita(cita, evento):
    horario = cita.horario
    paciente = cita.paciente
    profesional = horario.profesional
    cuando = _fecha(horario)
    lugar = f"{profesional.centro}, {profesional.comuna}"
    nombre_profesional = f"{profesional.usuario.first_name} {profesional.usuario.last_name}"
    nombre_paciente = f"{paciente.first_name} {paciente.last_name}"

    if evento == "registrada":
        para_paciente = (
            "Tu solicitud de cita fue registrada",
            f"Solicitaste una cita con {nombre_profesional} el {cuando} en {lugar}. "
            "Está pendiente de confirmación por parte del profesional.",
        )
        para_profesional = (
            "Nueva solicitud de cita",
            f"{nombre_paciente} solicitó una cita el {cuando}. Ingresa a Salud Oral para confirmarla, "
            "reprogramarla o cancelarla.",
        )
    elif evento == "confirmada":
        para_paciente = (
            "Tu cita fue confirmada",
            f"{nombre_profesional} confirmó tu cita del {cuando} en {lugar}.",
        )
        para_profesional = (
            "Confirmaste una cita",
            f"Confirmaste la cita con {nombre_paciente} del {cuando}.",
        )
    elif evento == "reprogramada":
        para_paciente = (
            "Tu cita fue reprogramada",
            f"{nombre_profesional} cambió tu cita para el {cuando} en {lugar}.",
        )
        para_profesional = (
            "Reprogramaste una cita",
            f"La cita con {nombre_paciente} quedó para el {cuando}.",
        )
    elif evento == "cancelada":
        para_paciente = (
            "Tu cita fue cancelada",
            f"{nombre_profesional} canceló tu cita del {cuando}. Motivo: {cita.motivo_cancelacion}. "
            "Puedes solicitar una nueva hora en Salud Oral.",
        )
        para_profesional = (
            "Cancelaste una cita",
            f"Cancelaste la cita con {nombre_paciente} del {cuando}. Motivo: {cita.motivo_cancelacion}.",
        )
    else:
        raise ValueError(evento)

    notificar(paciente, Notificacion.Tipo.CITA, *para_paciente, cita=cita)
    notificar(profesional.usuario, Notificacion.Tipo.CITA, *para_profesional, cita=cita)
