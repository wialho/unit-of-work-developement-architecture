from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from workflow_contracts import WorkflowMessage


MessageHandler = Callable[[WorkflowMessage], Awaitable[None]]


class QueueClient:
    def __init__(self, queue_url: str) -> None:
        self._queue_url = queue_url
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.RobustChannel | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._queue_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()

    async def publish(self, queue_name: str, message: WorkflowMessage) -> None:
        if self._channel is None:
            raise RuntimeError("QueueClient.connect() must be called before publish().")
        await self._channel.declare_queue(queue_name, durable=True)
        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=message.model_dump_json().encode("utf-8"),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                correlation_id=message.trace_id,
            ),
            routing_key=queue_name,
        )

    async def consume(self, queue_name: str, handler: MessageHandler) -> None:
        if self._channel is None:
            raise RuntimeError("QueueClient.connect() must be called before consume().")
        queue = await self._channel.declare_queue(queue_name, durable=True)

        async def on_message(raw: AbstractIncomingMessage) -> None:
            async with raw.process(requeue=True):
                payload = json.loads(raw.body.decode("utf-8"))
                await handler(WorkflowMessage.model_validate(payload))

        await queue.consume(on_message)
