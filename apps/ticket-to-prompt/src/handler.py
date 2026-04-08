from __future__ import annotations

from workflow_contracts import Artifact, ArtifactType, StepResult, StepType, WorkflowMessage


class TicketToPromptHandler:
    step_type = StepType.TICKET_TO_PROMPT

    async def process(self, message: WorkflowMessage, input_artifact: Artifact) -> StepResult:
        ticket = input_artifact.content or {}
        title = ticket.get("title") or ticket.get("summary") or "Untitled ticket"
        description = ticket.get("description") or ""
        acceptance_criteria = ticket.get("acceptance_criteria") or []

        prompt = (
            "Implement the following work ticket.\n\n"
            f"Title: {title}\n\n"
            f"Description:\n{description}\n\n"
            f"Acceptance criteria:\n{acceptance_criteria}\n"
        )
        return StepResult(
            output_artifact_type=ArtifactType.PROMPT,
            output_content={"prompt": prompt, "ticket": ticket},
            output_metadata={"source_artifact_id": message.input_artifact_id},
            next_step_type=StepType.PROMPT_TO_CODE,
        )
