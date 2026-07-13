"""Load and normalize images for the verification pipeline."""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import ExifTags, Image, ImageOps


@dataclass(frozen=True)
class ExifSignals:
    """Metadata hints for AI-vs-camera photo classification."""

    has_camera_make: bool
    has_camera_model: bool
    has_datetime_original: bool
    software_tag: str
    ai_software_hint: bool
    trust_score: float


@dataclass(frozen=True)
class LoadedImage:
    rgb: np.ndarray
    width: int
    height: int
    perceptual_hash: str
    hash_bits: np.ndarray
    exif: ExifSignals


def load_image_from_bytes(data: bytes) -> LoadedImage:
    pil = Image.open(io.BytesIO(data))
    pil = ImageOps.exif_transpose(pil)
    if pil.mode != "RGB":
        pil = pil.convert("RGB")

    width, height = pil.size
    rgb = np.asarray(pil, dtype=np.uint8)
    phash, bits = _perceptual_hash(pil)
    exif = _extract_exif_signals(pil)
    return LoadedImage(
        rgb=rgb,
        width=width,
        height=height,
        perceptual_hash=phash,
        hash_bits=bits,
        exif=exif,
    )


def load_image_from_file(uploaded_file) -> LoadedImage:
    return safe_load_image_from_file(uploaded_file)


MAX_VERIFICATION_IMAGE_BYTES = 10 * 1024 * 1024


def safe_load_image_from_file(uploaded_file, *, max_bytes: int = MAX_VERIFICATION_IMAGE_BYTES) -> LoadedImage:
    uploaded_file.seek(0)
    data = uploaded_file.read(max_bytes + 1)
    uploaded_file.seek(0)
    if len(data) > max_bytes:
        raise ValueError(f"Image exceeds maximum size of {max_bytes // (1024 * 1024)}MB.")
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


_AI_SOFTWARE_KEYWORDS = (
    "stable diffusion",
    "midjourney",
    "dall-e",
    "dalle",
    "flux",
    "comfyui",
    "automatic1111",
    "novelai",
    "leonardo",
    "ideogram",
    "firefly",
    "generated",
    "synthetic",
)


def _extract_exif_signals(pil: Image.Image) -> ExifSignals:
    raw = pil.getexif() or {}
    tag_map = {ExifTags.TAGS.get(k, str(k)): v for k, v in raw.items()}

    make = str(tag_map.get("Make", "")).strip()
    model = str(tag_map.get("Model", "")).strip()
    software = str(tag_map.get("Software", "")).strip()
    datetime_original = str(tag_map.get("DateTimeOriginal", "")).strip()

    software_lower = software.lower()
    ai_hint = any(keyword in software_lower for keyword in _AI_SOFTWARE_KEYWORDS)

    trust = 0.15
    if make:
        trust += 0.35
    if model:
        trust += 0.25
    if datetime_original:
        trust += 0.15
    if software and not ai_hint:
        trust += 0.10
    if ai_hint:
        trust = 0.05

    return ExifSignals(
        has_camera_make=bool(make),
        has_camera_model=bool(model),
        has_datetime_original=bool(datetime_original),
        software_tag=software,
        ai_software_hint=ai_hint,
        trust_score=float(np.clip(trust, 0.0, 1.0)),
    )
