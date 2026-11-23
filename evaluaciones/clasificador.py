import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as TiempoAgotado

TIEMPO_MAXIMO_SEGUNDOS = 10

logger = logging.getLogger(__name__)
_ejecutor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="clasificador")


class ClasificacionNoCompletada(Exception):
    pass


def _probabilidad(imagen_bytes):
    from ia.predict import predict

    return predict(imagen_bytes)["probabilities"]["cancer"]


def precargar_modelo():
    try:
        from ia.predict import predict
        from PIL import Image
        import io

        muestra = io.BytesIO()
        Image.new("RGB", (232, 232), (150, 90, 90)).save(muestra, format="PNG")
        predict(muestra.getvalue())
        logger.info("Modelo de IA cargado y listo.")
    except Exception:
        logger.exception("No se pudo precargar el modelo de IA.")


def probabilidad_de_riesgo(imagen_bytes):
    futuro = _ejecutor.submit(_probabilidad, imagen_bytes)
    try:
        return futuro.result(timeout=TIEMPO_MAXIMO_SEGUNDOS)
    except TiempoAgotado as error:
        raise ClasificacionNoCompletada("El análisis superó el tiempo máximo.") from error
    except Exception as error:
        logger.exception("Falló la clasificación de la imagen.")
        raise ClasificacionNoCompletada("El análisis no pudo completarse.") from error
