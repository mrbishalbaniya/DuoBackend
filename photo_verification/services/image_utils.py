"""Load and normalize images for the verification pipeline."""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps


@dataclass(frozen=True)
class LoadedImage:
    rgb: np.ndarray
    width: int
    height: int
    perceptual_hash: str
    hash_bits: np.ndarray


def load_image_from_bytes(data: bytes) -> LoadedImage:
    pil = Image.open(io.BytesIO(data))
    pil = ImageOps.exif_transpose(pil)
    if pil.mode != "RGB":
        pil = pil.convert("RGB")

    width, height = pil.size
    rgb = np.asarray(pil, dtype=np.uint8)
    phash, bits = _perceptual_hash(pil)
    return LoadedImage(rgb=rgb, width=width, height=height, perceptual_hash=phash, hash_bits=bits)


def load_image_from_file(uploaded_file) -> LoadedImage:
    uploaded_file.seek(0)
    data = uploaded_file.read()
    uploaded_file.seek(0)
    return load_image_from_bytes(data)


def _perceptual_hash(pil: Image.Image, hash_size: int = 16) -> tuple[str, np.ndarray]:
    """Difference hash — fast duplicate fingerprint."""
    gray = pil.convert("L").resize(
        (hash_size + 1, hash_size),
        Image.Resampling.LANCZOS,
    )
    pixels = np.asarray(gray, dtype=np.float32)
    diff = pixels[:, 1:] > pixels[:, :-1]
    bits = diff.flatten().astype(np.float32)
    hex_len = (hash_size * hash_size + 3) // 4
    as_int = int("".join("1" if b else "0" for b in bits), 2)
    return format(as_int, f"0{hex_len}x"), bits
