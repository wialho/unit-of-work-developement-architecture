from __future__ import annotations

from workflow_contracts import (
    Artifact,
    ArtifactType,
    ReviewDecision,
    StepResult,
    StepType,
    WorkflowMessage,
)


class CodeReviewHandler:
    step_type = StepType.CODE_REVIEW

    async def process(self, message: WorkflowMessage, input_artifact: Artifact) -> StepResult:
        files = (input_artifact.content or {}).get("files", [])
        findings = []
        for file in files:
            content = file.get("content", "")
            if "TODO" in content:
                findings.append({"path": file.get("path"), "message": "Generated code contains TODO."})

        decision = ReviewDecision.FAIL if findings else ReviewDecision.PASS
        return StepResult(
            output_artifact_type=ArtifactType.REVIEW_RESULT,
            output_content={"decision": decision.value, "findings": findings},
            output_metadata={"source_artifact_id": message.input_artifact_id},
            next_step_type=None,
        )
