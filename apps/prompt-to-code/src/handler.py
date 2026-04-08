from __future__ import annotations

import os

from workflow_contracts import ArtifactType, StepType
from workflow_runtime import (
    ContextPolicy,
    DeterministicContextResolver,
    LLMClient,
    SelfImprovingLLMStepHandler,
    SelfImprovingPromptStepConfig,
    load_prompt_template,
)


PROMPT_VERSION = os.getenv("PROMPT_TO_CODE_PROMPT_VERSION", "v1")
PROMPT_IDS = {
    "task_system": "prompt-to-code/task-system",
    "prompt_evaluation": "prompt-to-code/prompt-evaluation",
    "prompt_refinement": "prompt-to-code/prompt-refinement",
    "output_check": "prompt-to-code/output-check",
    "output_repair": "prompt-to-code/output-repair",
}


class PromptToCodeHandler(SelfImprovingLLMStepHandler):
    def __init__(self, llm_client: LLMClient) -> None:
        prompts = {
            name: load_prompt_template(prompt_id, PROMPT_VERSION)
            for name, prompt_id in PROMPT_IDS.items()
        }
        context_policy = ContextPolicy.from_env(
            "prompt-to-code",
            name="prompt-to-code-default",
            always_include_paths=("README.md",),
            path_globs=(
                "packages/workflow_contracts/src/workflow_contracts/*.py",
                "packages/workflow_runtime/src/workflow_runtime/*.py",
            ),
            max_files=8,
            max_chars=18_000,
        )
        super().__init__(
            SelfImprovingPromptStepConfig(
                step_type=StepType.PROMPT_TO_CODE,
                output_artifact_type=ArtifactType.CODE_ARTIFACT,
                next_step_type=StepType.TEST_RUNNER,
                task_system_prompt=prompts["task_system"].content,
                prompt_evaluation_system_prompt=prompts["prompt_evaluation"].content,
                prompt_refinement_system_prompt=prompts["prompt_refinement"].content,
                output_check_system_prompt=prompts["output_check"].content,
                output_repair_system_prompt=prompts["output_repair"].content,
                prompt_content_key="prompt",
                output_language="text",
                output_path="generated.txt",
                task_temperature=0.1,
                judge_temperature=0.0,
                prompt_pass_score=16,
                max_prompt_refinement_iterations=2,
                max_output_repair_iterations=1,
                rubric_version="prompt-to-code-v1",
                prompt_refs={name: prompt.ref for name, prompt in prompts.items()},
                context_policy=context_policy,
                context_resolver=DeterministicContextResolver(),
                context_extra_paths=(),
                preserved_input_content_keys=("prompt", "ticket"),
            ),
            llm_client,
        )
