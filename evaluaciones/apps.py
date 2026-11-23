import os
import sys
import threading

from django.apps import AppConfig


class EvaluacionesConfig(AppConfig):
    name = 'evaluaciones'

    def ready(self):
        es_servidor = "runserver" in sys.argv
        es_proceso_principal = os.environ.get("RUN_MAIN") == "true" or "--noreload" in sys.argv
        if es_servidor and es_proceso_principal:
            from .clasificador import precargar_modelo

            threading.Thread(target=precargar_modelo, daemon=True).start()
