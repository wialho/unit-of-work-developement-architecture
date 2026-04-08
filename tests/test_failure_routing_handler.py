from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from workflow_contracts import Artifact, ArtifactType, StepType, WorkflowMessage, WorkflowStatus


def _load_failure_routing_handler():
    handler_path = (
        Path(__file__).resolve().parents[1] / "apps" / "failure-routing" / "src" / "handler.py"
    )
    spec = importlib.util.spec_from_file_location("failure_routing_handler", handler_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.FailureRoutingHandler


def test_failure_routing_regenerates_once() -> None:
    handler = _load_failure_routing_handler()()

    result = asyncio.run(
        handler.process(
            WorkflowMessage(
                workflow_run_id="wr_123",
                workflow_step_id="ws_123",
                step_type=StepType.FAILURE_ROUTING,
                input_artifact_id="art_123",
                trace_id="tr_123",
            ),
            Artifact(
                id="art_123",
                workflow_run_id="wr_123",
                artifact_type=ArtifactType.TEST_RESULT,
                content={
                    "prompt": "Implement feature X",
                    "ticket": {"title": "Feature X"},
                    "review_stage": "test_runner",
                    "findings": [{"path": "generated.py", "message": "Generated file is empty."}],
                    "regeneration_attempt": 0,
                },
                content_ref=None,
                metadata={"review_stage": "test_runner"},
                created_by_service="test-runner",
            ),
        )
    )

    assert result.output_artifact_type == ArtifactType.PROMPT
    assert result.next_step_type == StepType.PROMPT_TO_CODE
    assert result.next_step_attempt == 2
    assert result.workflow_status_override == WorkflowStatus.RUNNING
    assert "Regeneration attempt 1:" in result.output_content["prompt"]
    assert "test_runner" in result.output_content["prompt"]


def test_failure_routing_sends_failed_regeneration_to_human_review() -> None:
    handler = _load_failure_routing_handler()()

    result = asyncio.run(
        handler.process(
            WorkflowMessage(
                workflow_run_id="wr_123",
                workflow_step_id="ws_124",
                step_type=StepType.FAILURE_ROUTING,
                input_artifact_id="art_124",
                trace_id="tr_123",
            ),
            Artifact(
                id="art_124",
                workflow_run_id="wr_123",
                artifact_type=ArtifactType.REVIEW_RESULT,
                content={
                    "prompt": "Implement feature X",
                    "ticket": {"title": "Feature X"},
                    "review_stage": "code_review",
                    "findings": [{"path": "generated.py", "message": "Logic is incorrect."}],
                    "regeneration_attempt": 1,
                },
                content_ref=None,
                metadata={"review_stage": "code_review"},
                created_by_service="code-review",
            ),
        )
    )

    assert result.output_artifact_type == ArtifactType.FAILURE_RESULT
    assert result.next_step_type == StepType.HUMAN_REVIEW
    assert result.workflow_status_override == WorkflowStatus.FAILED
    assert result.output_content["route"] == "human_review"
