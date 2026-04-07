from __future__ import annotations

from workflow_contracts import ArtifactType, StepType
from workflow_runtime import LLMClient, PromptLLMStepHandler, PromptStepConfig


class PromptToCodeHandler(PromptLLMStepHandler):
    def __init__(self, llm_client: LLMClient) -> None:
        super().__init__(
            PromptStepConfig(
                step_type=StepType.PROMPT_TO_CODE,
                output_artifact_type=ArtifactType.CODE_ARTIFACT,
                next_step_type=StepType.CODE_REVIEW,
                system_prompt=(
                    "You generate code artifacts for a workflow pipeline. "
                    "Return concise source code or structured implementation notes only."
                ),
                prompt_content_key="prompt",
                output_language="text",
                output_path="generated.txt",
                temperature=0.1,
            ),
            llm_client,
        )
