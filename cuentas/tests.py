from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import FichaClinica, Profesional, Usuario

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
        self.assertRedirects(respuesta, reverse("cuentas:login"))
        respuesta = self.client.get(reverse("cuentas:inicio"))
        self.assertEqual(respuesta.status_code, 302)


class FichaClinicaTests(TestCase):
    """La ficha que el paciente declara y que el profesional lee."""

    def setUp(self):
        self.paciente = crear_paciente()
        self.url = reverse("cuentas:mi_ficha")

    def datos(self, **cambios):
        datos = {
            "estatura_cm": "172",
            "peso_kg": "68.5",
            "molestias": "Una llaga en la lengua que no cierra.",
            "desde_cuando": "hace tres semanas",
        }
        datos.update(cambios)
        return datos

    def test_el_paciente_guarda_su_ficha(self):
        self.client.force_login(self.paciente)
        respuesta = self.client.post(self.url, self.datos())
        self.assertRedirects(respuesta, reverse("cuentas:inicio"))
        ficha = FichaClinica.objects.get(paciente=self.paciente)
        self.assertEqual(ficha.estatura_cm, 172)
        self.assertEqual(str(ficha.peso_kg), "68.5")
        self.assertIn("llaga", ficha.molestias)

    def test_todos_los_campos_son_opcionales(self):
        self.client.force_login(self.paciente)
        respuesta = self.client.post(
            self.url,
            {"estatura_cm": "", "peso_kg": "", "molestias": "", "desde_cuando": ""},
        )
        self.assertRedirects(respuesta, reverse("cuentas:inicio"))
        ficha = FichaClinica.objects.get(paciente=self.paciente)
        self.assertIsNone(ficha.estatura_cm)
        self.assertFalse(ficha.tiene_datos)

    def test_estatura_fuera_de_rango_se_rechaza_sin_corromper_lo_guardado(self):
        self.client.force_login(self.paciente)
        self.client.post(self.url, self.datos())
        respuesta = self.client.post(self.url, self.datos(estatura_cm="900"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(FichaClinica.objects.get(paciente=self.paciente).estatura_cm, 172)

    def test_un_profesional_no_entra_a_la_ficha(self):
        profesional = crear_paciente("pro@test.cl", rol=Usuario.Rol.PROFESIONAL)
        self.client.force_login(profesional)
        respuesta = self.client.get(self.url)
        self.assertRedirects(respuesta, reverse("cuentas:inicio"))

    def test_visitante_debe_iniciar_sesion(self):
        respuesta = self.client.get(self.url)
        self.assertRedirects(respuesta, f"{reverse('cuentas:login')}?next={self.url}")


class FichaVisibleParaElProfesionalTests(TestCase):
    """La ficha sigue la misma regla de acceso que el historial de evaluaciones."""

    def setUp(self):
        from agenda.models import Cita, Horario

        self.Cita = Cita
        self.paciente = crear_paciente()
        FichaClinica.objects.create(
            paciente=self.paciente,
            estatura_cm=172,
            molestias="Una llaga en la lengua que no cierra.",
        )
        usuario = crear_paciente("pro@test.cl", rol=Usuario.Rol.PROFESIONAL)
        self.profesional = Profesional.objects.create(
            usuario=usuario,
            registro="99",
            especialidad="Odontología",
            centro="Centro",
            comuna="Viña del Mar",
            verificado=True,
        )
        inicio = timezone.now() + timedelta(days=2)
        horario = Horario.objects.create(
            profesional=self.profesional,
            inicio=inicio,
            fin=inicio + timedelta(minutes=30),
            estado=Horario.Estado.RESERVADO,
        )
        self.cita = Cita.objects.create(
            paciente=self.paciente,
            horario=horario,
            estado=Cita.Estado.CONFIRMADA,
        )
        self.client.force_login(usuario)

    def test_con_cita_vigente_el_profesional_ve_la_ficha(self):
        respuesta = self.client.get(reverse("cuentas:inicio"))
        self.assertContains(respuesta, "llaga")
        self.assertContains(respuesta, "172 cm")

    def test_sin_cita_vigente_el_profesional_no_ve_la_ficha(self):
        self.cita.estado = self.Cita.Estado.CANCELADA
        self.cita.save()
        respuesta = self.client.get(reverse("cuentas:inicio"))
        self.assertNotContains(respuesta, "llaga")

    def test_otro_profesional_no_ve_la_ficha(self):
        otro = crear_paciente("otro@test.cl", rol=Usuario.Rol.PROFESIONAL)
        Profesional.objects.create(
            usuario=otro,
            registro="100",
            especialidad="Odontología",
            centro="Otro",
            comuna="Valparaíso",
            verificado=True,
        )
        self.client.force_login(otro)
        respuesta = self.client.get(reverse("cuentas:inicio"))
        self.assertNotContains(respuesta, "llaga")


class UbicacionDeLaConsultaTests(TestCase):
    """El enlace al mapa es lo único que el paciente no escribe a mano."""

    def crear(self, **cambios):
        datos = {
            "registro": "999",
            "especialidad": "Odontología",
            "centro": "Clínica Viña",
            "comuna": "Viña del Mar",
        }
        datos.update(cambios)
        return Profesional(
            usuario=Usuario(first_name="Luz", last_name="Soto"),
            **datos,
        )

    def test_la_ubicacion_va_de_lo_preciso_a_lo_general(self):
        profesional = self.crear(direccion="Av. Libertad 1348")
        self.assertEqual(
            profesional.ubicacion,
            "Av. Libertad 1348, Clínica Viña, Viña del Mar",
        )

    def test_sin_direccion_la_ubicacion_no_deja_comas_sueltas(self):
        self.assertEqual(self.crear().ubicacion, "Clínica Viña, Viña del Mar")

    def test_el_enlace_codifica_los_espacios_y_los_acentos(self):
        """Una dirección sin codificar rompe la URL y el mapa cae en otro lugar."""
        enlace = self.crear(direccion="Av. Libertad 1348").enlace_mapa
        self.assertTrue(enlace.startswith("https://www.google.com/maps/dir/?api=1&destination="))
        self.assertNotIn(" ", enlace)
        self.assertIn("Libertad+1348", enlace)
        self.assertIn("Vi%C3%B1a", enlace)

    def test_el_enlace_acota_la_busqueda_al_pais(self):
        """Hay comunas chilenas con el mismo nombre en otros países."""
        self.assertTrue(self.crear().enlace_mapa.endswith("%2C+Chile"))

    def test_sin_direccion_el_enlace_sigue_sirviendo(self):
        """Menos preciso, pero el centro y la comuna suelen bastar."""
        enlace = self.crear().enlace_mapa
        self.assertIn("Cl%C3%ADnica+Vi%C3%B1a", enlace)


class MiConsultaTests(TestCase):
    def setUp(self):
        usuario = crear_paciente("pro@test.cl", rol=Usuario.Rol.PROFESIONAL)
        self.profesional = Profesional.objects.create(
            usuario=usuario,
            registro="555",
            especialidad="Odontología",
            centro="Clínica Viña",
            comuna="Viña del Mar",
            verificado=True,
        )
        self.client.force_login(usuario)
        self.url = reverse("cuentas:mi_consulta")

    def test_el_profesional_guarda_donde_atiende(self):
        respuesta = self.client.post(
            self.url,
            {
                "centro": "Clínica Viña",
                "comuna": "Viña del Mar",
                "direccion": "Av. Libertad 1348",
                "como_llegar": "Piso 3, oficina 302",
            },
        )
        self.assertRedirects(respuesta, reverse("cuentas:inicio"))
        self.profesional.refresh_from_db()
        self.assertEqual(self.profesional.direccion, "Av. Libertad 1348")
        self.assertTrue(self.profesional.tiene_direccion)

    def test_sin_direccion_el_panel_se_lo_recuerda(self):
        respuesta = self.client.get(reverse("cuentas:inicio"))
        self.assertContains(respuesta, "No has puesto la dirección")

    def test_con_direccion_el_panel_no_insiste(self):
        self.profesional.direccion = "Av. Libertad 1348"
        self.profesional.save()
        respuesta = self.client.get(reverse("cuentas:inicio"))
        self.assertNotContains(respuesta, "No has puesto la dirección")

    def test_el_paciente_no_entra_a_mi_consulta(self):
        self.client.force_login(crear_paciente("otra@test.cl"))
        respuesta = self.client.get(self.url)
        self.assertRedirects(respuesta, reverse("cuentas:inicio"))
