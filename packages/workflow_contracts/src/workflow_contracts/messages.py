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
    TEST_RUNNER = "test_runner"
    REQUIREMENTS_REVIEW = "requirements_review"
    POLICY_REVIEW = "policy_review"
    CODE_REVIEW = "code_review"
    FAILURE_ROUTING = "failure_routing"
    HUMAN_REVIEW = "human_review"


class ArtifactType(StrEnum):
    SOURCE_TICKET = "source_ticket"
    PROMPT = "prompt"
    CODE_ARTIFACT = "code_artifact"
    TEST_RESULT = "test_result"
    REQUIREMENTS_REVIEW_RESULT = "requirements_review_result"
    POLICY_REVIEW_RESULT = "policy_review_result"
    REVIEW_RESULT = "review_result"
    FAILURE_RESULT = "failure_result"


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
    next_step_attempt: int = Field(default=1, ge=1)
    terminal_workflow_status: WorkflowStatus | None = None
    terminal_event_type: str | None = None
    failure_queue_name: str | None = None
    workflow_status_override: WorkflowStatus | None = None
