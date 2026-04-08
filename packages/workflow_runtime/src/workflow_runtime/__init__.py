from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from workflow_runtime.config import Settings
    from workflow_runtime.context import (
        ContextBundle,
        ContextPolicy,
        ContextResolver,
        ContextSource,
        DeterministicContextResolver,
    )
    from workflow_runtime.db import Database
    from workflow_runtime.llm import LLMClient, LLMRequest, LLMResponse, create_llm_client
    from workflow_runtime.object_storage import (
        BlobStorage,
        ObjectStorage,
        S3CompatibleBlobStorage,
        create_blob_storage,
    )
    from workflow_runtime.prompt_step import PromptLLMStepHandler, PromptStepConfig
    from workflow_runtime.prompt_registry import PromptTemplate, load_prompt, load_prompt_template
    from workflow_runtime.queue import QueueClient
    from workflow_runtime.self_improving_prompt_step import (
        SelfImprovingLLMStepHandler,
        SelfImprovingPromptStepConfig,
    )
    from workflow_runtime.worker import StepHandler, StepWorker


_EXPORTS = {
    "BlobStorage": "workflow_runtime.object_storage",
    "ContextBundle": "workflow_runtime.context",
    "ContextPolicy": "workflow_runtime.context",
    "ContextResolver": "workflow_runtime.context",
    "ContextSource": "workflow_runtime.context",
    "Database": "workflow_runtime.db",
    "DeterministicContextResolver": "workflow_runtime.context",
    "LLMClient": "workflow_runtime.llm",
    "LLMRequest": "workflow_runtime.llm",
    "LLMResponse": "workflow_runtime.llm",
    "ObjectStorage": "workflow_runtime.object_storage",
    "PromptLLMStepHandler": "workflow_runtime.prompt_step",
    "PromptTemplate": "workflow_runtime.prompt_registry",
    "PromptStepConfig": "workflow_runtime.prompt_step",
    "QueueClient": "workflow_runtime.queue",
    "S3CompatibleBlobStorage": "workflow_runtime.object_storage",
    "SelfImprovingLLMStepHandler": "workflow_runtime.self_improving_prompt_step",
    "SelfImprovingPromptStepConfig": "workflow_runtime.self_improving_prompt_step",
    "Settings": "workflow_runtime.config",
    "StepHandler": "workflow_runtime.worker",
    "StepWorker": "workflow_runtime.worker",
    "create_blob_storage": "workflow_runtime.object_storage",
    "create_llm_client": "workflow_runtime.llm",
    "load_prompt": "workflow_runtime.prompt_registry",
    "load_prompt_template": "workflow_runtime.prompt_registry",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_EXPORTS[name])
    exported_value = getattr(module, name)
    globals()[name] = exported_value
    return exported_value
