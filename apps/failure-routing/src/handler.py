from __future__ import annotations

import os

from workflow_contracts import Artifact, ArtifactType, StepResult, StepType, WorkflowMessage, WorkflowStatus


DEFAULT_ACTION = os.getenv("FAILURE_ROUTING_DEFAULT_ACTION", "regenerate").strip().lower()


class FailureRoutingHandler:
    step_type = StepType.FAILURE_ROUTING

    async def process(self, message: WorkflowMessage, input_artifact: Artifact) -> StepResult:
        content = input_artifact.content or {}
        prompt = content.get("prompt", "")
        ticket = content.get("ticket")
        regeneration_attempt = int(content.get("regeneration_attempt", 0) or 0)
        findings = content.get("findings") or []
        review_stage = content.get("review_stage") or input_artifact.metadata.get("review_stage", "review")

        route_to_regeneration = DEFAULT_ACTION == "regenerate" and regeneration_attempt < 1 and bool(prompt)

        if route_to_regeneration:
            regenerated_prompt = _build_regeneration_prompt(prompt, review_stage, findings)
            return StepResult(
                output_artifact_type=ArtifactType.PROMPT,
                output_content={
                    "prompt": regenerated_prompt,
                    "ticket": ticket,
                    "regeneration_attempt": regeneration_attempt + 1,
                    "previous_failure": {
                        "review_stage": review_stage,
                        "findings": findings,
                    },
                },
                output_metadata={
                    "source_artifact_id": message.input_artifact_id,
                    "routed_by": self.step_type.value,
                    "route": "regenerate",
                },
                next_step_type=StepType.PROMPT_TO_CODE,
                next_step_attempt=2,
                workflow_status_override=WorkflowStatus.RUNNING,
            )

        return StepResult(
            output_artifact_type=ArtifactType.FAILURE_RESULT,
            output_content={
                **content,
                "route": "human_review",
                "review_stage": review_stage,
                "regeneration_attempt": regeneration_attempt,
            },
            output_metadata={
                "source_artifact_id": message.input_artifact_id,
                "routed_by": self.step_type.value,
                "route": "human_review",
            },
            next_step_type=StepType.HUMAN_REVIEW,
            next_step_attempt=1,
            workflow_status_override=WorkflowStatus.FAILED,
        )


def _build_regeneration_prompt(
    prompt: str,
    review_stage: str,
    findings: list[dict[str, str]] | list[object],
) -> str:
    lines = [
        prompt.rstrip(),
        "",
        "Regeneration attempt 1:",
        f"The previous output failed at review stage '{review_stage}'.",
        "Regenerate the implementation and address the following failures:",
    ]
    if findings:
        for finding in findings:
            if isinstance(finding, dict):
                path = finding.get("path", "")
                message = finding.get("message", "")
                prefix = f"{path}: " if path else ""
                lines.append(f"- {prefix}{message}")
            else:
                lines.append(f"- {finding}")
    else:
        lines.append("- A downstream review stage failed without structured findings.")
    lines.extend(
        [
            "",
            "This is a regeneration request. Preserve valid parts of the prior intent and fix the reported failures.",
        ]
    )
    return "\n".join(lines)
