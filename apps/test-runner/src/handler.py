from __future__ import annotations

from workflow_contracts import Artifact, ArtifactType, StepResult, StepType, WorkflowMessage, WorkflowStatus


FAILURE_QUEUE = "workflow-failures.in"
FAIL_PATTERNS = ("TODO", "NotImplementedError")


class TestRunnerHandler:
    step_type = StepType.TEST_RUNNER

    async def process(self, message: WorkflowMessage, input_artifact: Artifact) -> StepResult:
        content = input_artifact.content or {}
        files = content.get("files", [])
        findings: list[dict[str, str]] = []

        if not files:
            findings.append({"path": "", "message": "No files were generated to test."})

        for file in files:
            path = file.get("path", "")
            file_content = file.get("content", "")
            if not file_content.strip():
                findings.append({"path": path, "message": "Generated file is empty."})
            for pattern in FAIL_PATTERNS:
                if pattern in file_content:
                    findings.append(
                        {
                            "path": path,
                            "message": f"Generated file contains placeholder or unimplemented code: {pattern!r}.",
                        }
                    )
            if any(line.strip() == "pass" for line in file_content.splitlines()):
                findings.append(
                    {
                        "path": path,
                        "message": "Generated file contains a bare pass statement placeholder.",
                    }
                )

        passed = not findings
        return StepResult(
            output_artifact_type=ArtifactType.TEST_RESULT,
            output_content={
                "language": content.get("language"),
                "files": files,
                "prompt": content.get("prompt"),
                "ticket": content.get("ticket"),
                "regeneration_attempt": content.get("regeneration_attempt", 0),
                "test_pass": passed,
                "review_stage": self.step_type.value,
                "findings": findings,
            },
            output_metadata={
                "source_artifact_id": message.input_artifact_id,
                "review_stage": self.step_type.value,
            },
            next_step_type=StepType.REQUIREMENTS_REVIEW if passed else None,
            terminal_workflow_status=None if passed else WorkflowStatus.FAILED,
            terminal_event_type=None if passed else "review_failed_test",
            failure_queue_name=None if passed else FAILURE_QUEUE,
        )
