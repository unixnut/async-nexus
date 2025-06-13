"""Top-level package for Async Nexus."""

__author__ = """Alastair Irvine"""
__email__ = 'alastair@plug.org.au'
__version__ = '0.1.0'


from typing import Set, Dict, Sequence, Tuple, List, Union, AnyStr, Iterable, Callable, Generator, Type, Optional, TextIO, IO

import time
import asyncio
import abc
from dataclasses import dataclass
import random
from enum import IntEnum

from . import errors


# *** SPECIAL ***
# anext() compatibility function for Python 3.9 and prior
if not hasattr(__builtins__, 'anext'):
    async def anext(g):
        return await g.__anext__()



# *** CLASSES ***
@dataclass
class Event:
    id:       int
    type:     int
    # Lower integers represent higher priorities
    priority: int
    payload:  str


class Handler:
    @abc.abstractmethod
    async def handle(self, event: Event) -> None:
        pass


class AsyncEventPriorityQueue(metaclass=abc.ABCMeta):
    pass



class AbstractNexus:
    @abc.abstractmethod
    async def ingest(self, event: Event) -> None:
        pass



class EventFactory:
    """
    Creates event IDs and/or whole Event objects, using convenience method(s).

    :ivar current_event_id: The ID to be returned by the next call to next_id()
    """

    AUTO = -1
    RANDOM = -2


    def __init__(self):
        self.current_event_id = 1

    
    def next_id(self) -> int:
        id = self.current_event_id
        self.current_event_id += 1
        return id

    
    def random_id(self) -> int:
        return random.randint(1, 1000)


    def create_event(self, payload, *, type: int, id: int = AUTO, priority: int = 0) -> Event:
        """
        Convenient wrapper around :class:`Event` constructor.

        Hint: for event types, use non-overlapping enum.IntEnum subclasses.
        Then when creating log messages etc., you can cast the event type back
        to the relevant subclass and use the ``.name`` attribute of the
        resulting object.  To determine the type category (group of types
        represented by a given subclass), attempt to cast the type to the first
        subclass and if you catch :class:`ValueError` try the next subclass,
        and so on.

        :param payload:  A generic payload to include in the event
        :param type:     Numeric event type; keyword only parameter
        :param id:       Numeric event ID, or a sequential event ID if ``AUTO``, or a random one if ``RANDOM`` 
        :param priority: Optional priority, with lower integers representing higher priorities
        """

        if id == self.AUTO:
            return Event(self.next_id(), type, priority, payload)
        elif id == self.RANDOM:
            return Event(self.random_id(), type, priority, payload)
        else:
            return Event(id, type, priority, payload)



class SimpleEventConverter(metaclass=abc.ABCMeta):
    """Event source used in pull mode.  Blocks until an event is ready."""

    @abc.abstractmethod
    async def obtain_event(self) -> Event:
        pass



class EventConverter(SimpleEventConverter):
    """Event source used in pull mode that uses a generator internally."""

    def __init__(self):
        self.gen: AsyncGenerator = self.event_generator()


    @abc.abstractmethod
    async def event_generator(self):
        yield None


    async def obtain_event(self) -> Event:
        """
        Gets one event.

        :raises errors.NoMoreEvents: If it is not possible to get an event
        """

        try:
            return await anext(self.gen)
        except StopAsyncIteration:
            raise errors.NoMoreEvents



class EventProducer(metaclass=abc.ABCMeta):
    """
    Event source used in push mode.  Can send each event to one or more nexus
    objects.  Unlike :class:`SimpleEventConverter`, :class:`EventProducer`
    emits events whenever they are ready, without being asked.

    It's up to an object of each subclass to manage its own flow of control.

    :ivar nexus_list: Maintains the list of AsyncEventNexus objects to send to
        :type nexus_list: List[AsyncEventNexus]
    :ivar event_factory:   Optional object that subclasses may use to create :class:`Event` objects
        :type event_factory: Optional[EventFactory]
    """

    def __init__(self, event_factory: Optional[EventFactory] = None):
        """
        :param event_factory:   Optional object that subclasses may use to create :class:`Event` objects
        """

        self.nexus_list = []
        self.event_factory = event_factory


    def register_nexus(self, nexus: AbstractNexus) -> None:
        """
        Mandatory method that must be called for each nexus that this producer
        is to be associated with.
        """

        self.nexus_list.append(nexus)


    async def start(self) -> None:
        """
        Optionally, kicks off any actions the producer needs to do in order to
        start producing events.  Subclasses must call ``await super().start()``.
        """

        if not self.nexus_list:
            raise errors.MisconfiguredEventProducer("No nexus objects registered")


    async def distribute_event(self, event: Event) -> None:
        for nexus in self.nexus_list:
            await nexus.ingest(event)



class AsyncEventNexus(Handler, AbstractNexus, EventFactory):
    """
    An event handler must accept as an argument, being the queue into which any
    secondary events are added.

    :ivar converters: Objects with async obtain_event() methods
        :type converters: List[SimpleEventConverter]
    :ivar producers: Objects with register_nexus() methods
        :type producers: List[EventProducer]
    """

    # The Callable should actually be a coroutine function
    HandlerType = Callable[[Event, asyncio.Queue], None]
    QUEUE_MAXLEN = 50


    def __init__(self, multiple: bool = False, bitmode: bool = False):
        """
        :param multiple: Allow multiple handlers per event type
        :param bitmode:  if True, means that event categories can only be powers of 2 and handlers can be associated with a bitmask
        """

        super().__init__()
        if bitmode:
            raise NotImplementedError
        self.handlers: Union[Dict[int, HandlerType], Dict[int, List[HandlerType]]] = {}
        self.queue = asyncio.Queue(maxsize=self.QUEUE_MAXLEN)
        self.multiple = multiple
        self.converters = []
        self.producers = []


    def add_handler(self, type: int, handler: HandlerType):
        """
        :param type: The type of event to handle, or -1 for events with no dedicated handler
        :param handler: If it's a Callable, it will be called or if it's a Coroutine it will be awaited
        """

        if self.multiple:
            if type in self.handlers:
                self.handlers[type].append(handler)
            else:
                self.handlers[type] = [handler]
        else:
            if type not in self.handlers:
                self.handlers[type] = handler
            else:
                raise LookupError("Handler for type %d already present" % type)


    def add_converter(self, converter: SimpleEventConverter) -> None:
        self.converters.append(converter)


    def add_producer(self, producer: EventProducer) -> None:
        self.producers.append(producer)
        producer.register_nexus(self)


    async def ingest(self, event: Event) -> None:
        """
        Handle an event, with queueing.

        All events (including secondary) are strictly handled, i.e. not as
        tasks.  Any background tasks should be created as such by handlers.
        """

        await self.queue.put(event)

        # Process all events, including those generated by handlers
        while True:
            # Deal with race condition where another coroutine removed the last
            # item after the loop condition check by ignoring the exception
            try:
                event = self.queue.get_nowait()
                await self.handle(event)
            except asyncio.QueueEmpty:
                break


    # This has to be async so handler coroutines can add secondary events to the queue
    async def handle(self, event: Event) -> None:
        try:
            if self.multiple:
                ## for handler in self.handlers[event.type]:
                ##     handled = await handler(event, self.queue)
                ##     if handled:
                ##         break
                ## else:
                ##     # It might not be a good idea to fall through to the generic handler list
                ##     for handler in self.handlers[-1]:
                ##         handled = await handler(event, self.queue)
                ##         if handled:
                ##             break
                ##     else:
                ##         raise errors.UnhandledEvent("Generic handlers all refused event")
                raise NotImplementedError
            else:
                try:
                    handler = self.handlers[event.type]
                except KeyError:
                    handler = self.handlers[-1]
                await handler(event, self.queue)
        except KeyError:
            raise errors.UnhandledEvent("No available event handler for event with ID=%d and type=%d" % (event.id, event.type), event)


    async def loop_forever(self) -> None:
        """
        The main Async Nexus loop.  Starts producers, then loops forever
        consuming and distributing events from converters.  In parallel to
        this, any registered producers will feed events into the queue
        unprompted.
        """

        for producer in self.producers:
            await producer.start()

        # TO-DO: task cancellation with event arising

        async def replace_future(task_to_converter_mapping: Dict[asyncio.Task, SimpleEventConverter],
                                 done_future: asyncio.Task) -> None:
            """Replace a task/future that's ready and reuse the rest."""
            converter = task_to_converter_mapping[done_future]
            del task_to_converter_mapping[done_future]
            new_future = asyncio.create_task(converter.obtain_event())
            task_to_converter_mapping[new_future] = converter

        task_to_converter_mapping: Dict[asyncio.Task, SimpleEventConverter] = {asyncio.create_task(converter.obtain_event()): converter for converter in self.converters}
        try:
            while True:
                converter_futures: List[asyncio.Task] = task_to_converter_mapping.keys()
                d, p = await asyncio.wait(converter_futures, return_when=asyncio.FIRST_COMPLETED)
                for done_future in d:
                    try:
                        # Task::result() might raise
                        await self.ingest(done_future.result())
                    except errors.NoMoreEvents:
                        # Remove references to the converter from the dict and the list
                        removed_converter_index = self.converters.index(task_to_converter_mapping[done_future])
                        del self.converters[removed_converter_index]
                        del task_to_converter_mapping[done_future]
                    else:
                        await replace_future(task_to_converter_mapping, done_future)

        except KeyboardInterrupt:
            pass



class EventConsumer(metaclass=abc.ABCMeta):
    """
    Optional parent class for classes whose ``ingest`` method is registered as
    a handler with :class:`AsyncEventNexus`.
    """

    @abc.abstractmethod
    async def ingest(self, event: Event, queue: asyncio.Queue) -> None:
        """
        Handle an event.

        :param queue: The caller's queue to which any secondary events should be sent.
        """
        pass



class EventFanout(Handler):
    pass
