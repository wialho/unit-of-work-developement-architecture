from __future__ import annotations

import asyncio

from workflow_contracts import Artifact, ArtifactType, StepType, WorkflowMessage
from workflow_runtime import LLMRequest, LLMResponse
from workflow_runtime.self_improving_prompt_step import (
    SelfImprovingLLMStepHandler,
    SelfImprovingPromptStepConfig,
)


class FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            text=self._responses.pop(0),
            model="fake-model",
            provider="fake-provider",
            metadata={},
        )

    async def close(self) -> None:
        return None


def test_self_improving_handler_refines_and_repairs_output() -> None:
    client = FakeLLMClient(
        [
            '{"score": 10, "max_score": 20, "pass": false, "violations": ["too vague"]}',
            "Refined prompt with explicit acceptance criteria.",
            '{"score": 18, "max_score": 20, "pass": true, "violations": []}',
            "Generated output with TODO",
            '{"pass": false, "findings": ["contains TODO"]}',
            "Generated output without placeholders.",
            '{"pass": true, "findings": []}',
        ]
    )
    handler = SelfImprovingLLMStepHandler(
        SelfImprovingPromptStepConfig(
            step_type=StepType.PROMPT_TO_CODE,
            output_artifact_type=ArtifactType.CODE_ARTIFACT,
            next_step_type=StepType.CODE_REVIEW,
            task_system_prompt="Generate code.",
            prompt_evaluation_system_prompt="Evaluate prompt.",
            prompt_refinement_system_prompt="Refine prompt.",
            output_check_system_prompt="Check output.",
            output_repair_system_prompt="Repair output.",
            prompt_pass_score=16,
            max_prompt_refinement_iterations=2,
            max_output_repair_iterations=1,
            prompt_refs={"task_system": "prompt-to-code/task-system-v1"},
        ),
        client,
    )

    result = asyncio.run(
        handler.process(
            WorkflowMessage(
                workflow_run_id="wr_123",
                workflow_step_id="ws_123",
                step_type=StepType.PROMPT_TO_CODE,
                input_artifact_id="art_123",
                trace_id="tr_123",
            ),
            Artifact(
                id="art_123",
                workflow_run_id="wr_123",
                artifact_type=ArtifactType.PROMPT,
                content={"prompt": "Initial prompt."},
                content_ref=None,
                metadata={},
                created_by_service="ticket-to-prompt",
            ),
        )
    )

    assert result.output_artifact_type == ArtifactType.CODE_ARTIFACT
    assert result.next_step_type == StepType.CODE_REVIEW
    assert result.output_content == {
        "language": "text",
        "files": [{"path": "generated.txt", "content": "Generated output without placeholders."}],
    }
    assert len(client.requests) == 7
    assert result.output_metadata["self_improvement"]["prompt_evaluations"][0]["score"] == 10
    assert result.output_metadata["self_improvement"]["prompt_evaluations"][1]["score"] == 18
    assert result.output_metadata["self_improvement"]["output_checks"][0]["passed"] is False
    assert result.output_metadata["self_improvement"]["output_checks"][1]["passed"] is True
    assert result.output_metadata["self_improvement"]["prompt_refs"] == {
        "task_system": "prompt-to-code/task-system-v1"
    }
