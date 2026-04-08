from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptOutcomeRecord:
    prompt_ref: str
    service_name: str
    workflow_run_id: str
    test_pass: bool
    requirements_pass: bool
    policy_pass: bool
    review_pass: bool
    repair_iterations: int = 0

    @property
    def workflow_pass(self) -> bool:
        return self.test_pass and self.requirements_pass and self.policy_pass and self.review_pass


@dataclass(frozen=True)
class PromptPerformanceSummary:
    prompt_ref: str
    sample_count: int
    workflow_pass_rate: float
    test_pass_rate: float
    requirements_pass_rate: float
    policy_pass_rate: float
    review_pass_rate: float
    average_repair_iterations: float


@dataclass(frozen=True)
class PromptPromotionPolicy:
    minimum_samples: int = 10
    minimum_workflow_pass_rate: float = 0.6
    minimum_test_pass_rate: float = 0.6
    minimum_requirements_pass_rate: float = 0.6
    minimum_policy_pass_rate: float = 0.95
    minimum_review_pass_rate: float = 0.6
    maximum_average_repair_iterations: float = 1.0
    minimum_workflow_pass_rate_delta: float = 0.0


@dataclass(frozen=True)
class PromptPromotionDecision:
    candidate_ref: str
    action: str
    reason: str
    summary: PromptPerformanceSummary
    baseline_summary: PromptPerformanceSummary | None = None


class PromptPromoter:
    def summarize(self, prompt_ref: str, outcomes: list[PromptOutcomeRecord]) -> PromptPerformanceSummary:
        if not outcomes:
            return PromptPerformanceSummary(
                prompt_ref=prompt_ref,
                sample_count=0,
                workflow_pass_rate=0.0,
                test_pass_rate=0.0,
                requirements_pass_rate=0.0,
                policy_pass_rate=0.0,
                review_pass_rate=0.0,
                average_repair_iterations=0.0,
            )
        sample_count = len(outcomes)
        return PromptPerformanceSummary(
            prompt_ref=prompt_ref,
            sample_count=sample_count,
            workflow_pass_rate=sum(outcome.workflow_pass for outcome in outcomes) / sample_count,
            test_pass_rate=sum(outcome.test_pass for outcome in outcomes) / sample_count,
            requirements_pass_rate=sum(outcome.requirements_pass for outcome in outcomes) / sample_count,
            policy_pass_rate=sum(outcome.policy_pass for outcome in outcomes) / sample_count,
            review_pass_rate=sum(outcome.review_pass for outcome in outcomes) / sample_count,
            average_repair_iterations=sum(outcome.repair_iterations for outcome in outcomes) / sample_count,
        )

    def decide(
        self,
        candidate_ref: str,
        candidate_outcomes: list[PromptOutcomeRecord],
        *,
        policy: PromptPromotionPolicy,
        baseline_outcomes: list[PromptOutcomeRecord] | None = None,
    ) -> PromptPromotionDecision:
        summary = self.summarize(candidate_ref, candidate_outcomes)
        baseline_summary = (
            self.summarize(baseline_outcomes[0].prompt_ref, baseline_outcomes)
            if baseline_outcomes
            else None
        )

        if summary.sample_count < policy.minimum_samples:
            return PromptPromotionDecision(
                candidate_ref=candidate_ref,
                action="keep_candidate",
                reason="Insufficient sample count for promotion.",
                summary=summary,
                baseline_summary=baseline_summary,
            )

        threshold_failures = [
            summary.workflow_pass_rate < policy.minimum_workflow_pass_rate,
            summary.test_pass_rate < policy.minimum_test_pass_rate,
            summary.requirements_pass_rate < policy.minimum_requirements_pass_rate,
            summary.policy_pass_rate < policy.minimum_policy_pass_rate,
            summary.review_pass_rate < policy.minimum_review_pass_rate,
            summary.average_repair_iterations > policy.maximum_average_repair_iterations,
        ]
        if any(threshold_failures):
            return PromptPromotionDecision(
                candidate_ref=candidate_ref,
                action="reject",
                reason="Candidate prompt does not meet the minimum promotion thresholds.",
                summary=summary,
                baseline_summary=baseline_summary,
            )

        if baseline_summary is not None:
            if (
                summary.workflow_pass_rate
                < baseline_summary.workflow_pass_rate + policy.minimum_workflow_pass_rate_delta
            ):
                return PromptPromotionDecision(
                    candidate_ref=candidate_ref,
                    action="keep_candidate",
                    reason="Candidate prompt is not yet materially better than the baseline.",
                    summary=summary,
                    baseline_summary=baseline_summary,
                )

        return PromptPromotionDecision(
            candidate_ref=candidate_ref,
            action="promote",
            reason="Candidate prompt meets promotion thresholds.",
            summary=summary,
            baseline_summary=baseline_summary,
        )
