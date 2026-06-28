"""Lazy exports — heavy CV deps load only when the pipeline runs."""

from photo_verification.services.pipeline import PhotoVerificationPipeline, PhotoVerificationResult

__all__ = ["PhotoVerificationPipeline", "PhotoVerificationResult"]
