"""Datos para el gráfico de evolución del riesgo.

El nivel de riesgo es una escala *ordinal* de tres posiciones, no una medida
continua: el modelo calcula una probabilidad pero el proyecto solo guarda el
nivel. Por eso el eje vertical tiene tres posiciones con nombre y no un
porcentaje. Si algún día se guarda la probabilidad, este módulo es el único
que habría que tocar.

Todo se expresa en porcentajes del área de dibujo. Así el SVG solo lleva la
geometría (bandas y línea) y las etiquetas y los puntos son HTML colocado por
CSS: la tipografía mantiene su tamaño sea cual sea el ancho del gráfico, en
vez de encogerse con él.

Los porcentajes salen como texto con punto decimal a propósito. Si fueran
números, Django los formatearía según el idioma y con es-cl escribiría
"76,0", que ni CSS ni SVG entienden.
"""

from .models import Evaluacion

# Posición vertical de cada nivel. Arriba es peor, que es como se lee.
NIVELES = [
    (Evaluacion.NivelRiesgo.ALTO, "Alto"),
    (Evaluacion.NivelRiesgo.MODERADO, "Moderado"),
    (Evaluacion.NivelRiesgo.BAJO, "Bajo"),
]
POSICION = {codigo: fila for fila, (codigo, _) in enumerate(NIVELES)}

# Margen horizontal para que el primer y el último punto no queden al filo.
MARGEN_PCT = 6.0

MINIMO_PARA_GRAFICAR = 2


def _pct(valor):
    """Porcentaje listo para un atributo: punto decimal, sin localizar."""
    return f"{valor:.2f}"


def _y_centro(fila):
    """Centro vertical de la banda, en porcentaje del alto."""
    return (100.0 / len(NIVELES)) * (fila + 0.5)


def _x(indice, total):
    if total == 1:
        return 50.0
    util = 100.0 - 2 * MARGEN_PCT
    return MARGEN_PCT + util * indice / (total - 1)


def evolucion(evaluaciones):
    """Lo que la plantilla necesita, o None si no hay con qué graficar.

    `evaluaciones` llega de la más reciente a la más antigua; el gráfico las
    muestra en orden cronológico, que es como se lee una evolución.
    """
    con_riesgo = [e for e in evaluaciones if e.riesgo]
    if len(con_riesgo) < MINIMO_PARA_GRAFICAR:
        return None

    cronologico = list(reversed(con_riesgo))
    total = len(cronologico)

    puntos = []
    for i, ev in enumerate(cronologico):
        puntos.append({
            "evaluacion": ev,
            "x": _pct(_x(i, total)),
            "y": _pct(_y_centro(POSICION[ev.riesgo])),
            "riesgo": ev.riesgo,
            "etiqueta": ev.get_riesgo_display(),
            "fecha": ev.fecha,
            "ultimo": i == total - 1,
        })

    alto_banda = 100.0 / len(NIVELES)
    bandas = [
        {
            "codigo": codigo,
            "nombre": nombre,
            "y": _pct(alto_banda * fila),
            "alto": _pct(alto_banda),
        }
        for fila, (codigo, nombre) in enumerate(NIVELES)
    ]

    primero, ultimo = cronologico[0], cronologico[-1]
    if POSICION[ultimo.riesgo] < POSICION[primero.riesgo]:
        tendencia = "subio"
    elif POSICION[ultimo.riesgo] > POSICION[primero.riesgo]:
        tendencia = "bajo"
    else:
        tendencia = "igual"

    return {
        "puntos": puntos,
        "bandas": bandas,
        # Extremos de la escala recorrida: es el "delta" de una escala
        # ordinal, y lo que permite leer la chispa sin ejes.
        "desde": primero.get_riesgo_display(),
        "hasta": ultimo.get_riesgo_display(),
        "linea": " ".join(f"{p['x']},{p['y']}" for p in puntos),
        "tendencia": tendencia,
        "total": total,
    }
