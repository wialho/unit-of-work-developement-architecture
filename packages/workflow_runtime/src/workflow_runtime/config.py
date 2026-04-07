from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str
    database_url: str
    queue_url: str
    llm_provider: str
    llm_base_url: str
    llm_model: str
    llm_api_key: str | None
    object_storage_provider: str
    object_storage_endpoint: str
    object_storage_bucket: str
    object_storage_region: str | None
    object_storage_access_key: str | None
    object_storage_secret_key: str | None
    object_storage_secure: bool

    @classmethod
    def from_env(cls, service_name: str) -> "Settings":
        service_env_prefix = service_name.upper().replace("-", "_")

        return cls(
            service_name=os.getenv("SERVICE_NAME", service_name),
            database_url=os.environ["DATABASE_URL"],
            queue_url=os.environ["QUEUE_URL"],
            llm_provider=_service_env(service_env_prefix, "LLM_PROVIDER", "ollama"),
            llm_base_url=_service_env(service_env_prefix, "LLM_BASE_URL", "http://ollama:11434"),
            llm_model=_service_env(service_env_prefix, "LLM_MODEL", "codellama"),
            llm_api_key=_service_env_optional(service_env_prefix, "LLM_API_KEY"),
            object_storage_provider=os.getenv("OBJECT_STORAGE_PROVIDER", "s3_compatible"),
            object_storage_endpoint=os.getenv("OBJECT_STORAGE_ENDPOINT", "minio:9000"),
            object_storage_bucket=os.getenv("OBJECT_STORAGE_BUCKET", "workflow-artifacts"),
            object_storage_region=os.getenv("OBJECT_STORAGE_REGION"),
            object_storage_access_key=os.getenv("OBJECT_STORAGE_ACCESS_KEY", "workflow"),
            object_storage_secret_key=os.getenv("OBJECT_STORAGE_SECRET_KEY", "workflow-secret"),
            object_storage_secure=os.getenv("OBJECT_STORAGE_SECURE", "false").lower() == "true",
        )


def _service_env(service_env_prefix: str, key: str, default: str) -> str:
    return (
        os.getenv(f"{service_env_prefix}_{key}")
        or os.getenv(f"SERVICE_{key}")
        or os.getenv(key)
        or default
    )


def _service_env_optional(service_env_prefix: str, key: str) -> str | None:
    return os.getenv(f"{service_env_prefix}_{key}") or os.getenv(f"SERVICE_{key}") or os.getenv(key)
