from __future__ import annotations

import json
from typing import Any

import asyncpg

from workflow_contracts import Artifact, ArtifactType, StepType, WorkflowStatus
from workflow_contracts.messages import StepStatus


class Database:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._database_url, init=self._init_connection)

    async def _init_connection(self, connection: asyncpg.Connection) -> None:
        await connection.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )
        await connection.set_type_codec(
            "json",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def create_workflow_run(self, run_id: str, source_type: str, source_ref: str) -> None:
        await self._execute(
            """
            INSERT INTO workflow.workflow_runs (id, source_type, source_ref, status)
            VALUES ($1, $2, $3, $4)
            """,
            run_id,
            source_type,
            source_ref,
            WorkflowStatus.RUNNING.value,
        )

    async def create_artifact(
        self,
        artifact_id: str,
        workflow_run_id: str,
        artifact_type: ArtifactType,
        content: dict[str, Any] | None,
        content_ref: str | None,
        metadata: dict[str, Any],
        created_by_service: str,
    ) -> None:
        await self._execute(
            """
            INSERT INTO workflow.artifacts (
              id, workflow_run_id, artifact_type, content, content_ref, metadata, created_by_service
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            artifact_id,
            workflow_run_id,
            artifact_type.value,
            content,
            content_ref,
            metadata,
            created_by_service,
        )

    async def get_artifact(self, artifact_id: str) -> Artifact:
        row = await self._fetchrow(
            """
            SELECT id, workflow_run_id, artifact_type, content, content_ref, metadata, created_by_service
            FROM workflow.artifacts
            WHERE id = $1
            """,
            artifact_id,
        )
        if row is None:
            raise LookupError(f"Artifact not found: {artifact_id}")
        return Artifact(
            id=row["id"],
            workflow_run_id=row["workflow_run_id"],
            artifact_type=ArtifactType(row["artifact_type"]),
            content=row["content"],
            content_ref=row["content_ref"],
            metadata=row["metadata"],
            created_by_service=row["created_by_service"],
        )

    async def create_workflow_step(
        self,
        step_id: str,
        workflow_run_id: str,
        step_type: StepType,
        input_artifact_id: str,
        attempt: int = 1,
    ) -> str:
        existing_or_inserted_id = await self._fetchval(
            """
            WITH inserted AS (
              INSERT INTO workflow.workflow_steps (
                id, workflow_run_id, step_type, status, attempt, input_artifact_id
              )
              VALUES ($1, $2, $3, $4, $5, $6)
              ON CONFLICT (workflow_run_id, step_type, attempt) DO NOTHING
              RETURNING id
            )
            SELECT id FROM inserted
            UNION ALL
            SELECT id
            FROM workflow.workflow_steps
            WHERE workflow_run_id = $2 AND step_type = $3 AND attempt = $5
            LIMIT 1
            """,
            step_id,
            workflow_run_id,
            step_type.value,
            StepStatus.PENDING.value,
            attempt,
            input_artifact_id,
        )
        if existing_or_inserted_id is None:
            raise RuntimeError("Failed to create or load workflow step.")
        return existing_or_inserted_id

    async def claim_step_for_processing(self, step_id: str) -> bool:
        claimed_step_id = await self._fetchval(
            """
            UPDATE workflow.workflow_steps
            SET status = $2, started_at = COALESCE(started_at, now())
            WHERE id = $1 AND status IN ('pending', 'failed')
            RETURNING id
            """,
            step_id,
            StepStatus.RUNNING.value,
        )
        return claimed_step_id is not None

    async def mark_step_completed(self, step_id: str, output_artifact_id: str) -> None:
        await self._execute(
            """
            UPDATE workflow.workflow_steps
            SET status = $2, output_artifact_id = $3, finished_at = now(), error = NULL
            WHERE id = $1
            """,
            step_id,
            StepStatus.COMPLETED.value,
            output_artifact_id,
        )

    async def mark_step_failed(self, step_id: str, error: dict[str, Any]) -> None:
        await self._execute(
            """
            UPDATE workflow.workflow_steps
            SET status = $2, finished_at = now(), error = $3
            WHERE id = $1
            """,
            step_id,
            StepStatus.FAILED.value,
            error,
        )

    async def mark_workflow_completed(self, workflow_run_id: str) -> None:
        await self._execute(
            """
            UPDATE workflow.workflow_runs
            SET status = $2, completed_at = now()
            WHERE id = $1
            """,
            workflow_run_id,
            WorkflowStatus.COMPLETED.value,
        )

    async def mark_workflow_failed(self, workflow_run_id: str) -> None:
        await self._execute(
            """
            UPDATE workflow.workflow_runs
            SET status = $2, completed_at = now()
            WHERE id = $1
            """,
            workflow_run_id,
            WorkflowStatus.FAILED.value,
        )

    async def mark_workflow_running(self, workflow_run_id: str) -> None:
        await self._execute(
            """
            UPDATE workflow.workflow_runs
            SET status = $2, completed_at = NULL
            WHERE id = $1
            """,
            workflow_run_id,
            WorkflowStatus.RUNNING.value,
        )

    async def record_event(
        self,
        workflow_run_id: str,
        workflow_step_id: str | None,
        service_name: str,
        event_type: str,
        trace_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        await self._execute(
            """
            INSERT INTO workflow.service_events (
              workflow_run_id, workflow_step_id, service_name, event_type, trace_id, payload
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            workflow_run_id,
            workflow_step_id,
            service_name,
            event_type,
            trace_id,
            payload or {},
        )

    async def _execute(self, query: str, *args: object) -> str:
        if self._pool is None:
            raise RuntimeError("Database.connect() must be called before queries.")
        return await self._pool.execute(query, *args)

    async def _fetchrow(self, query: str, *args: object) -> asyncpg.Record | None:
        if self._pool is None:
            raise RuntimeError("Database.connect() must be called before queries.")
        return await self._pool.fetchrow(query, *args)

    async def _fetchval(self, query: str, *args: object) -> object | None:
        if self._pool is None:
            raise RuntimeError("Database.connect() must be called before queries.")
        return await self._pool.fetchval(query, *args)
