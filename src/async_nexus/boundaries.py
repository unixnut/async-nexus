"""
Classes for managing the interaction between event domains, each of which
contains an :class:`async_nexus.AsyncEventNexus` and its associated
:class:`async_nexus.Event` sources and handlers.
"""

import asyncio

import async_nexus


class AsyncEventBoundary(async_nexus.EventProducer, async_nexus.EventConsumer):
    """
    Forwards events between event domains.  This is done by hooking into two
    different nexuses.

    Acts as both a handler registered with :class:`async_nexus.AsyncEventNexus`
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
        """
        Start :meth:`transfer_events` in the background.

        :return asyncio.Task: the task to be optionally awaited (in case it returns due to error or cancellation)
        """

        await super().start()
        self.task = asyncio.create_task(self.transfer_events())

        return self.task


    async def transfer_events(self):
        """Continuously feed events from the queue to registered nexuses."""

        while True:
            event = await self.queue.get()
            await self.distribute_event(event)


    async def handle(self, event: async_nexus.Event, queue: asyncio.Queue) -> None:
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
