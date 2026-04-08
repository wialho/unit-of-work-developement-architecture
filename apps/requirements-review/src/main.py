from __future__ import annotations

import asyncio
from contextlib import suppress

from handler import RequirementsReviewHandler
from workflow_runtime import Database, QueueClient, Settings, StepWorker, create_llm_client


async def main() -> None:
    settings = Settings.from_env("requirements-review")
    llm_client = create_llm_client(settings)
    worker = StepWorker(
        service_name=settings.service_name,
        db=Database(settings.database_url),
        queue=QueueClient(settings.queue_url),
        handler=RequirementsReviewHandler(llm_client),
    )
    try:
        await worker.start()
    finally:
        with suppress(Exception):
            await llm_client.close()


if __name__ == "__main__":
    asyncio.run(main())
