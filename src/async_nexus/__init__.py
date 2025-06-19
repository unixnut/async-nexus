"""Top-level package for Async Nexus."""

__author__ = """Alastair Irvine"""
__email__ = 'alastair@plug.org.au'
__version__ = '0.1.0'


from typing import Set, Dict, Sequence, Tuple, List, Union, AnyStr, Iterable, Callable, Generator, Type, Optional, TextIO, IO, Coroutine

import time
import asyncio
import abc
import itertools
from dataclasses import dataclass
import random
from enum import Enum
import weakref

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
    type:     Union[int, str]
    # Lower integers represent higher priorities
    priority: int
    payload:  str



class NamedEvent(Event, metaclass=abc.ABCMeta):
    """
    The qualified name of any given subclass is now used as its type.
    """

    def __init__(self, id: int, payload: str, *, priority: int = 0):
        super().__init__(id, type(self).__qualname__, priority, payload)



class EventDispatcher:
    """Dispatches events to registered handlers."""

    @abc.abstractmethod
    async def dispatch(self, event: Event) -> None:
        pass



class EventConsumer(metaclass=abc.ABCMeta):
    """
    Optional parent class for classes that are registered as handlers with
    :class:`AsyncEventNexus`.  Given that any coroutine function/method with
    the :meth:`handle` signature can also be a handler, this class has a
    different name in order to avoid confusion.

    Handlers must add secondary events (arising from the processing of events
    the receive) to the queue, so the nexus can dispatch them.
    """

    @abc.abstractmethod
    async def handle(self, event: Event, queue: asyncio.Queue) -> None:
        """
        Handle an event.

        :param queue: The caller's queue to which any secondary events should be sent.
        """
        pass



# If a Callable it should actually be a coroutine function, or if a
# :class:`EventConsumer` is used its ``handle`` method be a coroutine function
HandlerType = Union[Callable[[Event, asyncio.Queue], None], EventConsumer]
FilterType = Callable[[Event, asyncio.Queue], bool]


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


    def create_event(self, payload, *, type: Union[int, str], id: int = AUTO, priority: int = 0) -> Event:
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



class EventSource(metaclass=abc.ABCMeta):
    async def start(self) -> None:
        """
        Any subclass's :meth:`start` coroutine (if any) must call
        ``await super().start()``.
        """
        pass


    def close(self):
        pass



class SimpleEventConverter(EventSource):
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


    def close(self):
        super().close()
        return aclose(self.gen)


    async def obtain_event(self) -> Event:
        """
        Gets one event.

        :raises errors.NoMoreEvents: If it is not possible to get an event
        """

        try:
            return await anext(self.gen)
        except StopAsyncIteration:
            raise errors.NoMoreEvents



class EventProducer(EventSource, metaclass=abc.ABCMeta):
    """
    Event source used in push mode.  Can send each event to one or more nexus
    objects.  Unlike :class:`SimpleEventConverter`, :class:`EventProducer`
    emits events whenever they are ready, without being asked.  Each nexus will
    await :meth:`start` and call :meth:`close`.

    It's up to an object of each subclass to manage its own flow of control.
    They shouldn't do anything other than allocate resources until
    :meth:`start` is awaited.

    Uses weak references to stop circular references from preventing garbage collection.

    :ivar nexus_list: Maintains the list of AsyncEventNexus objects to send to
        :type nexus_list: List[AsyncEventNexus]
    :ivar event_factory:   Optional object that subclasses may use to create :class:`Event` objects
        :type event_factory: Optional[EventFactory]
    """

    def __init__(self, event_factory: Optional[EventFactory] = None):
        """
        :param event_factory:   Optional object that subclasses may use to create :class:`Event` objects
        """

        self.nexus_set: Set[AbstractNexus] = weakref.WeakSet()
        if event_factory:
            self.event_factory = weakref.proxy(event_factory)
        else:
            self.event_factory = None


    def register_nexus(self, nexus: AbstractNexus) -> None:
        """
        Mandatory method that must be called for each nexus that this producer
        is to be associated with.
        """

        self.nexus_set.add(nexus)


    async def start(self) -> None:
        """
        Optionally, kicks off any actions the producer needs to do in order to
        start producing events.  Subclasses must call ``await super().start()``.
        """

        if not self.nexus_set:
            raise errors.MisconfiguredEventProducer("No nexus objects registered")


    async def distribute_event(self, event: Event) -> None:
        for nexus in self.nexus_set:
            await nexus.ingest(event)



class Timer(EventProducer):
    """
    Represents one of several types of integer ticker, or a one-shot, timer
    that can be started/stopped and emits an event each time it fires.

    Timer intervals might be longer than specified if other tasks block.

    Don't use this class for anything other than creating events.

    :ivar interval:         How long (in seconds) the timer should run before emitting an event
    :ivar type:             What type of timer is being created (one of the below values)
    :ivar starting_value:   The value to start with
    :ivar ending_value:     The value to count up to or down from
    :ivar direction_value:  The value added each iteration
    :ivar task:             asyncio.Task
    :ivar event_type:       The numeric type to be used when an event it created
    :ivar event_factory:    Optional object used to create :class:`Event` objects
    """

    # Timeer type values
    COUNT_UP   = 1
    COUNT_DOWN = 2
    ONGOING    = 3  # Like COUNT_UP but repeats forever
    ONE_SHOT   = 4  # Equivalent to COUNT_UP with count=1


    def __init__(self, interval: float, *, event_type: Union[int, str], type: int = ONE_SHOT, count: int = 0, event_factory: Optional[EventFactory] = None):
        """
        :param event_factory:  Required unless a subclass overrides :method:`timer_fired` to create events
        """

        super().__init__(event_factory)

        if type == self.COUNT_DOWN:
            if count <= 0:
                raise ValueError("Countdown value invalid")
            self.starting_value = count
            self.ending_value = 0
            self.direction_value = -1
        elif type == self.COUNT_UP:
            if count <= 0:
                raise ValueError("Countup value invalid")
            self.starting_value = 0
            self.ending_value = count
            self.direction_value = 1
        elif type == self.ONGOING:
            if count != 0:
                raise ValueError("Counter value supplied when irrelevant")
            self.starting_value = 0
            self.ending_value = -1
            self.direction_value = 1
        elif type == self.ONE_SHOT:
            if not 0 <= count <= 1:
                raise ValueError("Oneshot value invalid")
            self.starting_value = 0
            self.ending_value = 1
            self.direction_value = 1
        else:
            raise ValueError("Invalid timer type " + str(type))
        self.task = None
        self.type = type
        self.event_type = event_type
        self.interval = interval


    async def start(self) -> asyncio.Task:
        """
        Kicks off actions the producer needs to do in order to
        start producing events.  Subclasses must call ``await super().start()``.
        """

        await super().start()
        if self.task:
            raise errors.MultipleStart("Timer already started")
        self.task = asyncio.create_task(self._loop())
        await asyncio.sleep(0)   # Give the task a chance to start
        return self.task


    def stop(self) -> bool:
        """
        Cancel the timer's task.

        :returns: True if the timer task was cancelled (or never run) or False if it had already run
        """

        if not self.task:
            return True
        else:
            return_value: bool = not (self.task.done() and not self.task.cancelled())
            self.task.cancel()
            self.task = None
            return return_value


    async def _loop(self):
        """Emit an event after each timed interval."""

        value = self.starting_value
        while value != self.ending_value:
            await asyncio.sleep(self.interval)
            value += self.direction_value
            # Timer has fired
            event = self.create_event(value)
            await self.distribute_event(event)
        # Won't return if self.type == ONGOING
        ## print(str(self.task) + " done.")
        self.task = None


    def create_event(self, value: int):
        """
        Called each time the timer fires.

        Don't call ``super().create_event()`` if overriding.

        :param value: The current count down or count up value
        """

        return self.event_factory.create_event(value, type=self.event_type)



class AsyncEventNexus(EventDispatcher, AbstractNexus, EventFactory):
    """
    Distributes events to filters (see alias :class:`FilterType`) and/or
    handlers (see alias :class:`HandlerType`) which must also accept a second
    argument, being the queue into which any secondary events are added.

    Can act as a context manager (non-async), which calls :meth:`cleanup`.

    Either :meth:`loop_forever` must be awaited or :meth:`start` called (in
    which case it runs the event loop in a separate task).

    If :meth:`stop` is called or a task (external or internal) running
    :meth:`loop_forever` is cancelled, or an error occurs, :meth:`cleanup` must
    then be run unless in a ``with`` block.

    AsyncEventNexus objects cannot be currently be chained, i.e. one nexus
    can't be registered as a handler with another.

    :ivar converters: Objects with async obtain_event() methods
        :type converters: List[SimpleEventConverter]
    :ivar producers: Objects with register_nexus() methods
        :type producers: List[EventProducer]
    """

    QUEUE_MAXLEN = 50
    States = Enum('States', "READY STARTING LOOPING STOPPED")


    def __init__(self, multiple: bool = False, bitmode: bool = False):
        """
        :param multiple: Allow multiple handlers per event type
        :param bitmode:  if True, means that event types can only be powers of 2 and handlers can be associated with a bitmask
        """

        super().__init__()
        if bitmode:
            raise NotImplementedError
        # A map of predicates that can choose to accept an event or pass it on
        # (and if none accept it it will be given to the handler(s))
        self.filters: Set[FilterType] = set()
        # Either a mapping of each event type (or -1 for any) to a handler, OR
        # if self.multiple is True, a mapping of event type / -1 to a list of handlers.
        self.handlers: Union[Dict[Union[int, str], HandlerType], Dict[Union[int, str], List[HandlerType]]] = {}
        self.queue = asyncio.Queue(maxsize=self.QUEUE_MAXLEN)
        self.multiple = multiple
        self.converters = []
        self.producers = []
        self.state = self.States.READY
        self.loop_task: Optional[asyncio.Task] = None


    def add_handler(self, type: Union[int, str], handler: HandlerType):
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
                raise LookupError("Handler for type %s already present" % type)


    def add_filter(self, handler: FilterType):
        """
        :param handler: A Callable to be awaited when an event is received
        """

        self.filters.add(handler)


    def add_converter(self, converter: SimpleEventConverter) -> None:
        self.converters.append(converter)


    def add_producer(self, producer: EventProducer) -> None:
        self.producers.append(producer)
        producer.register_nexus(self)


    def register(self, item: EventSource):
        if issubclass(type(item), SimpleEventConverter):
            self.add_converter(item)
        else:
            # Assume it has a start() method, which is the only requirement
            self.add_producer(item)


    async def ingest(self, event: Event) -> None:
        """
        Handle an event, with queueing.

        All events (including secondary) are sequentially handled, i.e. not as
        tasks.  Any background tasks should be created as such by handlers.
        """

        if self.state not in (self.States.STARTING, self.States.LOOPING):
            raise errors.BadCall("AsyncEventNexus event loop not running")

        await self.queue.put(event)

        # TODO: Wrap the dispatch loop in a critical section and skip it if
        # another :meth:`ingest` invocation is in progress on this object.
        # This preserves sequential queue processing.

        # Process all events, including those generated by handlers
        while True:
            # Deal with race condition where another coroutine removed the last
            # item after the loop condition check by ignoring the exception
            try:
                event = self.queue.get_nowait()
                await self.dispatch(event)
            except asyncio.QueueEmpty:
                # TODO: release critical section here
                break


    # This has to be async so handler coroutines can add secondary events to the queue
    async def dispatch(self, event: Event) -> None:
        try:
            if self.multiple:
                # This would need handlers to be of type FilterType
                ## for handler in self.handlers[event.type]:
                ##     handled = await handler(event, self.queue)
                ##     if handled:
                ##         break
                ## else:
                ##     # It might not be a good idea to fall through to the generic handler list
                ##     for handler in self.handlers[-1]:
                ##         handled: bool = await handler(event, self.queue)
                ##         if handled:
                ##             break
                ##     else:
                ##         raise errors.UnhandledEvent("Generic handlers all refused event")
                raise NotImplementedError
            else:
                # Try filters until one accepts the event and if so, stop processing
                for handler in self.filters:
                    handled: bool = await create_handler_coro(handler, event, self.queue)
                    if handled:
                        break
                else:
                    try:
                        # Otherwise, check for a type-specific handler
                        handler = self.handlers[event.type]
                    except KeyError:
                        # Failing that, check for a generic handler
                        handler = self.handlers[-1]
                    await create_handler_coro(handler, event, self.queue)
        except KeyError:
            raise errors.UnhandledEvent("No available event handler for event with ID=%d and type=%s" % (event.id, event.type), event)


    async def loop_forever(self) -> None:
        """
        The main Async Nexus loop.  Starts producers, then loops forever
        consuming and distributing events from converters.  In parallel to
        this, any registered producers will feed events into the queue
        unprompted.
        """

        if self.state in (self.States.STARTING, self.States.LOOPING):
            raise errors.LoopAlreadyStarted("Spurious call to loop_forever()")
        elif self.state is self.States.STOPPED:
            raise errors.LoopStopped("No longer looping (spurious call to loop_forever())")
        elif self.state is self.States.READY:
            self.state = self.States.STARTING
            # Start all event source objects
            await asyncio.gather(*(source.start() for source in itertools.chain(self.producers, self.converters)))
        # No need for self.States.STARTED because it transitions to
        # self.States.LOOPING immediately

        # TO-DO: task cancellation with event arising

        self.state = self.States.LOOPING

        async def replace_future(task_to_converter_mapping: Dict[asyncio.Task, SimpleEventConverter],
                                 done_future: asyncio.Task) -> None:
            """Replace a task/future that's ready and reuse the rest."""
            converter = task_to_converter_mapping[done_future]
            del task_to_converter_mapping[done_future]
            new_future = asyncio.create_task(converter.obtain_event())
            task_to_converter_mapping[new_future] = converter

        # This is not really an event loop, because events can be ingested
        # and dispatched before this.  Converters won't be queried without it
        # though.
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

        except (KeyboardInterrupt, asyncio.CancelledError):
            pass

        self.state = self.States.STOPPED


    def start(self) -> asyncio.Task:
        """
        Start the event loop in the background, and return the task to be
        optionally awaited (if it returns due to error or cancellation).
        """

        if self.state is not self.States.READY:
            raise errors.InvalidLoopState("start() called when state is " + self.state.name)
        if not self.loop_task:
            self.loop_task = asyncio.create_task(self.loop_forever())
            return self.loop_task
        else:
            raise errors.BadCall("AsyncEventNexus loop task already running")


    def stop(self):
        self.loop_task.cancel()


    def cleanup(self):
        while self.producers:
            producer = self.producers.pop()
            try:
                producer.close()
            except Exception:
                pass
        while self.converters:
            converter = self.converters.pop()
            try:
                converter.close()
            except Exception:
                pass
        self.handlers.clear()
        self.filters.clear()


    def __enter__(self):
        if self.state is not self.States.READY or any((self.producers, self.converters)):
            raise errors.BadCall("ContextManager entered for non-pristine nexus")
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        self.cleanup()
        return False  # ensure the exception, if any, is re-raised



class EventFanout(EventConsumer):
    """
    Event consumer that sends each event to every registered handler.

    A handler is a coroutine function/method with the same signature as
    :meth:`handle` or an object with an equivalent method.
    """

    def __init__(self):
        self.handlers: List[HandlerType] = []


    def register(self, handler: HandlerType):
        self.handlers.append(handler)


    async def handle(self, event: Event, queue: asyncio.Queue) -> None:
        await asyncio.gather(*(create_handler_coro(handler) for handler in self.handlers))



# *** FUNCTIONS ***
def create_handler_coro(handler: Union[HandlerType, FilterType], event: Event, queue: asyncio.Queue) -> Coroutine:
    """
    Supports calling dynamic handlers that are either a coroutine
    function/method, or a :class:`EventConsumer` object.  Note that this
    doesn't actually call the handler.
    """

    if callable(handler):
        return handler(event, queue)
    else:
        return handler.handle(event, queue)
