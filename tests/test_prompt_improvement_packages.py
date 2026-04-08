from __future__ import annotations

import asyncio

from workflow_runtime import (
    LLMRequest,
    LLMResponse,
    PromptEvaluationCriterion,
    PromptEvaluationRequest,
    PromptEvaluationRubric,
    PromptEvaluator,
    PromptGenerationRequest,
    PromptGenerator,
    PromptOutcomeRecord,
    PromptPromotionPolicy,
    PromptPromoter,
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
            metadata={"finish_reason": "stop"},
        )

    async def close(self) -> None:
        return None


def test_prompt_generator_builds_prompt_from_structured_request() -> None:
    client = FakeLLMClient(["Generated prompt text"])
    generator = PromptGenerator(client, system_prompt="Generate reusable prompts.")

    result = asyncio.run(
        generator.generate(
            PromptGenerationRequest(
                goal="Create a code review prompt",
                audience="code-review",
                why="Improve consistency",
                constraints=("JSON only", "No markdown fences"),
                context_items=("README.md summary",),
                required_sections=("Goal", "Constraints"),
            )
        )
    )

    assert result.prompt_text == "Generated prompt text"
    assert client.requests[0].system_prompt == "Generate reusable prompts."
    assert "Create a code review prompt" in client.requests[0].user_prompt


def test_prompt_evaluator_parses_structured_scores() -> None:
    client = FakeLLMClient(
        [
            '{"score": 17, "summary": "Solid prompt", "findings": ["Needs clearer output contract"], "suggested_changes": ["Add expected JSON schema"]}'
        ]
    )
    evaluator = PromptEvaluator(client, system_prompt="Evaluate prompts.")
    rubric = PromptEvaluationRubric(
        name="review-prompt",
        version="v1",
        passing_score=16,
        criteria=(
            PromptEvaluationCriterion("clarity", "Task is clear", 5),
            PromptEvaluationCriterion("constraints", "Constraints are explicit", 5),
            PromptEvaluationCriterion("output", "Output format is explicit", 5),
            PromptEvaluationCriterion("context", "Context is sufficient", 5),
        ),
    )

    result = asyncio.run(
        evaluator.evaluate(
            PromptEvaluationRequest(
                prompt_text="Review generated code and return JSON.",
                rubric=rubric,
                candidate_ref="code-review/system-v2",
            )
        )
    )

    assert result.score == 17
    assert result.passed is True
    assert result.findings == ("Needs clearer output contract",)
    assert result.suggested_changes == ("Add expected JSON schema",)


def test_prompt_promoter_promotes_better_candidate() -> None:
    promoter = PromptPromoter()
    candidate_outcomes = [
        PromptOutcomeRecord("candidate-v2", "prompt-to-code", f"wr_{index}", True, True, True, True)
        for index in range(12)
    ]
    baseline_outcomes = [
        PromptOutcomeRecord(
            "active-v1",
            "prompt-to-code",
            f"wr_b_{index}",
            index % 2 == 0,
            True,
            True,
            index % 2 == 0,
        )
        for index in range(12)
    ]

    decision = promoter.decide(
        "candidate-v2",
        candidate_outcomes,
        policy=PromptPromotionPolicy(minimum_samples=10, minimum_workflow_pass_rate_delta=0.1),
        baseline_outcomes=baseline_outcomes,
    )

    assert decision.action == "promote"
    assert decision.summary.sample_count == 12
    assert decision.summary.workflow_pass_rate == 1.0
