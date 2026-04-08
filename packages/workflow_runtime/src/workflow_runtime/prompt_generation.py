from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from workflow_runtime.llm import LLMClient, LLMRequest, LLMResponse
from workflow_runtime.prompt_registry import PromptTemplate, load_prompt_template


@dataclass(frozen=True)
class PromptGenerationRequest:
    goal: str
    audience: str | None = None
    why: str | None = None
    tone: str | None = None
    constraints: tuple[str, ...] = ()
    context_items: tuple[str, ...] = ()
    required_sections: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    counterexamples: tuple[str, ...] = ()
    output_format: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PromptGenerationResult:
    prompt_text: str
    system_prompt_ref: str | None
    provider: str
    model: str
    metadata: dict[str, Any] = field(default_factory=dict)


class PromptGenerator:
    def __init__(
        self,
        llm_client: LLMClient,
        *,
        system_prompt: str | None = None,
        system_prompt_id: str | None = None,
        system_prompt_version: str = "v1",
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> None:
        if system_prompt is None and system_prompt_id is None:
            raise ValueError("PromptGenerator requires system_prompt or system_prompt_id.")
        self._llm_client = llm_client
        self._system_prompt = system_prompt
        self._system_prompt_template: PromptTemplate | None = None
        if system_prompt_id is not None:
            self._system_prompt_template = load_prompt_template(system_prompt_id, system_prompt_version)
            self._system_prompt = self._system_prompt_template.content
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def generate(self, request: PromptGenerationRequest) -> PromptGenerationResult:
        response = await self._llm_client.complete(
            LLMRequest(
                system_prompt=self._system_prompt,
                user_prompt=_build_generation_prompt(request),
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
        )
        return PromptGenerationResult(
            prompt_text=response.text.strip(),
            system_prompt_ref=self._system_prompt_template.ref if self._system_prompt_template else None,
            provider=response.provider,
            model=response.model,
            metadata=response.metadata,
        )


def _build_generation_prompt(request: PromptGenerationRequest) -> str:
    payload = {
        "goal": request.goal,
        "audience": request.audience,
        "why": request.why,
        "tone": request.tone,
        "constraints": list(request.constraints),
        "context_items": list(request.context_items),
        "required_sections": list(request.required_sections),
        "examples": list(request.examples),
        "counterexamples": list(request.counterexamples),
        "output_format": request.output_format,
        "metadata": request.metadata,
    }
    return (
        "Generate a reusable prompt from the following structured request. "
        "Return only the final prompt text.\n\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}"
    )
