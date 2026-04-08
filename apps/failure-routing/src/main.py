from __future__ import annotations

import asyncio

from handler import FailureRoutingHandler
from workflow_runtime import Database, QueueClient, Settings, StepWorker


async def main() -> None:
    settings = Settings.from_env("failure-routing")
    worker = StepWorker(
        service_name=settings.service_name,
        db=Database(settings.database_url),
        queue=QueueClient(settings.queue_url),
        handler=FailureRoutingHandler(),
    )
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
