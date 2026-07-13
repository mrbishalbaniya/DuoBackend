"""Production media storage (Cloudflare R2 + Cloudinary fallback)."""

from duo_project.media.config import media_storage_backend, r2_is_configured

__all__ = ["media_storage_backend", "r2_is_configured"]
