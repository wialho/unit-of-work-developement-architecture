from __future__ import annotations

from workflow_contracts import Artifact, ArtifactType
from workflow_runtime.context import ContextPolicy, DeterministicContextResolver


def test_deterministic_context_resolver_collects_artifact_and_repo_sources(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "packages").mkdir(parents=True)
    (repo_root / "README.md").write_text("Repo overview\n", encoding="utf-8")
    runtime_dir = repo_root / "packages" / "workflow_runtime" / "src" / "workflow_runtime"
    runtime_dir.mkdir(parents=True)
    worker_path = runtime_dir / "worker.py"
    worker_path.write_text("class StepWorker: ...\n", encoding="utf-8")
    prompts_dir = repo_root / "prompts" / "prompt-to-code"
    prompts_dir.mkdir(parents=True)
    prompt_path = prompts_dir / "task-system-v1.md"
    prompt_path.write_text("Task prompt\n", encoding="utf-8")

    policy = ContextPolicy(
        name="prompt-to-code-default",
        always_include_paths=("README.md",),
        path_globs=("packages/workflow_runtime/src/workflow_runtime/*.py",),
        max_files=4,
        max_chars=1_000,
    )
    bundle = DeterministicContextResolver(repo_root=repo_root).resolve(
        policy,
        input_artifact=Artifact(
            id="art_123",
            workflow_run_id="wr_123",
            artifact_type=ArtifactType.PROMPT,
            content={"prompt": "Implement feature X"},
            content_ref=None,
            metadata={},
            created_by_service="ticket-to-prompt",
        ),
        prompt_refs={"task_system": "prompt-to-code/task-system-v1"},
    )

    assert bundle.policy.name == "prompt-to-code-default"
    assert [source.path for source in bundle.sources] == [
        "artifact:art_123",
        "prompts/prompt-to-code/task-system-v1.md",
        "README.md",
        "packages/workflow_runtime/src/workflow_runtime/worker.py",
    ]
    assert bundle.sources[1].reason == "prompt_ref:task_system"
    assert bundle.char_count > 0
