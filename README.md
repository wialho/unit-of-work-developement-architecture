# Workflow Pipeline

Kubernetes-oriented workflow pipeline made of specialized microservices. The orchestrator is the control plane; pipeline services process one synchronous step each and hand off through durable queue messages.

## Services

- `orchestrator`: accepts new work, creates workflow state, and publishes the first stage message.
- `ticket-to-prompt`: consumes `ticket-to-prompt.in`, converts source ticket artifacts into prompt artifacts.
- `prompt-to-code`: consumes `prompt-to-code.in`, converts prompt artifacts into generated code artifacts through the shared LLM client.
- `code-review`: consumes `code-review.in`, converts generated code artifacts into review result artifacts and completes the workflow.
- `analysis`: reads durable workflow data outside the execution path.

## Shared Infrastructure

- `postgres`: durable workflow state. This can be the local Compose container, the dev Kubernetes manifest, or a managed Postgres instance exposed through `DATABASE_URL`.
- `rabbitmq`: queue-driven stage handoff.
- `minio`: local S3-compatible object storage for development.
- `ollama`: local LLM service for development and private deployments.

The runtime exposes provider-neutral shared code for prompt-based LLM steps, LLM access, and blob storage:

- `workflow_runtime.prompt_step.PromptLLMStepHandler`
- `workflow_runtime.llm.LLMClient`
- `workflow_runtime.object_storage.BlobStorage`
- `workflow_runtime.object_storage.create_blob_storage`
- `workflow_runtime.llm.create_llm_client`

The LLM provider and model are selected at deploy time. Global defaults:

```text
LLM_PROVIDER=ollama
LLM_BASE_URL=http://ollama:11434
LLM_MODEL=codellama
```

Each service can override those defaults with service-prefixed variables. For `prompt-to-code`, use:

```text
PROMPT_TO_CODE_LLM_PROVIDER=ollama
PROMPT_TO_CODE_LLM_BASE_URL=http://ollama:11434
PROMPT_TO_CODE_LLM_MODEL=codellama
```

For an OpenAI-compatible API, set:

```text
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.example.com/v1
LLM_MODEL=some-model
LLM_API_KEY=...
```

Blob storage is selected at deploy time. MinIO works locally because it is S3-compatible:

```text
OBJECT_STORAGE_PROVIDER=s3_compatible
OBJECT_STORAGE_ENDPOINT=minio:9000
OBJECT_STORAGE_BUCKET=workflow-artifacts
OBJECT_STORAGE_ACCESS_KEY=workflow
OBJECT_STORAGE_SECRET_KEY=workflow-secret
OBJECT_STORAGE_SECURE=false
```

For Amazon S3, configure the same shared code with an S3 endpoint and credentials supplied through secrets:

```text
OBJECT_STORAGE_PROVIDER=s3_compatible
OBJECT_STORAGE_ENDPOINT=s3.amazonaws.com
OBJECT_STORAGE_BUCKET=my-workflow-artifacts
OBJECT_STORAGE_REGION=us-east-1
OBJECT_STORAGE_SECURE=true
```

## Queue Contract

V1 uses one RabbitMQ queue per stage:

- `ticket-to-prompt.in`
- `prompt-to-code.in`
- `code-review.in`

Messages carry references, not payload blobs:

```json
{
  "workflow_run_id": "wr_123",
  "workflow_step_id": "ws_123",
  "step_type": "prompt_to_code",
  "input_artifact_id": "art_456",
  "trace_id": "tr_789",
  "attempt": 1
}
```

## Persistence

Postgres uses one database with a shared `workflow` schema:

- `workflow.workflow_runs`
- `workflow.workflow_steps`
- `workflow.artifacts`
- `workflow.service_events`

Artifacts support either inline JSON `content` for small data or `content_ref` for future object storage.

## Local Development

Start the local stack:

```bash
docker compose up --build
```

Submit a workflow:

```bash
curl -X POST http://localhost:8080/workflow-runs \
  -H 'content-type: application/json' \
  -d '{
    "source_type": "jira",
    "source_ref": "PROJ-123",
    "ticket": {
      "title": "Add greeting endpoint",
      "description": "Create a simple endpoint that returns a greeting.",
      "acceptance_criteria": ["Endpoint returns 200", "Response includes greeting text"]
    }
  }'
```

RabbitMQ management UI is available at `http://localhost:15672` with `guest` / `guest`.

MinIO console is available at `http://localhost:9001` with `workflow` / `workflow-secret`.

Ollama is available at `http://localhost:11434`. Pull the configured local model before submitting `prompt-to-code` work, for example:

```bash
docker compose exec ollama ollama pull codellama
```

## Kubernetes

The development manifests are in `deploy/k8s`. They include local Postgres, RabbitMQ, MinIO, and Ollama for local cluster testing.

Apply order for a development cluster:

```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/configmap.yaml
kubectl apply -f deploy/k8s/secrets.example.yaml
kubectl apply -f deploy/k8s/postgres.yaml
kubectl apply -f deploy/k8s/rabbitmq.yaml
kubectl apply -f deploy/k8s/minio.yaml
kubectl apply -f deploy/k8s/minio-bucket-job.yaml
kubectl apply -f deploy/k8s/ollama.yaml
kubectl apply -f deploy/k8s/orchestrator-deployment.yaml
kubectl apply -f deploy/k8s/ticket-to-prompt-deployment.yaml
kubectl apply -f deploy/k8s/prompt-to-code-deployment.yaml
kubectl apply -f deploy/k8s/code-review-deployment.yaml
kubectl apply -f deploy/k8s/analysis-deployment.yaml
```

## Production Kubernetes

The production overlay is in `deploy/k8s/prod`. It deploys only the pipeline services and a migration job. It does not deploy local Postgres, RabbitMQ, MinIO, or Ollama.

Build and push service images:

```bash
docker build -t registry.example.com/workflow-pipeline/orchestrator:0.1.0 -f apps/orchestrator/Dockerfile .
docker build -t registry.example.com/workflow-pipeline/ticket-to-prompt:0.1.0 -f apps/ticket-to-prompt/Dockerfile .
docker build -t registry.example.com/workflow-pipeline/prompt-to-code:0.1.0 -f apps/prompt-to-code/Dockerfile .
docker build -t registry.example.com/workflow-pipeline/code-review:0.1.0 -f apps/code-review/Dockerfile .
docker build -t registry.example.com/workflow-pipeline/analysis:0.1.0 -f apps/analysis/Dockerfile .
docker build -t registry.example.com/workflow-pipeline/migrations:0.1.0 -f apps/migrations/Dockerfile .
```

Update `deploy/k8s/prod/kustomization.yaml` with your image registry and tag.

Create a real secret from the example:

```bash
cp deploy/k8s/prod/secret.example.yaml /tmp/workflow-secrets.yaml
```

Edit `/tmp/workflow-secrets.yaml` with production values:

```text
DATABASE_URL=postgresql://...
QUEUE_URL=amqps://...
LLM_API_KEY=...
OBJECT_STORAGE_ACCESS_KEY=...
OBJECT_STORAGE_SECRET_KEY=...
```

Apply production config:

```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f /tmp/workflow-secrets.yaml
kubectl apply -k deploy/k8s/prod
```

Run and verify the migration job:

```bash
kubectl -n workflow-pipeline wait --for=condition=complete job/workflow-db-migrations --timeout=180s
kubectl -n workflow-pipeline logs job/workflow-db-migrations
```

Verify rollouts:

```bash
kubectl -n workflow-pipeline rollout status deployment/orchestrator
kubectl -n workflow-pipeline rollout status deployment/ticket-to-prompt
kubectl -n workflow-pipeline rollout status deployment/prompt-to-code
kubectl -n workflow-pipeline rollout status deployment/code-review
kubectl -n workflow-pipeline rollout status deployment/analysis
```

The production overlay includes CPU/memory requests and limits, HTTP probes for API services, HPAs, PDBs, a migration Job, and managed-service configuration placeholders.

## Provisioning A New Service

Use this checklist when adding another specialized pipeline service, for example `security-scan`.

Add shared contract types in `packages/workflow_contracts/src/workflow_contracts/messages.py`:

```python
class StepType(StrEnum):
    TICKET_TO_PROMPT = "ticket_to_prompt"
    PROMPT_TO_CODE = "prompt_to_code"
    SECURITY_SCAN = "security_scan"
    CODE_REVIEW = "code_review"


class ArtifactType(StrEnum):
    SOURCE_TICKET = "source_ticket"
    PROMPT = "prompt"
    CODE_ARTIFACT = "code_artifact"
    SECURITY_SCAN_RESULT = "security_scan_result"
    REVIEW_RESULT = "review_result"
```

Add the queue mapping in `packages/workflow_runtime/src/workflow_runtime/worker.py`:

```python
QUEUE_BY_STEP: dict[StepType, str] = {
    StepType.TICKET_TO_PROMPT: "ticket-to-prompt.in",
    StepType.PROMPT_TO_CODE: "prompt-to-code.in",
    StepType.SECURITY_SCAN: "security-scan.in",
    StepType.CODE_REVIEW: "code-review.in",
}
```

Create the service app:

```text
apps/security-scan/
  src/
    main.py
    handler.py
  Dockerfile
```

If the service is prompt-based, reuse the shared prompt-step handler:

```python
from workflow_contracts import ArtifactType, StepType
from workflow_runtime import LLMClient, PromptLLMStepHandler, PromptStepConfig


class SecurityScanHandler(PromptLLMStepHandler):
    def __init__(self, llm_client: LLMClient) -> None:
        super().__init__(
            PromptStepConfig(
                step_type=StepType.SECURITY_SCAN,
                output_artifact_type=ArtifactType.SECURITY_SCAN_RESULT,
                next_step_type=StepType.CODE_REVIEW,
                system_prompt="Review the code artifact for security issues.",
                prompt_content_key="prompt",
                output_language="json",
                output_path="security-scan.json",
            ),
            llm_client,
        )
```

If it is not prompt-based, implement the normal `StepHandler` pattern and return a `StepResult`.

Wire the new service into the pipeline by changing the previous service's `next_step_type`. For example:

```text
prompt-to-code -> security-scan -> code-review
```

In that flow, `prompt-to-code` should return `next_step_type=StepType.SECURITY_SCAN`, and `security-scan` should return `next_step_type=StepType.CODE_REVIEW`.

Add deployment configuration:

1. Add a service entry to `docker-compose.yml`.
2. Add `deploy/k8s/security-scan-deployment.yaml` for local Kubernetes testing.
3. Add the production Deployment to `deploy/k8s/prod/services.yaml`.
4. Add an image mapping in `deploy/k8s/prod/kustomization.yaml`.
5. Add HPA/PDB entries in `deploy/k8s/prod/hpa.yaml` and `deploy/k8s/prod/pdb.yaml` if it needs independent production scaling.

Use service-specific LLM settings when the new service needs its own model:

```text
SECURITY_SCAN_LLM_PROVIDER=openai_compatible
SECURITY_SCAN_LLM_BASE_URL=https://api.example.com/v1
SECURITY_SCAN_LLM_MODEL=security-focused-model
SECURITY_SCAN_LLM_API_KEY=...
```

If those are omitted, the service falls back to global `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY`.

The architectural rule is: each new role gets its own Deployment and queue; services never target individual pods directly.

## Adding a Stage

1. Add a new `StepType` and `ArtifactType` in `packages/workflow_contracts`.
2. Add the queue name to `QUEUE_BY_STEP` in `packages/workflow_runtime`.
3. Create a new service app with a `StepHandler`, or use `PromptLLMStepHandler` if the service is prompt-based.
4. Set the previous stage handler's `next_step_type` to the new step.
5. Add Docker and Kubernetes deployment files for the new role.
