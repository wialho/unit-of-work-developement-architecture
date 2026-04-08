from __future__ import annotations

import json
import os
from typing import Any

from workflow_contracts import Artifact, ArtifactType, StepResult, StepType, WorkflowMessage, WorkflowStatus
from workflow_runtime import LLMClient, LLMRequest, load_prompt_template


FAILURE_QUEUE = "workflow-failures.in"
PROMPT_VERSION = os.getenv("REQUIREMENTS_REVIEW_PROMPT_VERSION", "v1")


class RequirementsReviewHandler:
    step_type = StepType.REQUIREMENTS_REVIEW

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client
        self._system_prompt = load_prompt_template("requirements-review/system", PROMPT_VERSION)

    async def process(self, message: WorkflowMessage, input_artifact: Artifact) -> StepResult:
        content = input_artifact.content or {}
        response = await self._llm_client.complete(
            LLMRequest(
                system_prompt=self._system_prompt.content,
                user_prompt=_build_requirements_prompt(content),
                temperature=0.0,
            )
        )
        payload = _extract_json_object(response.text)
        findings = _normalize_findings(payload.get("findings"))
        passed = _bool_or_default(payload.get("pass"), not findings)
        return StepResult(
            output_artifact_type=ArtifactType.REQUIREMENTS_REVIEW_RESULT,
            output_content={
                "language": content.get("language"),
                "files": content.get("files", []),
                "prompt": content.get("prompt"),
                "ticket": content.get("ticket"),
                "regeneration_attempt": content.get("regeneration_attempt", 0),
                "test_pass": content.get("test_pass"),
                "requirements_pass": passed,
                "review_stage": self.step_type.value,
                "summary": payload.get("summary", ""),
                "findings": findings,
            },
            output_metadata={
                "source_artifact_id": message.input_artifact_id,
                "review_stage": self.step_type.value,
                "llm_provider": response.provider,
                "llm_model": response.model,
                "prompt_ref": self._system_prompt.ref,
                **response.metadata,
            },
            next_step_type=StepType.POLICY_REVIEW if passed else None,
            terminal_workflow_status=None if passed else WorkflowStatus.FAILED,
            terminal_event_type=None if passed else "review_failed_requirements",
            failure_queue_name=None if passed else FAILURE_QUEUE,
        )


def _build_requirements_prompt(content: dict[str, Any]) -> str:
    ticket = content.get("ticket") or {}
    files = content.get("files") or []
    return (
        "Ticket:\n"
        f"{json.dumps(ticket, indent=2, sort_keys=True)}\n\n"
        "Generated files:\n"
        f"{json.dumps(files, indent=2, sort_keys=True)}"
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    stripped_text = text.strip()

    try:
        payload, _ = decoder.raw_decode(stripped_text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    for index, character in enumerate(stripped_text):
        if character != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(stripped_text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    return {}


def _normalize_findings(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    findings: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        findings.append(
            {
                "path": str(item.get("path", "")),
                "message": str(item.get("message", "")),
            }
        )
    return findings


def _bool_or_default(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized_value = value.strip().lower()
        if normalized_value in {"true", "pass", "passed", "yes"}:
            return True
        if normalized_value in {"false", "fail", "failed", "no"}:
            return False
    return default
