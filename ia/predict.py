"""
Inferencia pura para SaludOral-IA (etapa 9).

Modulo sin Django, sin acceso a base de datos y sin red: su unica frontera es
    entrada:  bytes de una imagen
    salida:   dict JSON-serializable (contrato de abajo)
    errores:  excepciones de dominio (InvalidImageError, CheckpointIntegrityError)

Decisiones aprobadas para esta etapa (docs/etapa9_inferencia.md):
- TorchScript: el runtime principal carga el checkpoint directo; el artefacto
  exportado (models/export/) es opcional y no lo consume este modulo.
- EXIF: se aplica ImageOps.exif_transpose() ANTES del resto del preprocesado.
  Es la UNICA diferencia deliberada frente al protocolo de evaluacion
  (etapas 7/8b), declarada porque las fotos reales de la aplicacion llevan
  orientacion EXIF y las del dataset (Kaggle) no.
- timestamp: NO forma parte del core (predict() es determinista: misma imagen
  -> mismo dict). La marca temporal la genera la capa que integre (p. ej.
  columna created_at en PostgreSQL).
- Umbral: parametro con default 0.5. A 0.5 la regla "cancer si
  prob_cancer >= threshold" equivale a argmax. Cualquier otro valor seria una
  nueva configuracion y deberia documentarse como tal (nunca elegido mirando
  test).
- Device: default CPU (entorno de integracion sin GPU); disponible como
  parametro para pruebas con GPU. CPU y CUDA pueden diferir en el orden de
  1e-6 en las probabilidades.

Convencion fija del proyecto: indice 0 = "cancer" (clase positiva),
indice 1 = "non-cancer"; probabilidad de cancer = softmax[:, 0].

Contrato de salida:
    {
      "label": "cancer" | "non-cancer",
      "probabilities": {"cancer": 0.83, "non-cancer": 0.17},  # 6 decimales
      "predicted_class_index": 0,             # 0 = cancer, 1 = non-cancer
      "threshold": 0.5,
      "model": {
        "arch": "efficientnet_b0", "epoch": 5, "phase": 1,
        "run_name": "efficientnet_b0", "sha256": "...",
        "model_version": "efficientnet_b0-ep5",
        "val_loss_entrenamiento": 0.250757
      },
      "disclaimer": "Resultado orientativo experimental; no es un diagnostico medico."
    }

La decision (cancer/non-cancer) se toma sobre la probabilidad REDONDEADA a 6
decimales para que el dict sea autoconsistente (label coherente con las
probabilidades y el threshold que el propio dict muestra). Con probabilidad
sin redondear la diferencia solo apareceria en casos frontera ~1e-6.

Carga del checkpoint (misma politica que evaluate.py, etapa 8b):
- Solo se aceptan checkpoints registrados en EXPECTED_CHECKPOINTS (por ruta
  relativa). El SHA-256 debe coincidir exactamente con el congelado; en caso
  contrario se lanza CheckpointIntegrityError.
- Primero torch.load(..., weights_only=True). Si falla (tipo no permitido),
  el fallback weights_only=False SOLO se ejecuta tras haber verificado el
  SHA-256 contra el valor congelado; checkpoints no registrados nunca tienen
  fallback.

Ejecucion (smoke, desde la raiz):
    python -m ia.predict --image <ruta.jpg>
"""

from __future__ import annotations

import hashlib
import io
import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import torch
from PIL import Image, ImageOps, UnidentifiedImageError

from ia.transforms import build_eval_transform_from_config
from ia.model import build_model

ROOT = Path(__file__).resolve().parents[1]

CLASSES = ("cancer", "non-cancer")  # 0 = cancer (positiva), 1 = non-cancer
DEFAULT_CHECKPOINT_REL = "ia/modelos/best_efficientnet_b0.pt"
DEFAULT_THRESHOLD = 0.5
DEFAULT_DEVICE = "cpu"
SEED = 42
MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB
DISCLAIMER = "Resultado orientativo experimental; no es un diagnostico medico."

# Checkpoints congelados con SHA-256 y metadatos exactos (misma fuente que
# evaluate.py, etapa 8b). La inferencia SOLO acepta checkpoints registrados
# aqui y con SHA-256 coincidente.
EXPECTED_CHECKPOINTS = {
    "ia/modelos/best_efficientnet_b0.pt": {
        "sha256": "986e902468dd25f27c8b2cffaf29434f0ada8b4673bf6508ff36356c544fd6d5",
        "arch": "efficientnet_b0",
        "run_name": "efficientnet_b0",
        "epoch": 5,
        "phase": 1,
    },
}


class InvalidImageError(ValueError):
    """Los bytes de entrada no forman una imagen valida o superan el limite de tamano."""


class CheckpointIntegrityError(RuntimeError):
    """El checkpoint no esta registrado, su SHA-256 no coincide o sus metadatos son inesperados."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Preprocesado de la imagen (antes del transform del checkpoint)
# --------------------------------------------------------------------------- #

def load_image_rgb(image_bytes: bytes) -> Image.Image:
    """Bytes -> PIL RGB, con EXIF transpose y fondo blanco si hay transparencia.

    Orden deliberado: 1) EXIF transpose (orientacion de fotos de movil),
    2) conversion a RGB con composite sobre blanco cuando hay canal alfa.
    El resultado entra al transform de evaluacion reconstruido desde el
    checkpoint (Resize -> CenterCrop -> ToTensor -> Normalize).
    """
    if len(image_bytes) == 0:
        raise InvalidImageError("imagen vacia: 0 bytes")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise InvalidImageError(
            f"imagen demasiado grande: {len(image_bytes)} bytes "
            f"(maximo {MAX_IMAGE_BYTES})"
        )
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise InvalidImageError(f"los bytes no decodifican como imagen: {e}") from e

    # aprobado etapa 9: orientacion EXIF aplicada y declarada
    img = ImageOps.exif_transpose(img)

    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return img.convert("RGB")


# --------------------------------------------------------------------------- #
# Predictor
# --------------------------------------------------------------------------- #

class Predictor:
    """Carga el checkpoint una vez (preflight incluido) y predice muchas veces.

    Inmutable tras __init__. Seguro para lectura concurrente en Django
    (model.eval() + torch.inference_mode() no mutan estado); el singleton de
    predict() usa un Lock solo para la inicializacion perezosa.
    """

    def __init__(
        self,
        checkpoint_path: str | Path = DEFAULT_CHECKPOINT_REL,
        device: str = DEFAULT_DEVICE,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        if not (0.0 < threshold < 1.0):
            raise ValueError(f"threshold debe estar en (0, 1); recibido {threshold!r}")

        self.device = torch.device(device)
        self.threshold = float(threshold)

        # ruta relativa a la raiz (para el registro) o absoluta tal cual
        path = Path(checkpoint_path)
        if path.is_absolute():
            self.checkpoint_path = path
            ckpt_rel = None
        else:
            self.checkpoint_path = ROOT / path
            ckpt_rel = path.as_posix()
        # 1) registro primero (autorizacion antes de cualquier I/O) y despues
        #    existencia; luego SHA-256 congelado (patron evaluate.py, etapa 8b)
        if ckpt_rel not in EXPECTED_CHECKPOINTS:
            raise CheckpointIntegrityError(
                f"checkpoint no registrado en EXPECTED_CHECKPOINTS: {ckpt_rel}. "
                "La inferencia solo acepta checkpoints con SHA-256 congelado."
            )
        if not self.checkpoint_path.exists():
            raise CheckpointIntegrityError(f"no existe el checkpoint {self.checkpoint_path}")
        spec = EXPECTED_CHECKPOINTS[ckpt_rel]
        ck_sha = sha256_file(self.checkpoint_path)
        if ck_sha != spec["sha256"]:
            raise CheckpointIntegrityError(
                f"SHA-256 de {ckpt_rel} no coincide con el congelado.\n"
                f"  esperado: {spec['sha256']}\n  actual:   {ck_sha}"
            )
        self.sha256 = ck_sha

        # 2) carga: weights_only=True primero; fallback weights_only=False
        #    SOLO con el SHA ya verificado contra el congelado
        try:
            ck = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)
            self.load_mode = "weights_only=True"
        except Exception:
            ck = torch.load(self.checkpoint_path, map_location="cpu", weights_only=False)
            self.load_mode = "weights_only=False (fallback; SHA-256 verificado)"

        # 3) sanity generico de metadatos (idempotente con el registro)
        meta_ok = (
            ck.get("classes") == list(CLASSES)
            and ck.get("positive_class") == "cancer"
            and ck.get("seed") == SEED
            and isinstance(ck.get("epoch"), int)
            and ck.get("phase") in (1, 2)
        )
        if not meta_ok:
            raise CheckpointIntegrityError(
                f"metadatos inesperados en {ckpt_rel}: classes={ck.get('classes')} "
                f"positive={ck.get('positive_class')} seed={ck.get('seed')} "
                f"epoch={ck.get('epoch')} phase={ck.get('phase')}"
            )
        for campo in ("arch", "run_name", "epoch", "phase"):
            if ck.get(campo) != spec[campo]:
                raise CheckpointIntegrityError(
                    f"{campo} del checkpoint ({ck.get(campo)!r}) no coincide con el "
                    f"registrado ({spec[campo]!r})"
                )

        self.ckpt = ck
        self.metadata = {
            "arch": ck["arch"],
            "epoch": ck["epoch"],
            "phase": ck["phase"],
            "run_name": ck.get("run_name"),
            "sha256": ck_sha,
            "model_version": f"{ck['arch']}-ep{ck['epoch']}",
            "val_loss_entrenamiento": ck["val_loss"],
        }

        # 4) modelo y transform reconstruidos desde el checkpoint (sin supuestos)
        model = build_model(ck["arch"], pretrained=False)
        model.load_state_dict(ck["state_dict"])  # strict=True por defecto
        model.to(self.device)
        model.eval()
        self.model = model
        self.transform = build_eval_transform_from_config(ck["transform_config"])

    # ------------------------------------------------------------------ #

    def predict(self, image: bytes) -> Dict[str, Any]:
        """bytes de imagen -> dict del contrato (determinista)."""
        pil_img = load_image_rgb(image)
        tensor = self.transform(pil_img).unsqueeze(0).to(self.device)

        with torch.inference_mode():
            probs = torch.softmax(self.model(tensor), dim=1)[0]

        # decision sobre la probabilidad redondeada (dict autoconsistente)
        prob_cancer = round(float(probs[0]), 6)
        prob_non_cancer = round(1.0 - prob_cancer, 6)
        label = "cancer" if prob_cancer >= self.threshold else "non-cancer"
        index = 0 if label == "cancer" else 1

        return {
            "label": label,
            "probabilities": {"cancer": prob_cancer, "non-cancer": prob_non_cancer},
            "predicted_class_index": index,
            "threshold": self.threshold,
            "model": dict(self.metadata),
            "disclaimer": DISCLAIMER,
        }


# --------------------------------------------------------------------------- #
# API de una linea (singleton perezoso por proceso)
# --------------------------------------------------------------------------- #

_default_predictor: Optional[Predictor] = None
_default_lock = threading.Lock()


def predict(image: bytes, checkpoint_path: str | Path = DEFAULT_CHECKPOINT_REL,
            device: str = DEFAULT_DEVICE, threshold: float = DEFAULT_THRESHOLD) -> Dict[str, Any]:
    """Crea/reutiliza el Predictor por defecto del proceso y predice.

    La primera llamada carga el checkpoint (preflight incluido); las
    siguientes reutilizan el singleton. Los parametros solo se aplican en la
    primera llamada del proceso.
    """
    global _default_predictor
    if _default_predictor is None:
        with _default_lock:
            if _default_predictor is None:
                _default_predictor = Predictor(
                    checkpoint_path=checkpoint_path, device=device, threshold=threshold
                )
    return _default_predictor.predict(image)


# --------------------------------------------------------------------------- #
# CLI smoke
# --------------------------------------------------------------------------- #

def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Inferencia de una imagen (SaludOral-IA).")
    ap.add_argument("--image", required=True, help="Ruta de la imagen a clasificar.")
    ap.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT_REL,
                    help=f"Checkpoint registrado. Default: {DEFAULT_CHECKPOINT_REL}")
    ap.add_argument("--device", default=DEFAULT_DEVICE, help=f"Default: {DEFAULT_DEVICE}")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                    help=f"Default: {DEFAULT_THRESHOLD}")
    args = ap.parse_args()

    image_bytes = Path(args.image).read_bytes()
    result = Predictor(
        checkpoint_path=args.checkpoint, device=args.device, threshold=args.threshold
    ).predict(image_bytes)
    # ensure_ascii=True: consola Windows (cp1252) sin errores por tildes
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
