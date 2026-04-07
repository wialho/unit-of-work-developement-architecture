from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from workflow_contracts import ArtifactType, StepType, WorkflowMessage
from workflow_runtime import Database, QueueClient, Settings
from workflow_runtime.ids import new_id
from workflow_runtime.worker import QUEUE_BY_STEP


settings = Settings.from_env("orchestrator")
db = Database(settings.database_url)
queue = QueueClient(settings.queue_url)


class CreateWorkflowRunRequest(BaseModel):
    source_type: str = Field(examples=["jira"])
    source_ref: str = Field(examples=["PROJ-123"])
    ticket: dict[str, Any]


class CreateWorkflowRunResponse(BaseModel):
    workflow_run_id: str
    first_step_id: str
    input_artifact_id: str
    trace_id: str


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.connect()
    await queue.connect()
    try:
        yield
    finally:
        await queue.close()
        await db.close()


app = FastAPI(title="workflow-orchestrator", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/workflow-runs", response_model=CreateWorkflowRunResponse, status_code=202)
async def create_workflow_run(request: CreateWorkflowRunRequest) -> CreateWorkflowRunResponse:
    workflow_run_id = new_id("wr")
    input_artifact_id = new_id("art")
    first_step_id = new_id("ws")
    trace_id = new_id("tr")

    await db.create_workflow_run(workflow_run_id, request.source_type, request.source_ref)
    await db.create_artifact(
        artifact_id=input_artifact_id,
        workflow_run_id=workflow_run_id,
        artifact_type=ArtifactType.SOURCE_TICKET,
        content=request.ticket,
        content_ref=None,
        metadata={"source_type": request.source_type, "source_ref": request.source_ref},
        created_by_service=settings.service_name,
    )
    first_step_id = await db.create_workflow_step(
        step_id=first_step_id,
        workflow_run_id=workflow_run_id,
        step_type=StepType.TICKET_TO_PROMPT,
        input_artifact_id=input_artifact_id,
    )
    await queue.publish(
        QUEUE_BY_STEP[StepType.TICKET_TO_PROMPT],
        WorkflowMessage(
            workflow_run_id=workflow_run_id,
            workflow_step_id=first_step_id,
            step_type=StepType.TICKET_TO_PROMPT,
            input_artifact_id=input_artifact_id,
            trace_id=trace_id,
        ),
    )
    await db.record_event(
        workflow_run_id,
        first_step_id,
        settings.service_name,
        "workflow_started",
        trace_id,
        {"first_queue": QUEUE_BY_STEP[StepType.TICKET_TO_PROMPT]},
    )

    return CreateWorkflowRunResponse(
        workflow_run_id=workflow_run_id,
        first_step_id=first_step_id,
        input_artifact_id=input_artifact_id,
        trace_id=trace_id,
    )
