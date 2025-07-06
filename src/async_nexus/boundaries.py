import asyncio

import async_nexus


class AsyncEventBoundary(async_nexus.EventProducer, async_nexus.EventConsumer):
    """
    Forwards events between event domains.  This is done by hooking into two
    different nexuses.

    Acts as both a handler registered with :class:`AsyncEventNexus`
    (``nexus1.add_handler(b)``) in one event domain and a producer
    (``nexus2.add_producer(b)``) in another.

    TODO: Send reply events back to the queue of the sending nexus, so it can dispatch them.
    """

    QUEUE_MAXLEN = 50


    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue(maxsize=self.QUEUE_MAXLEN)
        self.ready: bool = True


    async def start(self):
        await super().start()
        self.task = asyncio.create_task(self.transfer_events())


    async def transfer_events(self):
        while True:
            event = await self.queue.get()
            await self.distribute_event(event)


    async def handle(self, event: Event, queue: asyncio.Queue) -> None:
        """
        Handle an event.

        :param queue: The caller's queue to which any secondary events should be sent.
        """
        if not self.ready:
            raise asyncio.errors.BadCall("AsyncEventBoundary closed")

        await self.queue.put(event)

        # TODO: associate ``queue`` with event somehow, and use the latter to direct replies


    def close(self):
        self.ready = False
        asyncio.run(self.queue.join())
