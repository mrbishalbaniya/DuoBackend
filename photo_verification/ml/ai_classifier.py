"""Pluggable PyTorch classifier for synthetic face detection."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np


class AiClassifier(Protocol):
    def predict(self, rgb: np.ndarray) -> float: ...


class _TorchAiClassifier:
    """Loads a TorchScript or state_dict model when PHOTO_AI_MODEL_PATH is set."""

    def __init__(self, model_path: Path) -> None:
        import torch

        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model = torch.jit.load(str(model_path), map_location=self._device)
        self._model.eval()

    def predict(self, rgb: np.ndarray) -> float:
        import torch
        import cv2

        resized = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_AREA)
        tensor = torch.from_numpy(resized).permute(2, 0, 1).float() / 255.0
        tensor = tensor.unsqueeze(0).to(self._device)
        with torch.no_grad():
            out = self._model(tensor)
            if hasattr(out, "item"):
                return float(out.item())
            prob = torch.sigmoid(out).flatten()[0]
            return float(prob.item())


_classifier: AiClassifier | None = None
_classifier_checked = False


def get_ai_classifier() -> AiClassifier | None:
    global _classifier, _classifier_checked
    if _classifier_checked:
        return _classifier

    _classifier_checked = True
    try:
        from django.conf import settings

        path = getattr(settings, "PHOTO_AI_MODEL_PATH", "") or ""
        if path and Path(path).is_file():
            _classifier = _TorchAiClassifier(Path(path))
    except Exception:
        _classifier = None
    return _classifier
