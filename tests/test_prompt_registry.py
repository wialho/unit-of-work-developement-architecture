from __future__ import annotations

from workflow_runtime.prompt_registry import load_prompt_template


def test_load_prompt_template_from_registry_root(tmp_path) -> None:
    registry_root = tmp_path / "prompts"
    prompt_dir = registry_root / "example"
    prompt_dir.mkdir(parents=True)
    prompt_path = prompt_dir / "task-v2.md"
    prompt_path.write_text("Prompt content\n", encoding="utf-8")

    prompt = load_prompt_template("example/task", "v2", registry_root)

    assert prompt.content == "Prompt content"
    assert prompt.ref == "example/task-v2"
    assert prompt.path == prompt_path
