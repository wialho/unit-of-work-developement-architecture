# AGENTS.md

## Codebase map
- `README.md`: primary architecture and operations doc. Start here for service roles, local dev, Docker, and Kubernetes.
- `pyproject.toml`: Python package root. Runtime code lives under `packages/workflow_contracts/src` and `packages/workflow_runtime/src`. `pytest` is configured to import from those paths.
- `docker-compose.yml`: local stack wiring for Postgres, RabbitMQ, MinIO, Ollama, and the Python services.
- `migrations/001_init_workflow_schema.sql`: canonical DB schema for the `workflow` schema.
- `prompts/`: versioned starting prompts shared across apps. Current pattern is `<prompt-id>-<version>.md`, for example `prompts/prompt-to-code/task-system-v1.md`.

### Python services
- `apps/orchestrator/src/main.py`: FastAPI control plane. `POST /workflow-runs` creates the run, stores the source artifact, creates the first step, and publishes the first queue message.
- `apps/ticket-to-prompt/src/main.py`: worker bootstrap for `ticket-to-prompt`.
- `apps/ticket-to-prompt/src/handler.py`: converts source ticket artifact JSON into a prompt artifact.
- `apps/prompt-to-code/src/main.py`: worker bootstrap for `prompt-to-code`, including LLM client lifecycle.
- `apps/prompt-to-code/src/handler.py`: self-improving LLM step. Loads versioned prompts from `prompts/` and emits code artifacts.
- `apps/code-review/src/main.py`: worker bootstrap for `code-review`.
- `apps/code-review/src/handler.py`: simple review stage. Fails generated output containing `TODO`.
- `apps/analysis/src/main.py`: FastAPI read-only analysis API. Currently a placeholder outside the execution path.

### Shared Python packages
- `packages/workflow_contracts/src/workflow_contracts/messages.py`: shared enums and message models. Step names, artifact names, and queue payload shape come from here.
- `packages/workflow_runtime/src/workflow_runtime/config.py`: environment loading. Service-specific env vars use the uppercased service name prefix, for example `PROMPT_TO_CODE_LLM_MODEL`.
- `packages/workflow_runtime/src/workflow_runtime/worker.py`: generic queue worker, queue-name mapping, step claiming, artifact creation, and next-step publishing.
- `packages/workflow_runtime/src/workflow_runtime/db.py`: async Postgres access.
- `packages/workflow_runtime/src/workflow_runtime/queue.py`: RabbitMQ client.
- `packages/workflow_runtime/src/workflow_runtime/llm.py`: LLM client abstractions and provider implementations.
- `packages/workflow_runtime/src/workflow_runtime/prompt_step.py`: simple one-call prompt handler.
- `packages/workflow_runtime/src/workflow_runtime/self_improving_prompt_step.py`: bounded prompt-refinement and output-repair loop for LLM-backed services.
- `packages/workflow_runtime/src/workflow_runtime/prompt_registry.py`: prompt loader for versioned files under `prompts/`.

### Frontends
- `apps/orchestrator-dashboard/`: Vite + React shell for starting workflow runs.
- `apps/analysis-frontend/`: Vite + React shell for analysis data.
- Each frontend uses `package.json` scripts `dev`, `build`, and `preview`.

### Deploy/config
- `apps/*/Dockerfile`: per-service images. Python service images copy `pyproject.toml`, `packages/`, `prompts/`, and the service app.
- `deploy/k8s/`: development Kubernetes manifests.
- `deploy/k8s/prod/`: production overlay, service manifests, HPA/PDB, and migration job.

### Tests
- `tests/test_self_improving_prompt_step.py`: covers the self-improving handler loop and metadata.
- `tests/test_prompt_registry.py`: covers prompt registry loading.

## Entry points and wiring
- Python workers start from each app’s `src/main.py`, build `Settings.from_env("<service-name>")`, then create a `StepWorker` or FastAPI app.
- Queue routing is centralized in `packages/workflow_runtime/src/workflow_runtime/worker.py` as `QUEUE_BY_STEP`.
- The workflow is linear today: `ticket_to_prompt -> prompt_to_code -> code_review`.
- Orchestrator publishes `WorkflowMessage` objects that reference artifact IDs, not full payloads.
- `prompt-to-code` is the only LLM stage today. It uses service-local prompt files and supports `PROMPT_TO_CODE_PROMPT_VERSION`.
- Prompt registry resolution can be overridden with `PROMPT_REGISTRY_ROOT`; otherwise it searches upward for a `prompts/` directory.

## Naming conventions
- Step enums use snake_case values like `ticket_to_prompt`.
- RabbitMQ queues mirror service names with `.in`, for example `prompt-to-code.in`.
- IDs are prefixed by type (`wr`, `ws`, `art`, `tr`) via `workflow_runtime.ids`.
- Python service directories use hyphenated app names under `apps/`; env prefixes convert hyphens to underscores and uppercase.
- Prompt file names use `<name>-<version>.md`.

## Local norms
- Prefer targeted reads over full-repo sweeps. Start with `README.md`, `pyproject.toml`, `docker-compose.yml`, service `main.py` files, and shared runtime/contracts.
- Use `rg` and `rg --files` for discovery.
- Keep new pipeline stages aligned with shared contracts:
  - Add enum values in `workflow_contracts/messages.py`.
  - Add queue mapping in `workflow_runtime/worker.py`.
  - Wire the previous stage’s `next_step_type`.
- Reuse shared runtime helpers before adding service-specific plumbing. The intended extension points are `PromptLLMStepHandler`, `SelfImprovingLLMStepHandler`, and `prompt_registry`.
- Preserve the artifact-driven design: queue messages should carry references, while durable payloads live in Postgres artifacts.
- When adding reusable prompts, place them under `prompts/` and prefer versioned files over hardcoded prompt strings.
- If you change Python service Dockerfiles, keep `prompts/` copied into the image or prompt loading will break in containers.
- Tests currently live in `tests/` and are run with `pytest`. Add focused unit tests for shared runtime behavior.

## Self-correction
- If the code map is discovered to be stale, update it.
- If the user gives a correction about how work should be done in this repo, add it to `Local norms` or another clearly labeled section so future sessions inherit it.
