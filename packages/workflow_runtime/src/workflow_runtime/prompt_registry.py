from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptTemplate:
    prompt_id: str
    version: str
    content: str
    path: Path

    @property
    def ref(self) -> str:
        return f"{self.prompt_id}-{self.version}"


def load_prompt(prompt_id: str, version: str = "v1", registry_root: str | Path | None = None) -> str:
    return load_prompt_template(prompt_id, version, registry_root).content


def load_prompt_template(
    prompt_id: str,
    version: str = "v1",
    registry_root: str | Path | None = None,
) -> PromptTemplate:
    root = _resolve_registry_root(registry_root)
    path = root / f"{prompt_id}-{version}.md"
    if not path.is_file():
        raise FileNotFoundError(
            f"Prompt template not found: {prompt_id}-{version}.md under {root}"
        )
    return PromptTemplate(
        prompt_id=prompt_id,
        version=version,
        content=path.read_text(encoding="utf-8").strip(),
        path=path,
    )


def _resolve_registry_root(registry_root: str | Path | None) -> Path:
    if registry_root is not None:
        return Path(registry_root).expanduser().resolve()

    configured_root = os.getenv("PROMPT_REGISTRY_ROOT")
    if configured_root:
        return Path(configured_root).expanduser().resolve()

    for parent in [Path.cwd(), *Path.cwd().parents]:
        candidate = parent / "prompts"
        if candidate.is_dir():
            return candidate.resolve()

    package_path = Path(__file__).resolve()
    for parent in package_path.parents:
        candidate = parent / "prompts"
        if candidate.is_dir():
            return candidate.resolve()

    raise FileNotFoundError(
        "Prompt registry root not found. Set PROMPT_REGISTRY_ROOT or run from a tree "
        "containing a prompts/ directory."
    )
