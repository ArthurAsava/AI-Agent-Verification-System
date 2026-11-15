
import pytest

from app.services.storage_service import (
    StorageConfigurationError,
    SupabaseStorageService,
)


def test_storage_requires_https_url():
    with pytest.raises(StorageConfigurationError):
        SupabaseStorageService(
            supabase_url="http://example.com",
            service_role_key="test-key",
            bucket="agent-kyc-documents",
        )


def test_storage_requires_service_role_key():
    with pytest.raises(StorageConfigurationError):
        SupabaseStorageService(
            supabase_url="https://example.supabase.co",
            service_role_key="",
            bucket="agent-kyc-documents",
        )


def test_storage_requires_bucket():
    with pytest.raises(StorageConfigurationError):
        SupabaseStorageService(
            supabase_url="https://example.supabase.co",
            service_role_key="test-key",
            bucket="",
        )


def test_storage_object_url():
    storage = SupabaseStorageService(
        supabase_url="https://example.supabase.co",
        service_role_key="test-key",
        bucket="agent-kyc-documents",
    )

    url = storage._object_url(
        "agent-123/document-456/document.pdf"
    )

    assert url == (
        "https://example.supabase.co/storage/v1/object/"
        "agent-kyc-documents/"
        "agent-123/document-456/document.pdf"
    )


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/document.pdf",
        "../document.pdf",
        "agent/../document.pdf",
        "agent//document.pdf",
        r"agent\document.pdf",
    ],
)
def test_storage_rejects_invalid_paths(path):
    storage = SupabaseStorageService(
        supabase_url="https://example.supabase.co",
        service_role_key="test-key",
        bucket="agent-kyc-documents",
    )

    with pytest.raises(ValueError):
        storage._object_url(path)
