"""Cloudflare R2 client (S3-compatible)."""

from __future__ import annotations

import logging
from functools import lru_cache

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings

from .config import build_public_url

logger = logging.getLogger("duo.media")

CACHE_IMMUTABLE = "public, max-age=31536000, immutable"
CACHE_STANDARD = "public, max-age=86400"


class R2NotConfiguredError(Exception):
    pass


@lru_cache(maxsize=1)
def get_r2_client():
    if not getattr(settings, "R2_BUCKET_NAME", ""):
        raise R2NotConfiguredError("R2 bucket is not configured.")
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name=getattr(settings, "R2_REGION_NAME", "auto"),
        config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
    )


def ensure_bucket_exists() -> None:
    """Create bucket in development when missing (no-op if already exists)."""
    if not getattr(settings, "R2_AUTO_CREATE_BUCKET", False):
        return
    client = get_r2_client()
    bucket = settings.R2_BUCKET_NAME
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        try:
            client.create_bucket(Bucket=bucket)
            logger.info("r2_bucket_created bucket=%s", bucket)
        except ClientError as exc:
            logger.warning("r2_bucket_create_failed bucket=%s error=%s", bucket, exc)


def put_object(
    *,
    key: str,
    body: bytes,
    content_type: str,
    cache_control: str = CACHE_IMMUTABLE,
) -> str:
    ensure_bucket_exists()
    client = get_r2_client()
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=body,
        ContentType=content_type,
        CacheControl=cache_control,
    )
    return build_public_url(key)


def delete_object(key: str) -> None:
    try:
        client = get_r2_client()
        client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
    except Exception as exc:
        logger.debug("r2_delete_failed key=%s error=%s", key, exc)


def delete_prefix(prefix: str) -> int:
    """Delete all objects under a prefix. Returns count deleted."""
    try:
        client = get_r2_client()
        deleted = 0
        token = None
        while True:
            kwargs = {"Bucket": settings.R2_BUCKET_NAME, "Prefix": prefix.rstrip("/") + "/"}
            if token:
                kwargs["ContinuationToken"] = token
            resp = client.list_objects_v2(**kwargs)
            contents = resp.get("Contents") or []
            if not contents:
                break
            for item in contents:
                client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=item["Key"])
                deleted += 1
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return deleted
    except Exception as exc:
        logger.warning("r2_delete_prefix_failed prefix=%s error=%s", prefix, exc)
        return 0
