from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from administracion.models import Auditoria
from cuentas.models import Profesional, Usuario
from notificaciones.models import Notificacion

from .models import BloqueoTemporal, Cita, Horario

CLAVE = "clave1234"


def crear_paciente(email="paciente@test.cl"):
    return Usuario.objects.create_user(email, CLAVE, first_name="Ana", last_name="Pérez")


def crear_profesional(email="pro@test.cl", verificado=True, registro="100"):
    usuario = Usuario.objects.create_user(
        email, CLAVE, first_name="Diego", last_name="Rojas", rol=Usuario.Rol.PROFESIONAL,
    )
    return Profesional.objects.create(
        usuario=usuario, registro=registro, especialidad="Odontología general",
        centro="Clínica Viña", comuna="Viña del Mar", verificado=verificado,
    )


def crear_horario(profesional, horas=24, minutos=30):
    inicio = timezone.now() + timedelta(hours=horas)
    return Horario.objects.create(profesional=profesional, inicio=inicio, fin=inicio + timedelta(minutes=minutos))


class BaseAgendaTests(TestCase):
    def setUp(self):
        self.paciente = crear_paciente()
        self.profesional = crear_profesional()
        self.horario = crear_horario(self.profesional)

    def solicitar(self, horario=None, paciente=None):
        self.client.force_login(paciente or self.paciente)
        horario = horario or self.horario
        respuesta = self.client.post(reverse("agenda:reservar", args=[horario.pk]))
        bloqueo = BloqueoTemporal.objects.filter(horario=horario).order_by("-pk").first()
        return respuesta, bloqueo

    def confirmar_solicitud(self, bloqueo):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse("agenda:resumen", args=[bloqueo.pk]))

    def crear_cita(self, horario=None):
        _, bloqueo = self.solicitar(horario)
        self.confirmar_solicitud(bloqueo)
        return Cita.objects.latest("pk")


class DirectorioTests(BaseAgendaTests):
    def test_rf06_ca01_lista_profesionales_verificados_con_horarios(self):
        crear_profesional("noverificado@test.cl", verificado=False, registro="200")
        sin_horas = crear_profesional("sinhoras@test.cl", registro="300")
        sin_horas.usuario.first_name = "Sinhoras"
        sin_horas.usuario.save()
        self.client.force_login(self.paciente)
        respuesta = self.client.get(reverse("agenda:directorio"))
        self.assertEqual(list(respuesta.context["profesionales"]), [self.profesional])
        self.assertNotContains(respuesta, "Sinhoras")

    def test_rf10_ca02_profesional_no_verificado_no_aparece(self):
        pendiente = crear_profesional("pendiente@test.cl", verificado=False, registro="400")
        crear_horario(pendiente)
        self.client.force_login(self.paciente)
        respuesta = self.client.get(reverse("agenda:directorio"))
        self.assertNotIn(pendiente, respuesta.context["profesionales"])
        respuesta = self.client.get(reverse("agenda:horarios_profesional", args=[pendiente.pk]))
        self.assertEqual(respuesta.status_code, 404)

    def test_horarios_pasados_no_se_ofrecen(self):
        pasado = Horario.objects.create(
            profesional=self.profesional,
            inicio=timezone.now() - timedelta(hours=2),
            fin=timezone.now() - timedelta(hours=1),
        )
        self.client.force_login(self.paciente)
        respuesta = self.client.get(reverse("agenda:horarios_profesional", args=[self.profesional.pk]))
        horarios = [h for _, grupo in respuesta.context["dias"] for h in grupo]
        self.assertIn(self.horario, horarios)
        self.assertNotIn(pasado, horarios)


class SolicitudTests(BaseAgendaTests):
    def test_rf06_ca02_seleccionar_horario_lo_bloquea_15_minutos(self):
        respuesta, bloqueo = self.solicitar()
        self.assertRedirects(respuesta, reverse("agenda:resumen", args=[bloqueo.pk]))
        self.assertEqual(bloqueo.estado, BloqueoTemporal.Estado.VIGENTE)
        minutos = (bloqueo.expira_en - bloqueo.creado_en).total_seconds() / 60
        self.assertAlmostEqual(minutos, 15, delta=0.1)

    def test_rf06_ca03_confirmar_registra_cita_pendiente(self):
        _, bloqueo = self.solicitar()
        respuesta = self.confirmar_solicitud(bloqueo)
        self.assertRedirects(respuesta, reverse("agenda:mis_citas"))
        cita = Cita.objects.get()
        self.assertEqual(cita.estado, Cita.Estado.PENDIENTE_CONFIRMACION)
        bloqueo.refresh_from_db()
        self.horario.refresh_from_db()
        self.assertEqual(bloqueo.estado, BloqueoTemporal.Estado.UTILIZADO)
        self.assertEqual(self.horario.estado, Horario.Estado.RESERVADO)

    def test_rf06_ca04_bloqueo_vencido_libera_el_horario(self):
        _, bloqueo = self.solicitar()
        BloqueoTemporal.objects.filter(pk=bloqueo.pk).update(expira_en=timezone.now() - timedelta(seconds=1))
        respuesta = self.confirmar_solicitud(bloqueo)
        self.assertFalse(Cita.objects.exists())
        self.assertRedirects(respuesta, reverse("agenda:horarios_profesional", args=[self.profesional.pk]))
        otro = crear_paciente("otro@test.cl")
        _, nuevo = self.solicitar(paciente=otro)
        self.assertEqual(nuevo.paciente, otro)
        self.assertEqual(nuevo.estado, BloqueoTemporal.Estado.VIGENTE)

    def test_rf06_ca05_otro_paciente_no_puede_tomar_horario_bloqueado(self):
        self.solicitar()
        otro = crear_paciente("otro@test.cl")
        self.client.force_login(otro)
        respuesta = self.client.post(reverse("agenda:reservar", args=[self.horario.pk]), follow=True)
        self.assertContains(respuesta, "otro paciente lo eligió")
        self.assertEqual(BloqueoTemporal.objects.count(), 1)

    def test_horario_bloqueado_no_aparece_a_otros_pacientes(self):
        self.solicitar()
        otro = crear_paciente("otro@test.cl")
        self.client.force_login(otro)
        respuesta = self.client.get(reverse("agenda:directorio"))
        self.assertEqual(list(respuesta.context["profesionales"]), [])

    def test_horario_reservado_no_admite_segunda_solicitud(self):
        self.crear_cita()
        otro = crear_paciente("otro@test.cl")
        respuesta, _ = self.solicitar(paciente=otro)
        self.assertEqual(Cita.objects.count(), 1)
        self.assertEqual(BloqueoTemporal.objects.filter(paciente=otro).count(), 0)

    def test_soltar_libera_el_horario(self):
        _, bloqueo = self.solicitar()
        self.client.post(reverse("agenda:soltar", args=[bloqueo.pk]))
        bloqueo.refresh_from_db()
        self.assertEqual(bloqueo.estado, BloqueoTemporal.Estado.EXPIRADO)

    def test_paciente_no_puede_confirmar_bloqueo_ajeno(self):
        _, bloqueo = self.solicitar()
        otro = crear_paciente("otro@test.cl")
        self.client.force_login(otro)
        respuesta = self.client.post(reverse("agenda:resumen", args=[bloqueo.pk]))
        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(Cita.objects.exists())


class HorariosTests(BaseAgendaTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.profesional.usuario)
        self.manana = (timezone.localtime() + timedelta(days=1)).date()

    def publicar(self, inicio="10:00", fin="11:00", duracion="", fecha=None):
        return self.client.post(
            reverse("agenda:mis_horarios"),
            {"fecha": (fecha or self.manana).isoformat(), "hora_inicio": inicio, "hora_fin": fin, "duracion": duracion},
        )

    def test_rf08_ca01_bloque_valido_queda_disponible(self):
        respuesta = self.publicar()
        self.assertRedirects(respuesta, reverse("agenda:mis_horarios"))
        nuevo = Horario.objects.latest("pk")
        self.assertEqual(nuevo.estado, Horario.Estado.DISPONIBLE)
        self.assertEqual(timezone.localtime(nuevo.inicio).hour, 10)

    def test_rf08_rango_se_divide_en_bloques(self):
        self.publicar("09:00", "11:00", "30")
        self.assertEqual(Horario.objects.filter(profesional=self.profesional).count(), 5)

    def test_rf08_ca02_bloque_superpuesto_es_rechazado(self):
        self.publicar("10:00", "11:00")
        respuesta = self.publicar("10:30", "11:30")
        self.assertContains(respuesta, "se superpone")
        self.assertEqual(Horario.objects.filter(profesional=self.profesional).count(), 2)

    def test_rf08_fin_antes_de_inicio_es_rechazado(self):
        respuesta = self.publicar("11:00", "10:00")
        self.assertContains(respuesta, "posterior a la hora de inicio")

    def test_rf08_bloque_en_el_pasado_es_rechazado(self):
        ayer = (timezone.localtime() - timedelta(days=1)).date()
        respuesta = self.publicar(fecha=ayer)
        self.assertContains(respuesta, "fecha u hora pasada")

    def test_rf08_ca03_bloque_con_cita_vigente_no_se_elimina(self):
        cita = self.crear_cita()
        self.client.force_login(self.profesional.usuario)
        self.client.post(reverse("agenda:borrar_horario", args=[cita.horario.pk]))
        self.assertTrue(Horario.objects.filter(pk=cita.horario.pk).exists())

    def test_bloque_libre_se_puede_eliminar(self):
        self.client.post(reverse("agenda:borrar_horario", args=[self.horario.pk]))
        self.assertFalse(Horario.objects.filter(pk=self.horario.pk).exists())

    def test_rf08_ca04_profesional_no_verificado_no_publica(self):
        pendiente = crear_profesional("pendiente@test.cl", verificado=False, registro="500")
        self.client.force_login(pendiente.usuario)
        respuesta = self.client.post(
            reverse("agenda:mis_horarios"),
            {"fecha": self.manana.isoformat(), "hora_inicio": "10:00", "hora_fin": "11:00"},
        )
        self.assertRedirects(respuesta, reverse("cuentas:inicio"))
        self.assertFalse(Horario.objects.filter(profesional=pendiente).exists())


class GestionCitasTests(BaseAgendaTests):
    def setUp(self):
        super().setUp()
        self.cita = self.crear_cita()
        self.client.force_login(self.profesional.usuario)

    def accion(self, accion, datos=None, cita=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse("agenda:accion_cita", args=[(cita or self.cita).pk, accion]), datos or {}
            )

    def test_rf09_ca01_confirmar_cambia_estado_y_notifica(self):
        mail.outbox.clear()
        self.accion("confirmar")
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.estado, Cita.Estado.CONFIRMADA)
        self.assertTrue(any(self.paciente.email in m.to and "confirmada" in m.subject for m in mail.outbox))

    def test_rf09_ca02_cancelar_libera_el_bloque(self):
        self.accion("cancelar", {"motivo": "Imprevisto"})
        self.cita.refresh_from_db()
        self.cita.horario.refresh_from_db()
        self.assertEqual(self.cita.estado, Cita.Estado.CANCELADA)
        self.assertEqual(self.cita.motivo_cancelacion, "Imprevisto")
        self.assertEqual(self.cita.horario.estado, Horario.Estado.DISPONIBLE)

    def test_cancelar_exige_motivo(self):
        self.accion("cancelar", {"motivo": ""})
        self.cita.refresh_from_db()
        self.assertNotEqual(self.cita.estado, Cita.Estado.CANCELADA)

    def test_rf09_ca03_reprogramar_a_bloque_disponible(self):
        anterior = self.cita.horario
        nuevo = crear_horario(self.profesional, horas=48)
        self.accion("reprogramar", {"nuevo_horario": nuevo.pk})
        self.cita.refresh_from_db()
        anterior.refresh_from_db()
        nuevo.refresh_from_db()
        self.assertEqual(self.cita.estado, Cita.Estado.REPROGRAMADA)
        self.assertEqual(self.cita.horario, nuevo)
        self.assertEqual(anterior.estado, Horario.Estado.DISPONIBLE)
        self.assertEqual(nuevo.estado, Horario.Estado.RESERVADO)

    def test_rf09_ca03_no_reprograma_a_bloque_de_otro_profesional(self):
        ajeno = crear_horario(crear_profesional("otro@test.cl", registro="600"), horas=48)
        self.accion("reprogramar", {"nuevo_horario": ajeno.pk})
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.horario, self.horario)

    def test_reprogramada_se_puede_confirmar(self):
        nuevo = crear_horario(self.profesional, horas=48)
        self.accion("reprogramar", {"nuevo_horario": nuevo.pk})
        self.accion("confirmar")
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.estado, Cita.Estado.CONFIRMADA)

    def test_cita_cancelada_no_se_gestiona(self):
        self.accion("cancelar", {"motivo": "Imprevisto"})
        self.accion("confirmar")
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.estado, Cita.Estado.CANCELADA)

    def test_rf09_ca04_profesional_no_gestiona_citas_ajenas(self):
        otro = crear_profesional("otro@test.cl", registro="700")
        self.client.force_login(otro.usuario)
        respuesta = self.client.post(reverse("agenda:accion_cita", args=[self.cita.pk, "confirmar"]))
        self.assertEqual(respuesta.status_code, 404)
        respuesta = self.client.get(reverse("agenda:detalle_cita", args=[self.cita.pk]))
        self.assertEqual(respuesta.status_code, 404)

    def test_paciente_no_entra_a_gestion_de_citas(self):
        self.client.force_login(self.paciente)
        respuesta = self.client.get(reverse("agenda:citas_profesional"))
        self.assertEqual(respuesta.status_code, 403)

    def test_rf09_operacion_queda_en_auditoria(self):
        self.accion("confirmar")
        self.assertTrue(
            Auditoria.objects.filter(
                usuario=self.profesional.usuario, accion="CONFIRMAR_CITA", recurso=f"cita:{self.cita.pk}"
            ).exists()
        )


class NotificacionCitaTests(BaseAgendaTests):
    def test_rf07_ca01_ca03_solicitud_notifica_a_ambos_por_correo_y_alerta(self):
        mail.outbox.clear()
        cita = self.crear_cita()
        for destinatario in (self.paciente, self.profesional.usuario):
            canales = set(
                Notificacion.objects.filter(cita=cita, destinatario=destinatario).values_list("canal", flat=True)
            )
            self.assertEqual(canales, {Notificacion.Canal.CORREO, Notificacion.Canal.INTERNA})
        destinatarios = {direccion for mensaje in mail.outbox for direccion in mensaje.to}
        self.assertEqual(destinatarios, {self.paciente.email, self.profesional.usuario.email})
        self.assertFalse(
            Notificacion.objects.filter(canal=Notificacion.Canal.CORREO).exclude(
                estado_envio=Notificacion.EstadoEnvio.ENVIADA
            ).exists()
        )

    def test_rf07_ca02_notificacion_corresponde_al_estado(self):
        cita = self.crear_cita()
        self.client.force_login(self.profesional.usuario)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("agenda:accion_cita", args=[cita.pk, "cancelar"]), {"motivo": "Licencia"})
        ultima = Notificacion.objects.filter(destinatario=self.paciente).first()
        self.assertIn("cancelada", ultima.asunto)
        self.assertIn("Licencia", ultima.mensaje)

    def test_rf07_ca04_fallo_de_correo_mantiene_la_alerta(self):
        from unittest import mock

        with mock.patch("notificaciones.servicios.send_mail", side_effect=OSError("sin conexión")):
            cita = self.crear_cita()
        correo = Notificacion.objects.get(cita=cita, destinatario=self.paciente, canal=Notificacion.Canal.CORREO)
        self.assertEqual(correo.estado_envio, Notificacion.EstadoEnvio.FALLIDA)
        self.assertIn("sin conexión", correo.error)
        self.assertTrue(
            Notificacion.objects.filter(cita=cita, destinatario=self.paciente, canal=Notificacion.Canal.INTERNA).exists()
        )

    def test_alertas_se_muestran_y_se_marcan_leidas(self):
        self.crear_cita()
        respuesta = self.client.get(reverse("cuentas:inicio"))
        self.assertEqual(respuesta.context["avisos_sin_leer"], 1)
        respuesta = self.client.get(reverse("notificaciones:lista"))
        self.assertContains(respuesta, "Tu solicitud de cita fue registrada")
        respuesta = self.client.get(reverse("cuentas:inicio"))
        self.assertEqual(respuesta.context["avisos_sin_leer"], 0)


class HistorialProfesionalTests(BaseAgendaTests):
    def url(self):
        return reverse("evaluaciones:historial_paciente", args=[self.paciente.pk])

    def test_rn04_con_cita_vigente_puede_ver_historial(self):
        self.crear_cita()
        self.client.force_login(self.profesional.usuario)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.assertTrue(Auditoria.objects.filter(accion="VER_HISTORIAL", resultado="OK").exists())

    def test_rf05_ca03_sin_cita_no_puede_ver_historial(self):
        self.client.force_login(self.profesional.usuario)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_rf05_ca03_cita_cancelada_revoca_el_acceso(self):
        cita = self.crear_cita()
        self.client.force_login(self.profesional.usuario)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("agenda:accion_cita", args=[cita.pk, "cancelar"]), {"motivo": "x"})
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_rf05_ca05_acceso_vence_30_dias_despues_de_la_atencion(self):
        cita = self.crear_cita()
        Horario.objects.filter(pk=cita.horario_id).update(
            inicio=timezone.now() - timedelta(days=29, hours=1),
            fin=timezone.now() - timedelta(days=29),
        )
        self.client.force_login(self.profesional.usuario)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        Horario.objects.filter(pk=cita.horario_id).update(
            inicio=timezone.now() - timedelta(days=31, hours=1),
            fin=timezone.now() - timedelta(days=31),
        )
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_otro_profesional_no_ve_el_historial(self):
        self.crear_cita()
        otro = crear_profesional("otro@test.cl", registro="800")
        self.client.force_login(otro.usuario)
        self.assertEqual(self.client.get(self.url()).status_code, 404)
