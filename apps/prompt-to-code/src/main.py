from __future__ import annotations

import asyncio
from contextlib import suppress

from handler import PromptToCodeHandler
from workflow_runtime import Database, QueueClient, Settings, StepWorker, create_llm_client


async def main() -> None:
    settings = Settings.from_env("prompt-to-code")
    llm_client = create_llm_client(settings)
    worker = StepWorker(
        service_name=settings.service_name,
        db=Database(settings.database_url),
        queue=QueueClient(settings.queue_url),
        handler=PromptToCodeHandler(llm_client),
    )
    try:
        await worker.start()
    finally:
        with suppress(Exception):
            await llm_client.close()


if __name__ == "__main__":
    asyncio.run(main())
