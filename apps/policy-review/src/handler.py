from __future__ import annotations

from workflow_contracts import Artifact, ArtifactType, StepResult, StepType, WorkflowMessage, WorkflowStatus


FAILURE_QUEUE = "workflow-failures.in"


class PolicyReviewHandler:
    step_type = StepType.POLICY_REVIEW

    async def process(self, message: WorkflowMessage, input_artifact: Artifact) -> StepResult:
        content = input_artifact.content or {}
        files = content.get("files", [])
        findings: list[dict[str, str]] = []
        seen_paths: set[str] = set()

        if content.get("language") != "text":
            findings.append({"path": "", "message": "Generated artifact language must be 'text'."})

        for file in files:
            path = file.get("path", "")
            file_content = file.get("content", "")
            if not path:
                findings.append({"path": "", "message": "Generated file is missing a path."})
                continue
            if path in seen_paths:
                findings.append({"path": path, "message": "Generated artifact contains duplicate file paths."})
            seen_paths.add(path)
            if path.startswith("/") or ".." in path.split("/"):
                findings.append({"path": path, "message": "Generated file path must be repository-relative."})
            if len(file_content) > 100_000:
                findings.append({"path": path, "message": "Generated file content exceeds policy size limit."})

        passed = not findings
        return StepResult(
            output_artifact_type=ArtifactType.POLICY_REVIEW_RESULT,
            output_content={
                "language": content.get("language"),
                "files": files,
                "prompt": content.get("prompt"),
                "ticket": content.get("ticket"),
                "regeneration_attempt": content.get("regeneration_attempt", 0),
                "test_pass": content.get("test_pass"),
                "requirements_pass": content.get("requirements_pass"),
                "policy_pass": passed,
                "review_stage": self.step_type.value,
                "findings": findings,
            },
            output_metadata={
                "source_artifact_id": message.input_artifact_id,
                "review_stage": self.step_type.value,
            },
            next_step_type=StepType.CODE_REVIEW if passed else None,
            terminal_workflow_status=None if passed else WorkflowStatus.FAILED,
            terminal_event_type=None if passed else "review_failed_policy",
            failure_queue_name=None if passed else FAILURE_QUEUE,
        )
