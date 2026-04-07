CREATE SCHEMA IF NOT EXISTS workflow;

CREATE TABLE IF NOT EXISTS workflow.workflow_runs (
  id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS workflow.artifacts (
  id TEXT PRIMARY KEY,
  workflow_run_id TEXT NOT NULL REFERENCES workflow.workflow_runs(id),
  artifact_type TEXT NOT NULL,
  content JSONB,
  content_ref TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by_service TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (content IS NOT NULL OR content_ref IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS workflow.workflow_steps (
  id TEXT PRIMARY KEY,
  workflow_run_id TEXT NOT NULL REFERENCES workflow.workflow_runs(id),
  step_type TEXT NOT NULL,
  status TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 1,
  input_artifact_id TEXT REFERENCES workflow.artifacts(id),
  output_artifact_id TEXT REFERENCES workflow.artifacts(id),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  error JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workflow.service_events (
  id BIGSERIAL PRIMARY KEY,
  workflow_run_id TEXT NOT NULL REFERENCES workflow.workflow_runs(id),
  workflow_step_id TEXT REFERENCES workflow.workflow_steps(id),
  service_name TEXT NOT NULL,
  event_type TEXT NOT NULL,
  trace_id TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS workflow_steps_idempotency_idx
  ON workflow.workflow_steps (workflow_run_id, step_type, attempt);

CREATE INDEX IF NOT EXISTS workflow_steps_run_idx
  ON workflow.workflow_steps (workflow_run_id);

CREATE INDEX IF NOT EXISTS artifacts_run_idx
  ON workflow.artifacts (workflow_run_id);

CREATE INDEX IF NOT EXISTS service_events_run_idx
  ON workflow.service_events (workflow_run_id, created_at);
