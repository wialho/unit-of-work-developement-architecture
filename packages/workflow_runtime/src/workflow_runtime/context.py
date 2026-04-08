from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from workflow_contracts import Artifact


@dataclass(frozen=True)
class ContextPolicy:
    name: str
    version: str = "v1"
    mode: str = "deterministic"
    enabled: bool = True
    include_artifact_content: bool = True
    include_prompt_files: bool = True
    always_include_paths: tuple[str, ...] = ()
    path_globs: tuple[str, ...] = ()
    allowed_extensions: tuple[str, ...] = (".md", ".py", ".sql", ".yaml", ".yml", ".ts", ".tsx")
    max_files: int = 8
    max_chars: int = 18_000

    @classmethod
    def from_env(
        cls,
        service_name: str,
        *,
        name: str,
        version: str = "v1",
        always_include_paths: tuple[str, ...] = (),
        path_globs: tuple[str, ...] = (),
        allowed_extensions: tuple[str, ...] = (".md", ".py", ".sql", ".yaml", ".yml", ".ts", ".tsx"),
        max_files: int = 8,
        max_chars: int = 18_000,
    ) -> "ContextPolicy":
        service_env_prefix = service_name.upper().replace("-", "_")
        return cls(
            name=name,
            version=_service_env(service_env_prefix, "CONTEXT_POLICY_VERSION", version),
            mode=_service_env(service_env_prefix, "CONTEXT_MODE", "deterministic"),
            enabled=_env_bool(_service_env(service_env_prefix, "CONTEXT_ENABLED", "true")),
            include_artifact_content=_env_bool(
                _service_env(service_env_prefix, "CONTEXT_INCLUDE_ARTIFACT_CONTENT", "true")
            ),
            include_prompt_files=_env_bool(
                _service_env(service_env_prefix, "CONTEXT_INCLUDE_PROMPT_FILES", "true")
            ),
            always_include_paths=_csv_env_tuple(
                _service_env(
                    service_env_prefix,
                    "CONTEXT_ALWAYS_INCLUDE",
                    ",".join(always_include_paths),
                )
            ),
            path_globs=_csv_env_tuple(
                _service_env(
                    service_env_prefix,
                    "CONTEXT_PATH_GLOBS",
                    ",".join(path_globs),
                )
            ),
            allowed_extensions=_csv_env_tuple(
                _service_env(
                    service_env_prefix,
                    "CONTEXT_ALLOWED_EXTENSIONS",
                    ",".join(allowed_extensions),
                )
            ),
            max_files=_env_int(_service_env(service_env_prefix, "CONTEXT_MAX_FILES", str(max_files)), max_files),
            max_chars=_env_int(_service_env(service_env_prefix, "CONTEXT_MAX_CHARS", str(max_chars)), max_chars),
        )

    def to_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "mode": self.mode,
            "enabled": self.enabled,
            "include_artifact_content": self.include_artifact_content,
            "include_prompt_files": self.include_prompt_files,
            "always_include_paths": list(self.always_include_paths),
            "path_globs": list(self.path_globs),
            "allowed_extensions": list(self.allowed_extensions),
            "max_files": self.max_files,
            "max_chars": self.max_chars,
        }


@dataclass(frozen=True)
class ContextSource:
    source_type: str
    path: str
    reason: str
    content: str
    char_count: int
    truncated: bool = False

    def to_metadata(self) -> dict[str, Any]:
        return {
            "type": self.source_type,
            "path": self.path,
            "reason": self.reason,
            "content": self.content,
            "char_count": self.char_count,
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class ContextBundle:
    policy: ContextPolicy
    sources: tuple[ContextSource, ...] = ()
    char_count: int = 0
    truncated: bool = False

    def to_metadata(self) -> dict[str, Any]:
        return {
            "policy": self.policy.to_metadata(),
            "sources": [source.to_metadata() for source in self.sources],
            "stats": {
                "file_count": len(self.sources),
                "char_count": self.char_count,
                "truncated": self.truncated,
            },
        }

    def render_for_prompt(self) -> str:
        if not self.sources:
            return ""
        sections = []
        for source in self.sources:
            sections.append(
                f"[{source.source_type}] {source.path}\n"
                f"Reason: {source.reason}\n"
                f"{source.content}"
            )
        return "\n\n".join(sections)


class ContextResolver(Protocol):
    def resolve(
        self,
        policy: ContextPolicy,
        *,
        input_artifact: Artifact,
        prompt_refs: dict[str, str] | None = None,
        extra_paths: tuple[str, ...] = (),
    ) -> ContextBundle:
        ...


@dataclass
class DeterministicContextResolver:
    repo_root: Path | None = None
    _resolved_repo_root: Path = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._resolved_repo_root = (
            self.repo_root.resolve() if self.repo_root is not None else _resolve_repo_root()
        )

    def resolve(
        self,
        policy: ContextPolicy,
        *,
        input_artifact: Artifact,
        prompt_refs: dict[str, str] | None = None,
        extra_paths: tuple[str, ...] = (),
    ) -> ContextBundle:
        if not policy.enabled:
            return ContextBundle(policy=policy)

        sources: list[ContextSource] = []
        selected_paths: set[str] = set()
        total_chars = 0
        truncated = False

        if policy.include_artifact_content and input_artifact.content:
            artifact_text = json.dumps(input_artifact.content, indent=2, sort_keys=True)
            source, total_chars, was_truncated = self._make_source(
                source_type="artifact",
                path=f"artifact:{input_artifact.id}",
                reason="input_artifact",
                content=artifact_text,
                max_chars=policy.max_chars - total_chars,
            )
            if source:
                sources.append(source)
                truncated = truncated or was_truncated

        candidate_specs: list[tuple[str, str]] = []
        if policy.include_prompt_files:
            for ref_name, ref in (prompt_refs or {}).items():
                relative_path = self._prompt_ref_to_relative_path(ref)
                if relative_path is not None:
                    candidate_specs.append((relative_path, f"prompt_ref:{ref_name}"))

        for path in policy.always_include_paths:
            candidate_specs.append((path, "always_include"))
        for path in extra_paths:
            candidate_specs.append((path, "extra_path"))
        for pattern in policy.path_globs:
            for matched_path in self._glob_relative_paths(pattern, policy.allowed_extensions):
                candidate_specs.append((matched_path, f"path_glob:{pattern}"))

        for relative_path, reason in candidate_specs:
            normalized_path = relative_path.strip("/")
            if not normalized_path or normalized_path in selected_paths:
                continue
            if len(sources) >= policy.max_files or total_chars >= policy.max_chars:
                truncated = True
                break
            source, total_chars, was_truncated = self._load_file_source(
                normalized_path,
                reason,
                max_chars=policy.max_chars - total_chars,
                allowed_extensions=policy.allowed_extensions,
            )
            if source is None:
                continue
            sources.append(source)
            selected_paths.add(normalized_path)
            truncated = truncated or was_truncated

        return ContextBundle(
            policy=policy,
            sources=tuple(sources),
            char_count=total_chars,
            truncated=truncated,
        )

    def _glob_relative_paths(
        self,
        pattern: str,
        allowed_extensions: tuple[str, ...],
    ) -> list[str]:
        matches: list[str] = []
        for path in sorted(self._resolved_repo_root.glob(pattern)):
            if not path.is_file():
                continue
            if allowed_extensions and path.suffix not in allowed_extensions:
                continue
            matches.append(path.relative_to(self._resolved_repo_root).as_posix())
        return matches

    def _load_file_source(
        self,
        relative_path: str,
        reason: str,
        *,
        max_chars: int,
        allowed_extensions: tuple[str, ...],
    ) -> tuple[ContextSource | None, int, bool]:
        path = (self._resolved_repo_root / relative_path).resolve()
        try:
            path.relative_to(self._resolved_repo_root)
        except ValueError:
            return None, 0, False
        if not path.is_file():
            return None, 0, False
        if allowed_extensions and path.suffix not in allowed_extensions:
            return None, 0, False
        try:
            content = path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError:
            return None, 0, False
        source, used_chars, truncated = self._make_source(
            source_type="file",
            path=relative_path,
            reason=reason,
            content=content,
            max_chars=max_chars,
        )
        return source, used_chars, truncated

    def _make_source(
        self,
        *,
        source_type: str,
        path: str,
        reason: str,
        content: str,
        max_chars: int,
    ) -> tuple[ContextSource | None, int, bool]:
        if max_chars <= 0:
            return None, 0, True
        truncated = len(content) > max_chars
        bounded_content = content[:max_chars].rstrip()
        if not bounded_content:
            return None, 0, truncated
        source = ContextSource(
            source_type=source_type,
            path=path,
            reason=reason,
            content=bounded_content,
            char_count=len(bounded_content),
            truncated=truncated,
        )
        return source, len(bounded_content), truncated

    def _prompt_ref_to_relative_path(self, prompt_ref: str) -> str | None:
        if "-" not in prompt_ref:
            return None
        prompt_id, version = prompt_ref.rsplit("-", 1)
        return f"prompts/{prompt_id}-{version}.md"


def _resolve_repo_root() -> Path:
    for parent in [Path.cwd(), *Path.cwd().parents]:
        if (parent / "README.md").is_file() and (parent / "packages").is_dir():
            return parent.resolve()
    package_path = Path(__file__).resolve()
    for parent in package_path.parents:
        if (parent / "README.md").is_file() and (parent / "packages").is_dir():
            return parent.resolve()
    raise FileNotFoundError(
        "Repository root not found. Run from the repo or configure DeterministicContextResolver(repo_root=...)."
    )


def _service_env(service_env_prefix: str, key: str, default: str) -> str:
    return (
        os.getenv(f"{service_env_prefix}_{key}")
        or os.getenv(f"SERVICE_{key}")
        or os.getenv(key)
        or default
    )


def _csv_env_tuple(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _env_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(value: str, default: int) -> int:
    try:
        return int(value)
    except ValueError:
        return default
