from __future__ import annotations

from dataclasses import dataclass

from workflow_contracts import Artifact, ArtifactType, StepResult, StepType, WorkflowMessage
from workflow_runtime.llm import LLMClient, LLMRequest


@dataclass(frozen=True)
class PromptStepConfig:
    step_type: StepType
    output_artifact_type: ArtifactType
    next_step_type: StepType | None
    system_prompt: str
    prompt_content_key: str = "prompt"
    output_language: str = "text"
    output_path: str = "generated.txt"
    temperature: float = 0.1
    max_tokens: int | None = None


class PromptLLMStepHandler:
    def __init__(self, config: PromptStepConfig, llm_client: LLMClient) -> None:
        self._config = config
        self._llm_client = llm_client
        self.step_type = config.step_type

    async def process(self, message: WorkflowMessage, input_artifact: Artifact) -> StepResult:
        prompt = (input_artifact.content or {}).get(self._config.prompt_content_key, "")
        response = await self._llm_client.complete(
            LLMRequest(
                system_prompt=self._config.system_prompt,
                user_prompt=prompt,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
            )
        )
        return StepResult(
            output_artifact_type=self._config.output_artifact_type,
            output_content={
                "language": self._config.output_language,
                "files": [{"path": self._config.output_path, "content": response.text}],
            },
            output_metadata={
                "llm_provider": response.provider,
                "llm_model": response.model,
                "prompt_length": len(prompt),
                "source_artifact_id": message.input_artifact_id,
                **response.metadata,
            },
            next_step_type=self._config.next_step_type,
        )
