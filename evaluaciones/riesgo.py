from .models import Evaluacion

UMBRAL_MODERADO = 0.30
UMBRAL_ALTO = 0.50


def nivel_de_riesgo(probabilidad):
    if probabilidad >= UMBRAL_ALTO:
        return Evaluacion.NivelRiesgo.ALTO
    if probabilidad >= UMBRAL_MODERADO:
        return Evaluacion.NivelRiesgo.MODERADO
    return Evaluacion.NivelRiesgo.BAJO
