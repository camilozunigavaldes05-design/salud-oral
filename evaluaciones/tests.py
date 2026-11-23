import importlib.util
import io
import shutil
import tempfile
import time
from unittest import mock, skipUnless

import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from cuentas.models import Profesional, Usuario

from . import clasificador
from .advertencias import generar_reporte
from .calidad import evaluar_calidad
from .clasificador import ClasificacionNoCompletada
from .models import Consentimiento, Evaluacion
from .riesgo import nivel_de_riesgo

CLAVE = "clave1234"
TORCH_DISPONIBLE = importlib.util.find_spec("torch") is not None


def imagen_bytes(tipo="buena", formato="JPEG", lado=320):
    generador = np.random.default_rng(42)
    if tipo == "buena":
        pixeles = generador.integers(60, 200, (lado, lado, 3))
    elif tipo == "oscura":
        pixeles = generador.integers(0, 40, (lado, lado, 3))
    elif tipo == "brillante":
        pixeles = generador.integers(225, 256, (lado, lado, 3))
    elif tipo == "borrosa":
        pixeles = np.full((lado, lado, 3), 128)
    else:
        raise ValueError(tipo)
    salida = io.BytesIO()
    Image.fromarray(pixeles.astype(np.uint8)).save(salida, format=formato)
    return salida.getvalue()


def archivo(tipo="buena", formato="JPEG", nombre=None):
    extension = {"JPEG": "jpg", "PNG": "png", "GIF": "gif"}[formato]
    return SimpleUploadedFile(
        nombre or f"foto.{extension}",
        imagen_bytes(tipo, formato),
        content_type=f"image/{extension}",
    )


class CalidadTests(TestCase):
    def test_ca01_imagen_correcta_es_aprobada(self):
        resultado = evaluar_calidad(imagen_bytes("buena"))
        self.assertTrue(resultado.aprobada)
        self.assertTrue(60 <= resultado.luminancia <= 200)
        self.assertGreaterEqual(resultado.nitidez, 100)

    def test_ca02_imagen_oscura_es_rechazada(self):
        resultado = evaluar_calidad(imagen_bytes("oscura"))
        self.assertFalse(resultado.aprobada)
        self.assertIn("Iluminación insuficiente", resultado.motivo)

    def test_ca02_imagen_con_exceso_de_luz_es_rechazada(self):
        resultado = evaluar_calidad(imagen_bytes("brillante"))
        self.assertFalse(resultado.aprobada)
        self.assertIn("Exceso de iluminación", resultado.motivo)

    def test_ca02_imagen_borrosa_es_rechazada(self):
        resultado = evaluar_calidad(imagen_bytes("borrosa"))
        self.assertFalse(resultado.aprobada)
        self.assertIn("Falta de nitidez", resultado.motivo)

    def test_ca04_validacion_tarda_menos_de_2_segundos(self):
        salida = io.BytesIO()
        Image.fromarray(
            np.random.default_rng(1).integers(60, 200, (3000, 4000, 3)).astype(np.uint8)
        ).save(salida, format="JPEG")
        inicio = time.perf_counter()
        evaluar_calidad(salida.getvalue())
        self.assertLess(time.perf_counter() - inicio, 2)


class RiesgoTests(TestCase):
    def test_probabilidades_se_convierten_en_niveles(self):
        casos = {
            0.0: "BAJO",
            0.29: "BAJO",
            0.30: "MODERADO",
            0.49: "MODERADO",
            0.50: "ALTO",
            0.97: "ALTO",
        }
        for probabilidad, esperado in casos.items():
            with self.subTest(probabilidad=probabilidad):
                self.assertEqual(nivel_de_riesgo(probabilidad), esperado)

    def test_ca02_reporte_incluye_advertencias_y_aviso_orientativo(self):
        for nivel in Evaluacion.NivelRiesgo.values:
            with self.subTest(nivel=nivel):
                reporte = generar_reporte(nivel)
                self.assertIn("orientativo", reporte)
                self.assertNotIn("cáncer", reporte.lower())


class ClasificadorTests(TestCase):
    def test_tiempo_maximo_marca_no_completada(self):
        def lento(_):
            time.sleep(1)
            return 0.1

        with mock.patch.object(clasificador, "_probabilidad", lento), \
                mock.patch.object(clasificador, "TIEMPO_MAXIMO_SEGUNDOS", 0.1):
            with self.assertRaises(ClasificacionNoCompletada):
                clasificador.probabilidad_de_riesgo(b"imagen")

    def test_error_de_la_ia_marca_no_completada(self):
        def falla(_):
            raise RuntimeError("modelo no disponible")

        with mock.patch.object(clasificador, "_probabilidad", falla), \
                self.assertLogs("evaluaciones.clasificador", level="ERROR"):
            with self.assertRaises(ClasificacionNoCompletada):
                clasificador.probabilidad_de_riesgo(b"imagen")


class BaseEvaluacionTests(TestCase):
    def setUp(self):
        self.carpeta = tempfile.mkdtemp()
        ajustes = override_settings(ALMACENAMIENTO_PRIVADO=self.carpeta)
        ajustes.enable()
        self.addCleanup(ajustes.disable)
        self.addCleanup(shutil.rmtree, self.carpeta, ignore_errors=True)

        self.paciente = Usuario.objects.create_user(
            "paciente@test.cl", CLAVE, first_name="Ana", last_name="Pérez"
        )
        self.client.force_login(self.paciente)

        parche = mock.patch("evaluaciones.servicios.probabilidad_de_riesgo", return_value=0.1)
        self.ia = parche.start()
        self.addCleanup(parche.stop)

    def enviar(self, acepta=True, **kwargs):
        datos = {"imagen": kwargs.pop("imagen", None) or archivo(**kwargs)}
        if acepta:
            datos["acepta"] = "on"
        return self.client.post(reverse("evaluaciones:nueva"), datos)


class NuevaEvaluacionTests(BaseEvaluacionTests):
    def test_rf02_ca01_jpeg_es_recibido_y_analizado(self):
        respuesta = self.enviar()
        evaluacion = Evaluacion.objects.get()
        self.assertRedirects(respuesta, reverse("evaluaciones:detalle", args=[evaluacion.pk]))
        self.assertEqual(evaluacion.estado, Evaluacion.Estado.REPORTE_DISPONIBLE)
        self.assertEqual(evaluacion.mime, "image/jpeg")
        self.assertTrue(evaluacion.calidad_aprobada)

    def test_rf02_ca01_png_es_recibido(self):
        self.enviar(formato="PNG")
        self.assertEqual(Evaluacion.objects.get().mime, "image/png")

    def test_rf02_ca05_otro_formato_es_rechazado(self):
        respuesta = self.enviar(formato="GIF")
        self.assertContains(respuesta, "Formato no permitido")
        self.assertFalse(Evaluacion.objects.exists())

    def test_rf02_ca05_archivo_que_no_es_imagen_es_rechazado(self):
        falso = SimpleUploadedFile("foto.jpg", b"esto no es una imagen", content_type="image/jpeg")
        respuesta = self.enviar(imagen=falso)
        self.assertContains(respuesta, "no es una imagen válida")
        self.assertFalse(Evaluacion.objects.exists())

    def test_rf02_ca05_archivo_mayor_a_10_mb_es_rechazado(self):
        grande = SimpleUploadedFile(
            "foto.jpg",
            imagen_bytes() + b"0" * (10 * 1024 * 1024),
            content_type="image/jpeg",
        )
        respuesta = self.enviar(imagen=grande)
        self.assertContains(respuesta, "pesa más de 10 MB")
        self.assertFalse(Evaluacion.objects.exists())

    def test_rn01_sin_aceptar_el_aviso_no_se_inicia_la_evaluacion(self):
        respuesta = self.enviar(acepta=False)
        self.assertContains(respuesta, "Debes aceptar este aviso")
        self.assertFalse(Evaluacion.objects.exists())
        self.assertFalse(Consentimiento.objects.exists())
        self.ia.assert_not_called()

    def test_consentimiento_queda_registrado(self):
        self.enviar()
        consentimiento = Consentimiento.objects.get()
        self.assertEqual(consentimiento.paciente, self.paciente)
        self.assertEqual(Evaluacion.objects.get().consentimiento, consentimiento)

    def test_rn02_foto_oscura_no_se_envia_a_la_ia(self):
        respuesta = self.enviar(tipo="oscura")
        self.assertContains(respuesta, "La foto está muy oscura")
        self.ia.assert_not_called()
        evaluacion = Evaluacion.objects.get()
        self.assertEqual(evaluacion.estado, Evaluacion.Estado.RECHAZADA_POR_CALIDAD)
        self.assertEqual(evaluacion.motivo_rechazo, "Iluminación insuficiente")
        self.assertEqual(evaluacion.imagen_uri, "")

    def test_rn02_foto_borrosa_no_se_envia_a_la_ia(self):
        respuesta = self.enviar(tipo="borrosa")
        self.assertContains(respuesta, "La foto está borrosa")
        self.ia.assert_not_called()

    def test_imagen_se_guarda_fuera_de_la_carpeta_publica(self):
        self.enviar()
        evaluacion = Evaluacion.objects.get()
        self.assertTrue(evaluacion.imagen_uri.startswith(f"pacientes/{self.paciente.pk}/"))


class ReporteTests(BaseEvaluacionTests):
    def crear_con_probabilidad(self, probabilidad):
        self.ia.return_value = probabilidad
        self.enviar()
        evaluacion = Evaluacion.objects.latest("pk")
        return evaluacion, self.client.get(reverse("evaluaciones:detalle", args=[evaluacion.pk]))

    def test_rf04_ca01_riesgo_bajo(self):
        evaluacion, respuesta = self.crear_con_probabilidad(0.1)
        self.assertEqual(evaluacion.riesgo, Evaluacion.NivelRiesgo.BAJO)
        self.assertContains(respuesta, "Riesgo bajo")
        self.assertNotContains(respuesta, 'class="destacado-alto"')

    def test_rf04_ca01_riesgo_moderado(self):
        evaluacion, respuesta = self.crear_con_probabilidad(0.4)
        self.assertEqual(evaluacion.riesgo, Evaluacion.NivelRiesgo.MODERADO)
        self.assertContains(respuesta, "Riesgo moderado")

    def test_rf04_ca03_riesgo_alto_destaca_agendar_cita(self):
        evaluacion, respuesta = self.crear_con_probabilidad(0.9)
        self.assertEqual(evaluacion.riesgo, Evaluacion.NivelRiesgo.ALTO)
        self.assertContains(respuesta, 'class="destacado-alto"')
        self.assertContains(respuesta, "Agenda una cita con un profesional")

    def test_rf04_ca02_reporte_es_orientativo_y_no_menciona_cancer(self):
        evaluacion, respuesta = self.crear_con_probabilidad(0.9)
        self.assertContains(respuesta, "no constituye un diagnóstico")
        self.assertNotIn("cáncer", respuesta.content.decode().lower())
        self.assertNotIn("cancer", respuesta.content.decode().lower())
        self.assertIn("orientativo", evaluacion.reporte)

    def test_fallo_de_la_ia_deja_no_completada_y_permite_reintentar(self):
        self.ia.side_effect = ClasificacionNoCompletada("falla")
        self.enviar()
        evaluacion = Evaluacion.objects.get()
        self.assertEqual(evaluacion.estado, Evaluacion.Estado.NO_COMPLETADA)
        respuesta = self.client.get(reverse("evaluaciones:detalle", args=[evaluacion.pk]))
        self.assertContains(respuesta, "Reintentar el análisis")

        self.ia.side_effect = None
        self.ia.return_value = 0.2
        self.client.post(reverse("evaluaciones:reintentar", args=[evaluacion.pk]))
        evaluacion.refresh_from_db()
        self.assertEqual(evaluacion.estado, Evaluacion.Estado.REPORTE_DISPONIBLE)
        self.assertEqual(evaluacion.riesgo, Evaluacion.NivelRiesgo.BAJO)

    def test_imagen_se_muestra_a_su_dueno(self):
        evaluacion, _ = self.crear_con_probabilidad(0.1)
        respuesta = self.client.get(reverse("evaluaciones:imagen", args=[evaluacion.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "image/jpeg")
        self.assertIn("no-store", respuesta["Cache-Control"])


class HistorialTests(BaseEvaluacionTests):
    def setUp(self):
        super().setUp()
        self.otro = Usuario.objects.create_user(
            "otro@test.cl", CLAVE, first_name="Beto", last_name="Rojas"
        )

    def test_rf05_ca01_evaluacion_aparece_en_el_historial(self):
        self.enviar()
        respuesta = self.client.get(reverse("evaluaciones:historial"))
        self.assertContains(respuesta, "Riesgo bajo")

    def test_rf05_ca02_paciente_solo_ve_sus_propios_reportes(self):
        self.enviar()
        propia = Evaluacion.objects.get()
        self.client.force_login(self.otro)
        respuesta = self.client.get(reverse("evaluaciones:historial"))
        self.assertContains(respuesta, "Aún no tienes evaluaciones")
        for nombre in ("detalle", "imagen"):
            with self.subTest(vista=nombre):
                respuesta = self.client.get(reverse(f"evaluaciones:{nombre}", args=[propia.pk]))
                self.assertEqual(respuesta.status_code, 404)

    def test_fotos_rechazadas_no_aparecen_en_el_historial(self):
        self.enviar(tipo="oscura")
        respuesta = self.client.get(reverse("evaluaciones:historial"))
        self.assertContains(respuesta, "Aún no tienes evaluaciones")

    def test_historial_en_orden_cronologico_descendente(self):
        self.enviar()
        self.ia.return_value = 0.9
        self.enviar()
        primera, segunda = Evaluacion.objects.order_by("pk")
        respuesta = self.client.get(reverse("evaluaciones:historial"))
        self.assertEqual(list(respuesta.context["evaluaciones"]), [segunda, primera])


class PermisosTests(BaseEvaluacionTests):
    def test_visitante_debe_iniciar_sesion(self):
        self.client.logout()
        respuesta = self.client.get(reverse("evaluaciones:nueva"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("cuentas:login"), respuesta["Location"])

    def test_profesional_no_usa_las_paginas_de_paciente(self):
        profesional = Usuario.objects.create_user(
            "pro@test.cl", CLAVE, first_name="Pro", last_name="Fesional",
            rol=Usuario.Rol.PROFESIONAL,
        )
        Profesional.objects.create(
            usuario=profesional, registro="1", especialidad="Odontología",
            centro="Centro", comuna="Viña del Mar",
        )
        self.client.force_login(profesional)
        for nombre in ("nueva", "historial"):
            with self.subTest(vista=nombre):
                respuesta = self.client.get(reverse(f"evaluaciones:{nombre}"))
                self.assertEqual(respuesta.status_code, 403)

    def test_reintentar_exige_post(self):
        self.enviar()
        evaluacion = Evaluacion.objects.get()
        respuesta = self.client.get(reverse("evaluaciones:reintentar", args=[evaluacion.pk]))
        self.assertEqual(respuesta.status_code, 405)


@skipUnless(TORCH_DISPONIBLE, "PyTorch no está instalado")
class ModeloRealTests(TestCase):
    def test_modelo_real_entrega_una_probabilidad_valida(self):
        probabilidad = clasificador.probabilidad_de_riesgo(imagen_bytes("buena"))
        self.assertGreaterEqual(probabilidad, 0)
        self.assertLessEqual(probabilidad, 1)

    def test_modelo_real_responde_en_menos_de_10_segundos(self):
        clasificador.probabilidad_de_riesgo(imagen_bytes("buena"))
        inicio = time.perf_counter()
        clasificador.probabilidad_de_riesgo(imagen_bytes("buena", formato="PNG"))
        self.assertLess(time.perf_counter() - inicio, 10)
