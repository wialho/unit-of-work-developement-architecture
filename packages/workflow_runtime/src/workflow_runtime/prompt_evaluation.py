from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from workflow_runtime.llm import LLMClient, LLMRequest, LLMResponse
from workflow_runtime.prompt_registry import PromptTemplate, load_prompt_template


@dataclass(frozen=True)
class PromptEvaluationCriterion:
    name: str
    description: str
    max_points: int


@dataclass(frozen=True)
class PromptEvaluationRubric:
    name: str
    version: str
    criteria: tuple[PromptEvaluationCriterion, ...]
    passing_score: int

    @property
    def max_score(self) -> int:
        return sum(criterion.max_points for criterion in self.criteria)


@dataclass(frozen=True)
class PromptEvaluationRequest:
    prompt_text: str
    rubric: PromptEvaluationRubric
    context_summary: str | None = None
    candidate_ref: str | None = None


@dataclass(frozen=True)
class PromptEvaluationResult:
    score: int | None
    max_score: int
    passed: bool
    summary: str
    findings: tuple[str, ...]
    suggested_changes: tuple[str, ...]
    provider: str
    model: str
    system_prompt_ref: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] = field(default_factory=dict)


class PromptEvaluator:
    def __init__(
        self,
        llm_client: LLMClient,
        *,
        system_prompt: str | None = None,
        system_prompt_id: str | None = None,
        system_prompt_version: str = "v1",
        max_tokens: int | None = None,
    ) -> None:
        if system_prompt is None and system_prompt_id is None:
            raise ValueError("PromptEvaluator requires system_prompt or system_prompt_id.")
        self._llm_client = llm_client
        self._system_prompt = system_prompt
        self._system_prompt_template: PromptTemplate | None = None
        if system_prompt_id is not None:
            self._system_prompt_template = load_prompt_template(system_prompt_id, system_prompt_version)
            self._system_prompt = self._system_prompt_template.content
        self._max_tokens = max_tokens

    async def evaluate(self, request: PromptEvaluationRequest) -> PromptEvaluationResult:
        response = await self._llm_client.complete(
            LLMRequest(
                system_prompt=self._system_prompt,
                user_prompt=_build_evaluation_prompt(request),
                temperature=0.0,
                max_tokens=self._max_tokens,
            )
        )
        payload = _extract_json_object(response.text)
        score = _int_or_none(payload.get("score"))
        findings = _normalize_string_list(payload.get("findings"))
        suggested_changes = _normalize_string_list(payload.get("suggested_changes"))
        passed = score >= request.rubric.passing_score if score is not None else not findings
        return PromptEvaluationResult(
            score=score,
            max_score=request.rubric.max_score,
            passed=passed,
            summary=str(payload.get("summary", "")),
            findings=findings,
            suggested_changes=suggested_changes,
            provider=response.provider,
            model=response.model,
            system_prompt_ref=self._system_prompt_template.ref if self._system_prompt_template else None,
            metadata=response.metadata,
            raw_payload=payload,
        )


def _build_evaluation_prompt(request: PromptEvaluationRequest) -> str:
    rubric = {
        "name": request.rubric.name,
        "version": request.rubric.version,
        "passing_score": request.rubric.passing_score,
        "max_score": request.rubric.max_score,
        "criteria": [
            {
                "name": criterion.name,
                "description": criterion.description,
                "max_points": criterion.max_points,
            }
            for criterion in request.rubric.criteria
        ],
    }
    payload = {
        "candidate_ref": request.candidate_ref,
        "context_summary": request.context_summary,
        "rubric": rubric,
        "prompt_text": request.prompt_text,
    }
    return (
        "Evaluate the candidate prompt against the rubric. Return only valid JSON with keys "
        "`score`, `summary`, `findings`, and `suggested_changes`.\n\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}"
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    stripped_text = text.strip()
    try:
        payload, _ = decoder.raw_decode(stripped_text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    for index, character in enumerate(stripped_text):
        if character != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(stripped_text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _normalize_string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
