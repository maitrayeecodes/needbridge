"""Provider-neutral file storage for NeedBridge.

All objects are private by default. Persist the returned object key and metadata in the
application database; never persist a temporary signed URL. Local storage is for
development. S3-compatible storage can be enabled without changing API callers.
"""
from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

ROOT = Path(__file__).resolve().parent.parent
LOCAL_ROOT = Path(os.getenv("NEEDBRIDGE_UPLOAD_DIR", ROOT / "data" / "uploads")).resolve()
BACKEND = os.getenv("NEEDBRIDGE_STORAGE_BACKEND", "local").lower()
MAX_IMAGE_BYTES = int(os.getenv("NEEDBRIDGE_MAX_IMAGE_BYTES", 5 * 1024 * 1024))
MAX_DOCUMENT_BYTES = int(os.getenv("NEEDBRIDGE_MAX_DOCUMENT_BYTES", 10 * 1024 * 1024))

IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
DOCUMENT_TYPES = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}


class StorageError(Exception):
    """Raised for invalid files or storage provider failures."""


@dataclass(frozen=True)
class StoredObject:
    key: str
    content_type: str
    size: int
    visibility: str


def _safe_segment(value: str) -> str:
    value = re.sub(r"[^a-z0-9_-]", "", value.lower())
    if not value:
        raise StorageError("Invalid storage category.")
    return value


def _detect_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def _read_limited(file: BinaryIO, limit: int) -> bytes:
    data = file.read(limit + 1)
    if len(data) > limit:
        raise StorageError(f"File exceeds the {limit // (1024 * 1024)} MB upload limit.")
    if not data:
        raise StorageError("The uploaded file is empty.")
    return data


class LocalStorage:
    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = (LOCAL_ROOT / key).resolve()
        if LOCAL_ROOT not in path.parents:
            raise StorageError("Invalid object key.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def delete(self, key: str) -> None:
        path = (LOCAL_ROOT / key).resolve()
        if LOCAL_ROOT not in path.parents:
            raise StorageError("Invalid object key.")
        path.unlink(missing_ok=True)

    def read(self, key: str) -> bytes:
        path = (LOCAL_ROOT / key).resolve()
        if LOCAL_ROOT not in path.parents or not path.is_file():
            raise StorageError("File not found.")
        return path.read_bytes()

    def url(self, key: str, expires: int = 300) -> str | None:
        # Local files are delivered through an authenticated application endpoint.
        return None


class S3Storage:
    def __init__(self) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise StorageError("Install boto3 to use S3-compatible storage.") from exc
        endpoint = os.getenv("S3_ENDPOINT_URL") or None
        self.bucket = os.environ["S3_BUCKET"]
        self.client = boto3.client(
            "s3", endpoint_url=endpoint,
            region_name=os.getenv("S3_REGION", "auto"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data,
                               ContentType=content_type)

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def read(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def url(self, key: str, expires: int = 300) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires
        )


_provider = None


def provider():
    global _provider
    if _provider is None:
        if BACKEND == "local":
            _provider = LocalStorage()
        elif BACKEND == "s3":
            _provider = S3Storage()
        else:
            raise StorageError("NEEDBRIDGE_STORAGE_BACKEND must be 'local' or 's3'.")
    return _provider


def save_upload(file: BinaryIO, purpose: str, owner_id: str) -> StoredObject:
    """Save an image or verification document and return its durable object key.

    purpose is 'donation-photo' or 'verification-document'. The original filename is
    deliberately discarded; only verified magic-byte types are accepted.
    """
    if purpose not in {"donation-photo", "verification-document"}:
        raise StorageError("Unsupported upload purpose.")
    is_image = purpose == "donation-photo"
    limit = MAX_IMAGE_BYTES if is_image else MAX_DOCUMENT_BYTES
    allowed = IMAGE_TYPES if is_image else DOCUMENT_TYPES
    data = _read_limited(file, limit)
    content_type = _detect_type(data)
    if content_type not in allowed:
        raise StorageError("Unsupported file. Upload a JPG, PNG, WebP image or PDF document as applicable.")
    # The key contains no original filename, email, or other personal information.
    folder = "public-listing-photos" if is_image else "private-verification-documents"
    owner_segment = _safe_segment(str(owner_id))
    key = f"{folder}/{owner_segment}/{uuid.uuid4().hex}{allowed[content_type]}"
    provider().put(key, data, content_type)
    return StoredObject(key=key, content_type=content_type, size=len(data),
                        visibility="public" if is_image else "private")


def delete_object(key: str) -> None:
    provider().delete(key)


def read_object(key: str) -> bytes:
    return provider().read(key)


def signed_url(key: str, expires: int = 300) -> str | None:
    return provider().url(key, expires)
