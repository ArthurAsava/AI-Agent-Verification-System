
from __future__ import annotations

import pytest

from app.services.storage_service import (
    SupabaseStorageService,
)


@pytest.fixture
def storage():
    return SupabaseStorageService(
        supabase_url="https://example.supabase.co",
        service_role_key="test-key",
        bucket="agent-kyc-documents",
    )


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/document.pdf",
        "../document.pdf",
        "agent/../document.pdf",
        "agent/./document.pdf",
        "agent//document.pdf",
        r"agent\document.pdf",
        "agent/%2e%2e/document.pdf",
        "agent/%2F/document.pdf",
        "agent/document.pdf\n",
        "agent/document.pdf\x00",
    ],
)
def test_unsafe_storage_paths_are_rejected(
    storage,
    path,
):
    with pytest.raises(ValueError):
        storage._object_url(path)


def test_valid_storage_path_is_accepted(storage):
    path = (
        "e1c1d719-4739-408c-b92d-313e67d794fc/"
        "5572d488-17d6-421e-a247-f107592bd715/"
        "document.png"
    )

    url = storage._object_url(path)

    assert url.startswith(
        "https://example.supabase.co/"
        "storage/v1/object/agent-kyc-documents/"
    )

    assert url.endswith("document.png")
