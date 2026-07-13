"""Image processing — WebP variants, orientation, compression."""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps

IMAGE_VARIANTS: dict[str, int] = {
    "thumb": 150,
    "small": 400,
    "medium": 800,
    "large": 1600,
}

MAX_ORIGINAL_EDGE = 2048
WEBP_QUALITY = 82


@dataclass(frozen=True)
class ProcessedVariant:
    name: str
    data: bytes
    content_type: str = "image/webp"
    width: int = 0
    height: int = 0


def _load_image(file_obj) -> Image.Image:
    file_obj.seek(0)
    image = Image.open(file_obj)
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    elif image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    return image


def _resize(image: Image.Image, max_edge: int) -> Image.Image:
    image = image.copy()
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    return image


def _to_webp_bytes(image: Image.Image, *, quality: int = WEBP_QUALITY) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=quality, method=6)
    return buffer.getvalue()


def process_image_variants(file_obj, *, animated_gif: bool = False) -> list[ProcessedVariant]:
    """Generate thumb/small/medium/large/original WebP variants."""
    if animated_gif:
        file_obj.seek(0)
        raw = file_obj.read()
        return [
            ProcessedVariant(name="original", data=raw, content_type="image/gif"),
        ]

    image = _load_image(file_obj)
    variants: list[ProcessedVariant] = []

    for name, edge in IMAGE_VARIANTS.items():
        resized = _resize(image, edge)
        variants.append(
            ProcessedVariant(
                name=name,
                data=_to_webp_bytes(resized),
                width=resized.width,
                height=resized.height,
            )
        )

    original = _resize(image, MAX_ORIGINAL_EDGE)
    variants.append(
        ProcessedVariant(
            name="original",
            data=_to_webp_bytes(original, quality=88),
            width=original.width,
            height=original.height,
        )
    )
    return variants


def primary_delivery_variant(variants: list[ProcessedVariant]) -> ProcessedVariant:
    for preferred in ("medium", "large", "small", "original"):
        for variant in variants:
            if variant.name == preferred:
                return variant
    return variants[0]
