from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StepType(StrEnum):
    TICKET_TO_PROMPT = "ticket_to_prompt"
    PROMPT_TO_CODE = "prompt_to_code"
    CODE_REVIEW = "code_review"


class ArtifactType(StrEnum):
    SOURCE_TICKET = "source_ticket"
    PROMPT = "prompt"
    CODE_ARTIFACT = "code_artifact"
    REVIEW_RESULT = "review_result"


class ReviewDecision(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class WorkflowMessage(BaseModel):
    workflow_run_id: str
    step_type: StepType
    input_artifact_id: str
    trace_id: str
    workflow_step_id: str | None = None
    attempt: int = Field(default=1, ge=1)


class Artifact(BaseModel):
    id: str
    workflow_run_id: str
    artifact_type: ArtifactType
    content: dict[str, Any] | None = None
    content_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by_service: str


class StepResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    output_artifact_type: ArtifactType
    output_content: dict[str, Any] | None = None
    output_content_ref: str | None = None
    output_metadata: dict[str, Any] = Field(default_factory=dict)
    next_step_type: StepType | None = None
