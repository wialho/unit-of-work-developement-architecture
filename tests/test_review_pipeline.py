from __future__ import annotations

import asyncio

from workflow_contracts import Artifact, ArtifactType, StepResult, StepType, WorkflowMessage, WorkflowStatus
from workflow_runtime.worker import StepWorker


class FakeDatabase:
    def __init__(self, artifact: Artifact) -> None:
        self.artifact = artifact
        self.events: list[tuple[str, dict | None]] = []
        self.completed_steps: list[tuple[str, str]] = []
        self.failed_workflows: list[str] = []
        self.created_artifacts: list[dict] = []
        self.created_steps: list[dict] = []

    async def connect(self) -> None:
        return None

    async def claim_step_for_processing(self, step_id: str) -> bool:
        return True

    async def record_event(
        self,
        workflow_run_id: str,
        workflow_step_id: str | None,
        service_name: str,
        event_type: str,
        trace_id: str,
        payload: dict | None = None,
    ) -> None:
        self.events.append((event_type, payload))

    async def get_artifact(self, artifact_id: str) -> Artifact:
        return self.artifact

    async def create_artifact(self, **kwargs) -> None:
        self.created_artifacts.append(kwargs)

    async def mark_step_completed(self, step_id: str, output_artifact_id: str) -> None:
        self.completed_steps.append((step_id, output_artifact_id))

    async def mark_workflow_failed(self, workflow_run_id: str) -> None:
        self.failed_workflows.append(workflow_run_id)

    async def mark_workflow_completed(self, workflow_run_id: str) -> None:
        raise AssertionError("workflow should not complete on review failure")

    async def create_workflow_step(self, **kwargs):
        self.created_steps.append(kwargs)
        return kwargs["step_id"]

    async def mark_step_failed(self, step_id: str, error: dict) -> None:
        raise AssertionError("handler should not raise")


class FakeQueue:
    def __init__(self) -> None:
        self.published: list[tuple[str, WorkflowMessage]] = []

    async def connect(self) -> None:
        return None

    async def consume(self, queue_name: str, handler) -> None:
        return None

    async def publish(self, queue_name: str, message: WorkflowMessage) -> None:
        self.published.append((queue_name, message))


class FailingReviewHandler:
    step_type = StepType.TEST_RUNNER

    async def process(self, message: WorkflowMessage, input_artifact: Artifact) -> StepResult:
        return StepResult(
            output_artifact_type=ArtifactType.TEST_RESULT,
            output_content={"test_pass": False, "files": []},
            output_metadata={},
            terminal_workflow_status=WorkflowStatus.FAILED,
            terminal_event_type="review_failed_test",
            failure_queue_name="workflow-failures.in",
        )


def test_worker_routes_terminal_review_failures_to_failure_queue() -> None:
    artifact = Artifact(
        id="art_123",
        workflow_run_id="wr_123",
        artifact_type=ArtifactType.CODE_ARTIFACT,
        content={"files": []},
        content_ref=None,
        metadata={},
        created_by_service="prompt-to-code",
    )
    db = FakeDatabase(artifact)
    queue = FakeQueue()
    worker = StepWorker(
        service_name="test-runner",
        db=db,
        queue=queue,
        handler=FailingReviewHandler(),
    )

    asyncio.run(
        worker._handle(
            WorkflowMessage(
                workflow_run_id="wr_123",
                workflow_step_id="ws_123",
                step_type=StepType.TEST_RUNNER,
                input_artifact_id="art_123",
                trace_id="tr_123",
            )
        )
    )

    assert db.failed_workflows == ["wr_123"]
    assert queue.published[0][0] == "workflow-failures.in"
    assert queue.published[0][1].step_type == StepType.FAILURE_ROUTING
    assert db.created_steps[0]["step_type"] == StepType.FAILURE_ROUTING
    assert ("review_failed_test", {"output_artifact_id": db.completed_steps[0][1]}) in db.events
    assert any(event_type == "workflow_failure_published" for event_type, _ in db.events)
