import io
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageOps

LUMINANCIA_MINIMA = 60
LUMINANCIA_MAXIMA = 200
NITIDEZ_MINIMA = 100
LADO_MAXIMO = 1024


@dataclass(frozen=True)
class Problema:
    motivo: str
    consejo: str


POCA_LUZ = Problema(
    "Iluminación insuficiente",
    "La foto está muy oscura. Busca un lugar con más luz o usa la linterna del teléfono.",
)
MUCHA_LUZ = Problema(
    "Exceso de iluminación",
    "La foto tiene demasiada luz. Evita el flash directo o la luz del sol de frente.",
)
POCA_NITIDEZ = Problema(
    "Falta de nitidez",
    "La foto está borrosa. Mantén el teléfono quieto y espera a que enfoque antes de tomarla.",
)


@dataclass
class ResultadoCalidad:
    luminancia: float
    nitidez: float
    problemas: list = field(default_factory=list)

    @property
    def aprobada(self):
        return not self.problemas

    @property
    def motivo(self):
        return "; ".join(problema.motivo for problema in self.problemas)


def evaluar_calidad(imagen_bytes):
    with Image.open(io.BytesIO(imagen_bytes)) as imagen:
        gris = ImageOps.exif_transpose(imagen).convert("L")
    gris.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    matriz = np.asarray(gris, dtype=np.uint8)

    luminancia = float(matriz.mean())
    nitidez = float(cv2.Laplacian(matriz, cv2.CV_64F).var())

    problemas = []
    if luminancia < LUMINANCIA_MINIMA:
        problemas.append(POCA_LUZ)
    elif luminancia > LUMINANCIA_MAXIMA:
        problemas.append(MUCHA_LUZ)
    if nitidez < NITIDEZ_MINIMA:
        problemas.append(POCA_NITIDEZ)

    return ResultadoCalidad(luminancia=luminancia, nitidez=nitidez, problemas=problemas)
