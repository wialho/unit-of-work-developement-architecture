from __future__ import annotations

import asyncio

from handler import PolicyReviewHandler
from workflow_runtime import Database, QueueClient, Settings, StepWorker


async def main() -> None:
    settings = Settings.from_env("policy-review")
    worker = StepWorker(
        service_name=settings.service_name,
        db=Database(settings.database_url),
        queue=QueueClient(settings.queue_url),
        handler=PolicyReviewHandler(),
    )
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
