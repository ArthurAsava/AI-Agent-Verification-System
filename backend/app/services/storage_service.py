
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.core.config import get_settings


class StorageConfigurationError(RuntimeError):
    """Storage configuration is missing or invalid."""


class StorageOperationError(RuntimeError):
    """A Supabase Storage operation failed."""


@dataclass(frozen=True)
class StorageObject:
    bucket: str
    path: str


class SupabaseStorageService:
    """Server-side access to private Supabase Storage."""

    def __init__(
        self,
        supabase_url: str,
        service_role_key: str,
        bucket: str,
        timeout: float = 30.0,
    ) -> None:
        if not supabase_url or not supabase_url.startswith(
            "https://"
        ):
            raise StorageConfigurationError(
                "A valid HTTPS Supabase URL is required"
            )

        if not service_role_key:
            raise StorageConfigurationError(
                "Supabase service-role key is missing"
            )

        if not bucket:
            raise StorageConfigurationError(
                "Supabase Storage bucket is missing"
            )

        self.supabase_url = supabase_url.rstrip("/")
        self.bucket = bucket
        self.timeout = timeout

        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        }

    def _object_url(self, path: str) -> str:
        if (
            not path
            or path.startswith("/")
            or "\\" in path
            or any(
                segment in ("", ".", "..")
                for segment in path.split("/")
            )
        ):
            raise ValueError("Invalid storage object path")

        encoded_bucket = quote(self.bucket, safe="")
        encoded_path = quote(path, safe="/")

        return (
            f"{self.supabase_url}/storage/v1/object/"
            f"{encoded_bucket}/{encoded_path}"
        )

    async def upload(
        self,
        path: str,
        content: bytes,
        content_type: str,
    ) -> StorageObject:
        """Upload a validated file without overwriting."""

        headers = {
            **self.headers,
            "Content-Type": content_type,
            "x-upsert": "false",
        }

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:
            response = await client.post(
                self._object_url(path),
                content=content,
                headers=headers,
            )

        if response.status_code not in (200, 201):
            raise StorageOperationError(
                "Private storage upload failed "
                f"(HTTP {response.status_code})"
            )

        return StorageObject(
            bucket=self.bucket,
            path=path,
        )

    async def download(self, path: str) -> bytes:
        """Download a private object through the backend."""

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:
            response = await client.get(
                self._object_url(path),
                headers=self.headers,
            )

        if response.status_code != 200:
            raise StorageOperationError(
                "Private storage download failed "
                f"(HTTP {response.status_code})"
            )

        return response.content

    async def delete(self, path: str) -> None:
        """Delete an object for cleanup operations."""

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:
            response = await client.delete(
                self._object_url(path),
                headers=self.headers,
            )

        if response.status_code not in (200, 204):
            raise StorageOperationError(
                "Private storage deletion failed "
                f"(HTTP {response.status_code})"
            )



def get_storage_service() -> SupabaseStorageService:
    """Build the storage client using backend settings."""

    settings = get_settings()

    return SupabaseStorageService(
        supabase_url=settings.supabase_url or "",
        service_role_key=(
            settings.supabase_service_role_key or ""
        ),
        bucket=settings.supabase_storage_bucket,
    )

