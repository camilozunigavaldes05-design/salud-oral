"""
Transformaciones de preprocesamiento para SaludOral-IA.

Diseño aprobado en docs/diseno_pipeline.md (seccion B):

- Train (augmentation moderado, semilla controlada por el caller):
    Resize(232) -> RandomCrop(224) -> HFlip(0.5) -> Rotation(10)
    -> ColorJitter(0.1) -> ToTensor -> Normalize(ImageNet)

- Eval / inferencia (determinista):
    Resize(232) -> CenterCrop(224) -> ToTensor -> Normalize(ImageNet)

Resize usa tamano escalar (232) para conservar la relacion de aspecto
original de la imagen.

No se aplican VerticalFlip ni crops agresivos para no destruir el
contexto lesional. Las estadisticas de ImageNet corresponden al
preentrenamiento del backbone.

Ejecucion esperada: `python -m ia.transforms` desde la raiz.
"""

from __future__ import annotations

from typing import Any, Dict

from torchvision import transforms

# Normalizacion ImageNet (requerida por el backbone preentrenado)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# Tamanos: dataset nativo 260x260; ResNet18 preentrenado a 224x224
RESIZE_SIZE = 232
INPUT_SIZE = 224


def build_train_transform() -> transforms.Compose:
    """Transforms de entrenamiento (augmentation moderado)."""
    return transforms.Compose(
        [
            transforms.Resize(RESIZE_SIZE),  # escalar: conserva relacion de aspecto
            transforms.RandomCrop(INPUT_SIZE),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(degrees=10),
            transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


def build_eval_transform() -> transforms.Compose:
    """Transforms de validacion/test/inferencia (deterministas)."""
    return transforms.Compose(
        [
            transforms.Resize(RESIZE_SIZE),  # escalar: conserva relacion de aspecto
            transforms.CenterCrop(INPUT_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


def build_eval_transform_from_config(cfg: Dict[str, Any]) -> transforms.Compose:
    """Reconstruye el pipeline de evaluacion desde la config del checkpoint.

    Permite que la inferencia (y Django en el futuro) replique el
    preprocesado exacto usado en entrenamiento sin depender del codigo
    fuente ni de supuestos implicitos.
    """
    resize = cfg["resize"]["size"]
    center_crop = cfg["eval"]["center_crop"]["size"]
    mean = cfg["normalize"]["mean"]
    std = cfg["normalize"]["std"]
    return transforms.Compose(
        [
            transforms.Resize(resize),
            transforms.CenterCrop(center_crop),
            transforms.ToTensor(),
            transforms.Normalize(mean=mean, std=std),
        ]
    )


def get_transform_config() -> Dict[str, Any]:
    """Config completa embebible en el checkpoint y reconstruible en inferencia.

    Registra todos los parametros necesarios para reconstruir
    exactamente el preprocesamiento de inferencia.
    """
    return {
        "resize": {"size": RESIZE_SIZE, "interpolation": "bilinear", "antialias": True},
        "train": {
            "random_crop": {"size": INPUT_SIZE, "padding": 0, "fill": 0},
            "hflip": {"p": 0.5},
            "rotation": {"degrees": 10, "interpolation": "nearest", "expand": False, "fill": 0},
            "colorjitter": {"brightness": 0.1, "contrast": 0.1, "saturation": 0.1, "hue": 0.0},
        },
        "eval": {
            "center_crop": {"size": INPUT_SIZE},
        },
        "to_tensor": {"scale": [0.0, 1.0]},
        "normalize": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD},
        "input_size": INPUT_SIZE,
        "classes": ["cancer", "non-cancer"],  # orden fijo, 0 = cancer
    }
