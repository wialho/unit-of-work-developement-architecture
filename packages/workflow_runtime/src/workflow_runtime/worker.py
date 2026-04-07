from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from workflow_contracts import Artifact, StepResult, StepType, WorkflowMessage
from workflow_runtime.db import Database
from workflow_runtime.ids import new_id
from workflow_runtime.queue import QueueClient


QUEUE_BY_STEP: dict[StepType, str] = {
    StepType.TICKET_TO_PROMPT: "ticket-to-prompt.in",
    StepType.PROMPT_TO_CODE: "prompt-to-code.in",
    StepType.CODE_REVIEW: "code-review.in",
}


class StepHandler(Protocol):
    step_type: StepType

    async def process(self, message: WorkflowMessage, input_artifact: Artifact) -> StepResult:
        ...


@dataclass
class StepWorker:
    service_name: str
    db: Database
    queue: QueueClient
    handler: StepHandler

    async def start(self) -> None:
        await self.db.connect()
        await self.queue.connect()
        await self.queue.consume(QUEUE_BY_STEP[self.handler.step_type], self._handle)
        await asyncio.Future()

    async def _handle(self, message: WorkflowMessage) -> None:
        if message.step_type != self.handler.step_type:
            raise ValueError(f"{self.service_name} received unexpected step {message.step_type}")
        if message.workflow_step_id is None:
            raise ValueError("workflow_step_id is required for idempotent processing")

        claimed = await self.db.claim_step_for_processing(message.workflow_step_id)
        if not claimed:
            await self.db.record_event(
                message.workflow_run_id,
                message.workflow_step_id,
                self.service_name,
                "step_skipped_not_claimed",
                message.trace_id,
            )
            return

        await self.db.record_event(
            message.workflow_run_id,
            message.workflow_step_id,
            self.service_name,
            "step_started",
            message.trace_id,
        )

        try:
            input_artifact = await self.db.get_artifact(message.input_artifact_id)
            result = await self.handler.process(message, input_artifact)
            output_artifact_id = new_id("art")
            await self.db.create_artifact(
                artifact_id=output_artifact_id,
                workflow_run_id=message.workflow_run_id,
                artifact_type=result.output_artifact_type,
                content=result.output_content,
                content_ref=result.output_content_ref,
                metadata=result.output_metadata,
                created_by_service=self.service_name,
            )
            await self.db.mark_step_completed(message.workflow_step_id, output_artifact_id)

            if result.next_step_type is None:
                await self.db.mark_workflow_completed(message.workflow_run_id)
                await self.db.record_event(
                    message.workflow_run_id,
                    message.workflow_step_id,
                    self.service_name,
                    "workflow_completed",
                    message.trace_id,
                    {"output_artifact_id": output_artifact_id},
                )
                return

            next_step_id = new_id("ws")
            next_step_id = await self.db.create_workflow_step(
                step_id=next_step_id,
                workflow_run_id=message.workflow_run_id,
                step_type=result.next_step_type,
                input_artifact_id=output_artifact_id,
            )
            await self.queue.publish(
                QUEUE_BY_STEP[result.next_step_type],
                WorkflowMessage(
                    workflow_run_id=message.workflow_run_id,
                    workflow_step_id=next_step_id,
                    step_type=result.next_step_type,
                    input_artifact_id=output_artifact_id,
                    trace_id=message.trace_id,
                ),
            )
            await self.db.record_event(
                message.workflow_run_id,
                message.workflow_step_id,
                self.service_name,
                "next_step_published",
                message.trace_id,
                {"next_step_id": next_step_id, "output_artifact_id": output_artifact_id},
            )
        except Exception as exc:
            await self.db.mark_step_failed(message.workflow_step_id, {"message": str(exc)})
            await self.db.record_event(
                message.workflow_run_id,
                message.workflow_step_id,
                self.service_name,
                "step_failed",
                message.trace_id,
                {"message": str(exc)},
            )
            raise
