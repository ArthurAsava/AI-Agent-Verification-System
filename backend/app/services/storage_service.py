
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

    
    @staticmethod
    def _validate_bucket(bucket: str) -> str:
        """Validate a Storage bucket name before building a service URL."""

        if not isinstance(bucket, str) or not bucket:
            raise ValueError("Invalid storage bucket")

        if any(
            character in bucket for character in ("/", "\\", "%")
        ):
            raise ValueError("Invalid storage bucket")

        if any(
            ord(character) < 32 or ord(character) == 127
            for character in bucket
        ):
            raise ValueError("Invalid storage bucket")

        return bucket

    def _object_url(
        self,
        path: str,
        *,
        bucket: str | None = None,
    ) -> str:
        """Build a safely encoded private Storage object URL."""

        if not isinstance(path, str) or not path:
            raise ValueError("Invalid storage object path")

        if path.startswith("/") or "\\" in path:
            raise ValueError("Invalid storage object path")

        segments = path.split("/")

        if any(
            segment in ("", ".", "..")
            for segment in segments
        ):
            raise ValueError("Invalid storage object path")

        if any(ord(character) < 32 or ord(character) == 127
               for character in path):
            raise ValueError("Invalid storage object path")

        # Reject percent-encoded paths to avoid ambiguous
        # interpretation across HTTP and Storage layers.
        if "%" in path:
            raise ValueError("Invalid storage object path")

        selected_bucket = self._validate_bucket(
            self.bucket if bucket is None else bucket
        )
        encoded_bucket = quote(selected_bucket, safe="")
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

        url = self._object_url(path)

        headers = {
            **self.headers,
            "Content-Type": content_type,
            "x-upsert": "false",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:
                response = await client.post(
                    url,
                    content=content,
                    headers=headers,
                )
        except httpx.RequestError as exc:
            raise StorageOperationError(
                "Private storage upload unavailable"
            ) from exc

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

        url = self._object_url(path)

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                )
        except httpx.RequestError as exc:
            raise StorageOperationError(
                "Private storage download unavailable"
            ) from exc

        if response.status_code != 200:
            raise StorageOperationError(
                "Private storage download failed "
                f"(HTTP {response.status_code})"
            )

        return response.content

    async def delete(
        self,
        path: str,
        *,
        bucket: str | None = None,
    ) -> None:
        """Delete an object for cleanup operations."""

        url = self._object_url(path, bucket=bucket)

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:
                response = await client.delete(
                    url,
                    headers=self.headers,
                )
        except httpx.RequestError as exc:
            raise StorageOperationError(
                "Private storage deletion unavailable"
            ) from exc

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

