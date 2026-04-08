from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from workflow_contracts import Artifact, ArtifactType, StepResult, StepType, WorkflowMessage
from workflow_runtime.context import ContextBundle, ContextPolicy, ContextResolver
from workflow_runtime.llm import LLMClient, LLMRequest, LLMResponse


@dataclass(frozen=True)
class SelfImprovingPromptStepConfig:
    step_type: StepType
    output_artifact_type: ArtifactType
    next_step_type: StepType | None
    task_system_prompt: str
    prompt_evaluation_system_prompt: str
    prompt_refinement_system_prompt: str
    output_check_system_prompt: str | None = None
    output_repair_system_prompt: str | None = None
    prompt_content_key: str = "prompt"
    output_language: str = "text"
    output_path: str = "generated.txt"
    prompt_pass_score: int = 16
    max_prompt_refinement_iterations: int = 2
    max_output_repair_iterations: int = 1
    task_temperature: float = 0.1
    judge_temperature: float = 0.0
    max_tokens: int | None = None
    rubric_version: str = "v1"
    prompt_refs: dict[str, str] | None = None
    context_policy: ContextPolicy | None = None
    context_resolver: ContextResolver | None = None
    context_extra_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class PromptEvaluation:
    score: int | None
    max_score: int | None
    passed: bool
    payload: dict[str, Any]
    raw_text: str
    response: LLMResponse


@dataclass(frozen=True)
class OutputCheck:
    passed: bool
    payload: dict[str, Any]
    raw_text: str
    response: LLMResponse


class SelfImprovingLLMStepHandler:
    def __init__(self, config: SelfImprovingPromptStepConfig, llm_client: LLMClient) -> None:
        self._config = config
        self._llm_client = llm_client
        self.step_type = config.step_type

    async def process(self, message: WorkflowMessage, input_artifact: Artifact) -> StepResult:
        base_prompt = (input_artifact.content or {}).get(self._config.prompt_content_key, "")
        context_bundle = self._build_context_bundle(input_artifact)
        prompt = self._build_effective_prompt(base_prompt, context_bundle)
        prompt_versions: list[dict[str, Any]] = [
            {
                "iteration": 0,
                "prompt": prompt,
                "prompt_length": len(prompt),
            }
        ]
        prompt_evaluations: list[dict[str, Any]] = []
        prompt_responses: list[LLMResponse] = []
        refinements_completed = 0

        while True:
            iteration = len(prompt_evaluations) + 1
            evaluation = await self._evaluate_prompt(prompt)
            prompt_responses.append(evaluation.response)
            prompt_evaluations.append(
                {
                    "iteration": iteration,
                    "score": evaluation.score,
                    "max_score": evaluation.max_score,
                    "passed": evaluation.passed,
                    "payload": evaluation.payload,
                    "raw_text": evaluation.raw_text,
                }
            )
            if evaluation.passed:
                break
            if refinements_completed >= self._config.max_prompt_refinement_iterations:
                break

            refined_prompt_response = await self._refine_prompt(prompt, evaluation)
            prompt_responses.append(refined_prompt_response)
            prompt = refined_prompt_response.text.strip()
            refinements_completed += 1
            prompt_versions.append(
                {
                    "iteration": refinements_completed,
                    "prompt": prompt,
                    "prompt_length": len(prompt),
                }
            )

        task_response = await self._run_task(prompt)
        output_text = task_response.text
        output_checks: list[dict[str, Any]] = []
        output_responses: list[LLMResponse] = []
        repairs_completed = 0

        while self._config.output_check_system_prompt:
            iteration = len(output_checks) + 1
            output_check = await self._check_output(prompt, output_text)
            output_responses.append(output_check.response)
            output_checks.append(
                {
                    "iteration": iteration,
                    "passed": output_check.passed,
                    "payload": output_check.payload,
                    "raw_text": output_check.raw_text,
                }
            )
            if output_check.passed or not self._config.output_repair_system_prompt:
                break
            if repairs_completed >= self._config.max_output_repair_iterations:
                break

            repair_response = await self._repair_output(prompt, output_text, output_check)
            output_responses.append(repair_response)
            output_text = repair_response.text
            repairs_completed += 1

        return StepResult(
            output_artifact_type=self._config.output_artifact_type,
            output_content={
                "language": self._config.output_language,
                "files": [{"path": self._config.output_path, "content": output_text}],
            },
            output_metadata={
                "llm_provider": task_response.provider,
                "llm_model": task_response.model,
                "prompt_length": len(prompt),
                "source_artifact_id": message.input_artifact_id,
                "self_improvement": {
                    "rubric_version": self._config.rubric_version,
                    "prompt_refs": self._config.prompt_refs or {},
                    "context": context_bundle.to_metadata() if context_bundle else None,
                    "prompt_pass_score": self._config.prompt_pass_score,
                    "prompt_versions": prompt_versions,
                    "prompt_evaluations": prompt_evaluations,
                    "output_checks": output_checks,
                },
                "llm_calls": self._llm_call_metadata(
                    prompt_responses + [task_response] + output_responses
                ),
                **task_response.metadata,
            },
            next_step_type=self._config.next_step_type,
        )

    def _build_context_bundle(self, input_artifact: Artifact) -> ContextBundle | None:
        if self._config.context_policy is None or self._config.context_resolver is None:
            return None
        return self._config.context_resolver.resolve(
            self._config.context_policy,
            input_artifact=input_artifact,
            prompt_refs=self._config.prompt_refs,
            extra_paths=self._config.context_extra_paths,
        )

    def _build_effective_prompt(
        self,
        base_prompt: str,
        context_bundle: ContextBundle | None,
    ) -> str:
        if context_bundle is None or not context_bundle.sources:
            return base_prompt
        return (
            f"{base_prompt}\n\n"
            "Relevant context:\n"
            "Use this context when it helps satisfy the task. Prefer explicit repo context over assumptions.\n\n"
            f"{context_bundle.render_for_prompt()}"
        )

    async def _evaluate_prompt(self, prompt: str) -> PromptEvaluation:
        response = await self._llm_client.complete(
            LLMRequest(
                system_prompt=self._config.prompt_evaluation_system_prompt,
                user_prompt=(
                    "Evaluate this prompt against the rubric. Return only JSON.\n\n"
                    f"Prompt:\n{prompt}"
                ),
                temperature=self._config.judge_temperature,
                max_tokens=self._config.max_tokens,
            )
        )
        payload = _extract_json_object(response.text)
        score = _int_or_none(payload.get("score"))
        max_score = _int_or_none(payload.get("max_score"))
        passed = (
            score >= self._config.prompt_pass_score
            if score is not None
            else _bool_or_default(payload.get("pass"), False)
        )
        return PromptEvaluation(
            score=score,
            max_score=max_score,
            passed=passed,
            payload=payload,
            raw_text=response.text,
            response=response,
        )

    async def _refine_prompt(self, prompt: str, evaluation: PromptEvaluation) -> LLMResponse:
        return await self._llm_client.complete(
            LLMRequest(
                system_prompt=self._config.prompt_refinement_system_prompt,
                user_prompt=(
                    "Improve the prompt using the evaluation. Preserve the original task intent, "
                    "acceptance criteria, and constraints. Return only the revised prompt text.\n\n"
                    f"Current prompt:\n{prompt}\n\n"
                    f"Evaluation JSON:\n{json.dumps(evaluation.payload, sort_keys=True)}"
                ),
                temperature=self._config.task_temperature,
                max_tokens=self._config.max_tokens,
            )
        )

    async def _run_task(self, prompt: str) -> LLMResponse:
        return await self._llm_client.complete(
            LLMRequest(
                system_prompt=self._config.task_system_prompt,
                user_prompt=prompt,
                temperature=self._config.task_temperature,
                max_tokens=self._config.max_tokens,
            )
        )

    async def _check_output(self, prompt: str, output_text: str) -> OutputCheck:
        response = await self._llm_client.complete(
            LLMRequest(
                system_prompt=self._config.output_check_system_prompt,
                user_prompt=(
                    "Review the output against the prompt. Return only JSON.\n\n"
                    f"Prompt:\n{prompt}\n\n"
                    f"Output:\n{output_text}"
                ),
                temperature=self._config.judge_temperature,
                max_tokens=self._config.max_tokens,
            )
        )
        payload = _extract_json_object(response.text)
        passed = _bool_or_default(payload.get("pass"), True)
        return OutputCheck(passed=passed, payload=payload, raw_text=response.text, response=response)

    async def _repair_output(
        self,
        prompt: str,
        output_text: str,
        output_check: OutputCheck,
    ) -> LLMResponse:
        return await self._llm_client.complete(
            LLMRequest(
                system_prompt=self._config.output_repair_system_prompt,
                user_prompt=(
                    "Repair the output using the review findings. Preserve correct work and return "
                    "only the repaired output.\n\n"
                    f"Prompt:\n{prompt}\n\n"
                    f"Current output:\n{output_text}\n\n"
                    f"Review JSON:\n{json.dumps(output_check.payload, sort_keys=True)}"
                ),
                temperature=self._config.task_temperature,
                max_tokens=self._config.max_tokens,
            )
        )

    def _llm_call_metadata(self, responses: list[LLMResponse]) -> list[dict[str, Any]]:
        return [
            {
                "provider": response.provider,
                "model": response.model,
                "metadata": response.metadata,
            }
            for response in responses
        ]


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


def _bool_or_default(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized_value = value.strip().lower()
        if normalized_value in {"true", "pass", "passed", "yes"}:
            return True
        if normalized_value in {"false", "fail", "failed", "no"}:
            return False
    return default
