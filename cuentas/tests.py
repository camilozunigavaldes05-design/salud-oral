from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Profesional, Usuario

CLAVE = "clave1234"


def crear_paciente(email="paciente@test.cl", **extra):
    return Usuario.objects.create_user(
        email,
        CLAVE,
        first_name="Ana",
        last_name="Pérez",
        **extra,
    )


class RegistroTests(TestCase):
    def datos_paciente(self, **cambios):
        datos = {
            "first_name": "Ana",
            "last_name": "Pérez",
            "email": "ana@test.cl",
            "password1": CLAVE,
            "password2": CLAVE,
        }
        datos.update(cambios)
        return datos

    def test_ca01_registro_paciente_crea_cuenta(self):
        respuesta = self.client.post(reverse("cuentas:registro_paciente"), self.datos_paciente())
        self.assertRedirects(respuesta, reverse("cuentas:inicio"))
        usuario = Usuario.objects.get(email="ana@test.cl")
        self.assertEqual(usuario.rol, Usuario.Rol.PACIENTE)
        self.assertEqual(usuario.estado, Usuario.Estado.ACTIVA)

    def test_ca04_contrasena_se_guarda_con_hash(self):
        self.client.post(reverse("cuentas:registro_paciente"), self.datos_paciente())
        usuario = Usuario.objects.get(email="ana@test.cl")
        self.assertNotEqual(usuario.password, CLAVE)
        self.assertTrue(usuario.check_password(CLAVE))

    def test_correo_repetido_es_rechazado(self):
        crear_paciente("ana@test.cl")
        respuesta = self.client.post(
            reverse("cuentas:registro_paciente"),
            self.datos_paciente(email="ANA@test.cl"),
        )
        self.assertContains(respuesta, "Ya existe una cuenta con este correo.")
        self.assertEqual(Usuario.objects.count(), 1)

    def test_ca05_contrasena_corta_es_rechazada(self):
        respuesta = self.client.post(
            reverse("cuentas:registro_paciente"),
            self.datos_paciente(password1="ab12", password2="ab12"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.exists())

    def test_ca05_contrasena_sin_numeros_es_rechazada(self):
        respuesta = self.client.post(
            reverse("cuentas:registro_paciente"),
            self.datos_paciente(password1="solamenteletras", password2="solamenteletras"),
        )
        self.assertContains(respuesta, "La contraseña debe incluir letras y números.")
        self.assertFalse(Usuario.objects.exists())

    def test_ca05_contrasena_sin_letras_es_rechazada(self):
        respuesta = self.client.post(
            reverse("cuentas:registro_paciente"),
            self.datos_paciente(password1="48151623", password2="48151623"),
        )
        self.assertContains(respuesta, "La contraseña debe incluir letras y números.")
        self.assertFalse(Usuario.objects.exists())

    def test_contrasenas_distintas_son_rechazadas(self):
        respuesta = self.client.post(
            reverse("cuentas:registro_paciente"),
            self.datos_paciente(password2="otraclave99"),
        )
        self.assertContains(respuesta, "Las contraseñas no coinciden.")
        self.assertFalse(Usuario.objects.exists())

    def test_ca07_registro_publico_no_crea_administradores(self):
        self.client.post(
            reverse("cuentas:registro_paciente"),
            self.datos_paciente(rol="ADMINISTRADOR", is_staff="on", is_superuser="on"),
        )
        usuario = Usuario.objects.get(email="ana@test.cl")
        self.assertEqual(usuario.rol, Usuario.Rol.PACIENTE)
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)

    def test_registro_profesional_queda_pendiente(self):
        datos = self.datos_paciente(
            email="pro@test.cl",
            registro="123456",
            especialidad="Odontología general",
            centro="Clínica Viña",
            comuna="Viña del Mar",
        )
        respuesta = self.client.post(reverse("cuentas:registro_profesional"), datos)
        self.assertRedirects(respuesta, reverse("cuentas:login"))
        usuario = Usuario.objects.get(email="pro@test.cl")
        self.assertEqual(usuario.rol, Usuario.Rol.PROFESIONAL)
        self.assertEqual(usuario.estado, Usuario.Estado.PENDIENTE_VERIFICACION)
        self.assertFalse(usuario.profesional.verificado)


class InicioSesionTests(TestCase):
    def setUp(self):
        self.paciente = crear_paciente()
        self.url = reverse("cuentas:login")

    def ingresar(self, email="paciente@test.cl", password=CLAVE):
        return self.client.post(self.url, {"email": email, "password": password})

    def test_ca02_credenciales_correctas_permiten_ingresar(self):
        respuesta = self.ingresar()
        self.assertRedirects(respuesta, reverse("cuentas:inicio"))
        respuesta = self.client.get(reverse("cuentas:inicio"))
        self.assertTemplateUsed(respuesta, "cuentas/inicio_paciente.html")

    def test_ca02_correo_con_mayusculas_permite_ingresar(self):
        respuesta = self.ingresar(email="PACIENTE@test.cl")
        self.assertRedirects(respuesta, reverse("cuentas:inicio"))

    def test_ca03_credenciales_incorrectas_son_rechazadas(self):
        respuesta = self.ingresar(password="incorrecta1")
        self.assertContains(respuesta, "Correo o contraseña incorrectos.")
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.intentos_fallidos, 1)

    def test_correo_inexistente_muestra_mismo_mensaje(self):
        respuesta = self.ingresar(email="nadie@test.cl")
        self.assertContains(respuesta, "Correo o contraseña incorrectos.")

    def test_ca06_cinco_intentos_fallidos_bloquean_15_minutos(self):
        for _ in range(4):
            self.ingresar(password="incorrecta1")
        respuesta = self.ingresar(password="incorrecta1")
        self.assertContains(respuesta, "Tu cuenta está bloqueada")
        self.paciente.refresh_from_db()
        minutos = (self.paciente.bloqueado_hasta - timezone.now()).total_seconds() / 60
        self.assertAlmostEqual(minutos, 15, delta=1)
        respuesta = self.ingresar()
        self.assertContains(respuesta, "Tu cuenta está bloqueada")

    def test_ca06_bloqueo_vencido_permite_ingresar_y_reinicia_contador(self):
        self.paciente.bloqueado_hasta = timezone.now() - timedelta(minutes=1)
        self.paciente.intentos_fallidos = 3
        self.paciente.save()
        respuesta = self.ingresar()
        self.assertRedirects(respuesta, reverse("cuentas:inicio"))
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.intentos_fallidos, 0)
        self.assertIsNone(self.paciente.bloqueado_hasta)

    def test_profesional_pendiente_no_puede_ingresar(self):
        usuario = crear_paciente(
            "pro@test.cl",
            rol=Usuario.Rol.PROFESIONAL,
            estado=Usuario.Estado.PENDIENTE_VERIFICACION,
        )
        Profesional.objects.create(
            usuario=usuario,
            registro="1",
            especialidad="Odontología",
            centro="Centro",
            comuna="Viña del Mar",
        )
        respuesta = self.ingresar(email="pro@test.cl")
        self.assertContains(respuesta, "pendiente de verificación")

    def test_cuenta_suspendida_no_puede_ingresar(self):
        self.paciente.estado = Usuario.Estado.SUSPENDIDA
        self.paciente.save()
        respuesta = self.ingresar()
        self.assertContains(respuesta, "Tu cuenta está suspendida")

    def test_inicio_muestra_pagina_segun_rol(self):
        usuario = crear_paciente("pro@test.cl", rol=Usuario.Rol.PROFESIONAL)
        Profesional.objects.create(
            usuario=usuario,
            registro="2",
            especialidad="Odontología",
            centro="Centro",
            comuna="Viña del Mar",
        )
        self.ingresar(email="pro@test.cl")
        respuesta = self.client.get(reverse("cuentas:inicio"))
        self.assertTemplateUsed(respuesta, "cuentas/inicio_profesional.html")

    def test_inicio_exige_sesion(self):
        respuesta = self.client.get(reverse("cuentas:inicio"))
        self.assertRedirects(respuesta, f"{self.url}?next={reverse('cuentas:inicio')}")

    def test_cerrar_sesion(self):
        self.ingresar()
        respuesta = self.client.post(reverse("cuentas:logout"))
        self.assertRedirects(respuesta, reverse("cuentas:bienvenida"))
        respuesta = self.client.get(reverse("cuentas:inicio"))
        self.assertEqual(respuesta.status_code, 302)
