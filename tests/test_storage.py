from io import BytesIO

import pytest

from backend import storage


PNG = b"\x89PNG\r\n\x1a\n" + b"needbridge-test-image"
PDF = b"%PDF-1.4\nNeedBridge test document"


def test_save_image_uses_opaque_key_and_local_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "LOCAL_ROOT", tmp_path)
    monkeypatch.setattr(storage, "_provider", storage.LocalStorage())
    saved = storage.save_upload(BytesIO(PNG), "donation-photo", 17)
    assert saved.visibility == "public"
    assert saved.content_type == "image/png"
    assert saved.size == len(PNG)
    assert "17" in saved.key and "needbridge-test-image" not in saved.key
    assert storage.read_object(saved.key) == PNG
    storage.delete_object(saved.key)
    with pytest.raises(storage.StorageError):
        storage.read_object(saved.key)


def test_verification_documents_are_private(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "LOCAL_ROOT", tmp_path)
    monkeypatch.setattr(storage, "_provider", storage.LocalStorage())
    saved = storage.save_upload(BytesIO(PDF), "verification-document", 4)
    assert saved.visibility == "private"
    assert saved.content_type == "application/pdf"
    assert saved.key.startswith("private-verification-documents/")


def test_rejects_wrong_magic_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "LOCAL_ROOT", tmp_path)
    monkeypatch.setattr(storage, "_provider", storage.LocalStorage())
    with pytest.raises(storage.StorageError):
        storage.save_upload(BytesIO(b"not really a png"), "donation-photo", 1)


def test_rejects_oversized_upload(monkeypatch):
    monkeypatch.setattr(storage, "MAX_IMAGE_BYTES", 4)
    with pytest.raises(storage.StorageError):
        storage.save_upload(BytesIO(PNG), "donation-photo", 1)
