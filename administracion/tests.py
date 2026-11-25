from django.core import mail
from django.test import TestCase
from django.urls import reverse

from cuentas.models import Profesional, Usuario
from notificaciones.models import Notificacion

from .models import Auditoria

CLAVE = "clave1234"


class AdministracionTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            "admin@test.cl", CLAVE, first_name="Ada", last_name="Min"
        )
        self.paciente = Usuario.objects.create_user(
            "paciente@test.cl", CLAVE, first_name="Ana", last_name="Pérez"
        )
        usuario = Usuario.objects.create_user(
            "pro@test.cl", CLAVE, first_name="Diego", last_name="Rojas",
            rol=Usuario.Rol.PROFESIONAL, estado=Usuario.Estado.PENDIENTE_VERIFICACION,
        )
        self.profesional = Profesional.objects.create(
            usuario=usuario, registro="123", especialidad="Odontología",
            centro="Clínica", comuna="Viña del Mar",
        )
        self.client.force_login(self.admin)

    def decidir(self, decision):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse("administracion:decidir_profesional", args=[self.profesional.pk, decision])
            )

    def test_rf10_ca01_verificar_profesional(self):
        self.decidir("verificar")
        self.profesional.refresh_from_db()
        self.profesional.usuario.refresh_from_db()
        self.assertTrue(self.profesional.verificado)
        self.assertEqual(self.profesional.usuario.estado, Usuario.Estado.ACTIVA)
        self.assertTrue(any("verificado" in m.subject for m in mail.outbox))

    def test_rf10_profesional_verificado_puede_ingresar(self):
        self.decidir("verificar")
        self.client.logout()
        respuesta = self.client.post(reverse("cuentas:login"), {"email": "pro@test.cl", "password": CLAVE})
        self.assertRedirects(respuesta, reverse("cuentas:inicio"))

    def test_rechazar_profesional(self):
        self.decidir("rechazar")
        self.profesional.refresh_from_db()
        self.profesional.usuario.refresh_from_db()
        self.assertFalse(self.profesional.verificado)
        self.assertEqual(self.profesional.usuario.estado, Usuario.Estado.SUSPENDIDA)

    def test_pendientes_aparecen_en_la_lista(self):
        respuesta = self.client.get(reverse("administracion:profesionales"))
        self.assertIn(self.profesional, respuesta.context["pendientes"])

    def test_rf10_ca03_cuenta_suspendida_no_inicia_sesion(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("administracion:estado_usuario", args=[self.paciente.pk]), {"estado": "suspender"}
            )
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.estado, Usuario.Estado.SUSPENDIDA)
        self.client.logout()
        respuesta = self.client.post(reverse("cuentas:login"), {"email": "paciente@test.cl", "password": CLAVE})
        self.assertContains(respuesta, "Tu cuenta está suspendida")

    def test_cuenta_suspendida_pierde_la_sesion_abierta(self):
        otro = self.client_class()
        otro.force_login(self.paciente)
        self.client.post(reverse("administracion:estado_usuario", args=[self.paciente.pk]), {"estado": "suspender"})
        respuesta = otro.get(reverse("cuentas:inicio"))
        self.assertRedirects(respuesta, reverse("cuentas:login"))

    def test_reactivar_cuenta(self):
        self.paciente.estado = Usuario.Estado.SUSPENDIDA
        self.paciente.save()
        self.client.post(reverse("administracion:estado_usuario", args=[self.paciente.pk]), {"estado": "activar"})
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.estado, Usuario.Estado.ACTIVA)

    def test_admin_no_se_suspende_a_si_mismo(self):
        self.client.post(reverse("administracion:estado_usuario", args=[self.admin.pk]), {"estado": "suspender"})
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.estado, Usuario.Estado.ACTIVA)

    def test_rf10_ca04_sin_rol_administrador_no_entra(self):
        self.client.force_login(self.paciente)
        for nombre in ("profesionales", "usuarios", "auditoria"):
            with self.subTest(pagina=nombre):
                self.assertEqual(self.client.get(reverse(f"administracion:{nombre}")).status_code, 403)
        respuesta = self.client.post(
            reverse("administracion:decidir_profesional", args=[self.profesional.pk, "verificar"])
        )
        self.assertEqual(respuesta.status_code, 403)
        self.profesional.refresh_from_db()
        self.assertFalse(self.profesional.verificado)

    def test_rf10_ca05_operacion_queda_en_auditoria_con_todos_los_datos(self):
        self.decidir("verificar")
        registro = Auditoria.objects.get(accion="VERIFICAR_PROFESIONAL")
        self.assertEqual(registro.usuario, self.admin)
        self.assertEqual(registro.recurso, f"usuario:{self.profesional.pk}")
        self.assertEqual(registro.resultado, "OK")
        self.assertIsNotNone(registro.fecha)

    def test_auditoria_se_filtra_por_accion_y_usuario(self):
        self.decidir("verificar")
        self.client.post(reverse("administracion:estado_usuario", args=[self.paciente.pk]), {"estado": "suspender"})
        respuesta = self.client.get(reverse("administracion:auditoria"), {"accion": "SUSPENDER_CUENTA"})
        acciones = {registro.accion for registro in respuesta.context["pagina"]}
        self.assertEqual(acciones, {"SUSPENDER_CUENTA"})
        respuesta = self.client.get(reverse("administracion:auditoria"), {"usuario": "nadie@"})
        self.assertEqual(len(respuesta.context["pagina"]), 0)

    def test_inicios_de_sesion_quedan_registrados(self):
        self.client.logout()
        self.client.post(reverse("cuentas:login"), {"email": "paciente@test.cl", "password": "mala1234"})
        self.client.post(reverse("cuentas:login"), {"email": "paciente@test.cl", "password": CLAVE})
        resultados = list(
            Auditoria.objects.filter(usuario=self.paciente, accion="INICIO_SESION")
            .order_by("pk")
            .values_list("resultado", flat=True)
        )
        self.assertEqual(resultados, ["FALLIDO", "OK"])

    def test_registro_profesional_avisa_a_los_administradores(self):
        self.client.logout()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("cuentas:registro_profesional"),
                {
                    "first_name": "Nico", "last_name": "Soto", "email": "nico@test.cl",
                    "password1": CLAVE, "password2": CLAVE, "registro": "999",
                    "especialidad": "Periodoncia", "centro": "Centro", "comuna": "Valparaíso",
                },
            )
        self.assertTrue(
            Notificacion.objects.filter(
                destinatario=self.admin, tipo=Notificacion.Tipo.VERIFICACION, canal=Notificacion.Canal.INTERNA
            ).exists()
        )
