from __future__ import annotations

from io import BytesIO
import json
from typing import Any, Protocol

from minio import Minio

from workflow_runtime.config import Settings


class BlobStorage(Protocol):
    def put_json(self, key: str, payload: dict[str, Any]) -> str:
        ...

    def get_json(self, content_ref: str) -> dict[str, Any]:
        ...


class S3CompatibleBlobStorage:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.object_storage_bucket
        self._client = Minio(
            settings.object_storage_endpoint,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            secure=settings.object_storage_secure,
            region=settings.object_storage_region,
        )

    def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def put_json(self, key: str, payload: dict[str, Any]) -> str:
        data = json.dumps(payload).encode("utf-8")
        self.ensure_bucket()
        self._client.put_object(
            self._bucket,
            key,
            data=BytesIO(data),
            length=len(data),
            content_type="application/json",
        )
        return f"s3://{self._bucket}/{key}"

    def get_json(self, content_ref: str) -> dict[str, Any]:
        prefix = f"s3://{self._bucket}/"
        if not content_ref.startswith(prefix):
            raise ValueError(f"Unsupported content_ref for configured bucket: {content_ref}")
        key = content_ref.removeprefix(prefix)
        response = self._client.get_object(self._bucket, key)
        try:
            return json.loads(response.read().decode("utf-8"))
        finally:
            response.close()
            response.release_conn()


def create_blob_storage(settings: Settings) -> BlobStorage:
    if settings.object_storage_provider == "s3_compatible":
        return S3CompatibleBlobStorage(settings)
    raise ValueError(f"Unsupported OBJECT_STORAGE_PROVIDER: {settings.object_storage_provider}")


ObjectStorage = S3CompatibleBlobStorage
