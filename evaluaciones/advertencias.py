from .models import Evaluacion

AVISO_ORIENTATIVO = (
    "Este resultado es orientativo y no constituye un diagnóstico. "
    "Solo un profesional de la salud oral puede confirmar o descartar una lesión."
)

ADVERTENCIAS = {
    Evaluacion.NivelRiesgo.BAJO: {
        "titulo": "Riesgo bajo",
        "resumen": "No se observaron señales de alerta en esta fotografía.",
        "destacado": "",
        "recomendaciones": [
            "Mantén tu higiene bucal: cepíllate después de cada comida y usa hilo dental.",
            "Haz una nueva evaluación si notas una herida, mancha o bulto que no sana en dos semanas.",
            "Visita a tu dentista para un control al menos una vez al año.",
        ],
    },
    Evaluacion.NivelRiesgo.MODERADO: {
        "titulo": "Riesgo moderado",
        "resumen": "Se observaron algunas características que conviene revisar con un profesional.",
        "destacado": "",
        "recomendaciones": [
            "Agenda una consulta con un profesional de la salud oral en las próximas semanas.",
            "Observa si la zona cambia de color o tamaño, sangra o duele.",
            "Evita el tabaco y el alcohol, porque aumentan el riesgo de lesiones en la boca.",
        ],
    },
    Evaluacion.NivelRiesgo.ALTO: {
        "titulo": "Riesgo alto",
        "resumen": "Se observaron características que requieren la evaluación de un profesional.",
        "destacado": "Agenda una cita con un profesional de la salud oral lo antes posible.",
        "recomendaciones": [
            "No esperes a sentir dolor u otros síntomas para consultar.",
            "Muestra esta evaluación en tu consulta.",
            "Evita el tabaco y el alcohol mientras te atienden.",
        ],
    },
}


def advertencias_para(nivel):
    return ADVERTENCIAS[nivel]


def generar_reporte(nivel):
    advertencias = advertencias_para(nivel)
    lineas = [advertencias["titulo"], advertencias["resumen"]]
    if advertencias["destacado"]:
        lineas.append(advertencias["destacado"])
    lineas.extend(f"- {recomendacion}" for recomendacion in advertencias["recomendaciones"])
    lineas.append(AVISO_ORIENTATIVO)
    return "\n".join(lineas)
