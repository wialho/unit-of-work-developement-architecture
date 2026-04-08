from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from workflow_contracts import Artifact, ArtifactType, StepType, WorkflowMessage, WorkflowStatus


def _load_test_runner_handler():
    handler_path = (
        Path(__file__).resolve().parents[1] / "apps" / "test-runner" / "src" / "handler.py"
    )
    spec = importlib.util.spec_from_file_location("test_runner_handler", handler_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.TestRunnerHandler


def test_test_runner_fails_placeholder_code_and_terminates_workflow() -> None:
    handler = _load_test_runner_handler()()

    result = asyncio.run(
        handler.process(
            WorkflowMessage(
                workflow_run_id="wr_123",
                workflow_step_id="ws_123",
                step_type=StepType.TEST_RUNNER,
                input_artifact_id="art_123",
                trace_id="tr_123",
            ),
            Artifact(
                id="art_123",
                workflow_run_id="wr_123",
                artifact_type=ArtifactType.CODE_ARTIFACT,
                content={
                    "language": "text",
                    "files": [{"path": "generated.py", "content": "def run():\n    pass\n"}],
                    "prompt": "Implement run",
                    "ticket": {"title": "Run"},
                },
                content_ref=None,
                metadata={},
                created_by_service="prompt-to-code",
            ),
        )
    )

    assert result.output_artifact_type == ArtifactType.TEST_RESULT
    assert result.next_step_type is None
    assert result.terminal_workflow_status == WorkflowStatus.FAILED
    assert result.failure_queue_name == "workflow-failures.in"
    assert result.output_content["test_pass"] is False
