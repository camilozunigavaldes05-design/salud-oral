"""
Fabrica de modelos para SaludOral-IA.

Diseño aprobado en docs/diseno_pipeline.md (seccion D) y etapa 6:

- resnet18: backbone preentrenado ImageNet (IMAGENET1K_V1), cabeza
  reemplazada por Dropout(0.3) + Linear(in_features, 2).
- efficientnet_b0: preparado en la misma fabrica para la comparacion de la
  etapa 8, respetando que su cabeza es `classifier` (no `fc`). Sin
  entrenamiento planificado todavia.

Convencion de salidas (fija en todo el proyecto):
    indice 0 = "cancer"      (clase positiva)
    indice 1 = "non-cancer"
"""

from __future__ import annotations

import torch.nn as nn
from torchvision import models

NUM_CLASSES = 2
DROPOUT_P = 0.3


def build_model(arch: str = "resnet18", pretrained: bool = True) -> nn.Module:
    """Construye el modelo con cabeza clasificadora de 2 clases."""
    if arch == "resnet18":
        weights = models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
        model = models.resnet18(weights=weights)
        in_features = model.fc.in_features
        model.fc = nn.Sequential(nn.Dropout(DROPOUT_P), nn.Linear(in_features, NUM_CLASSES))
    elif arch == "efficientnet_b0":
        weights = models.EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
        model = models.efficientnet_b0(weights=weights)
        in_features = model.classifier[1].in_features  # la cabeza de EfficientNet es `classifier`
        model.classifier = nn.Sequential(nn.Dropout(DROPOUT_P), nn.Linear(in_features, NUM_CLASSES))
    else:
        raise ValueError(f"Arquitectura no soportada: {arch} (resnet18 | efficientnet_b0)")
    return model
