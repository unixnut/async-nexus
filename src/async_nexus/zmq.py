"""Wrapper/helper classes and functions for interfacing with 0mq (ZeroMQ)."""

from typing import Set, Dict, Sequence, Tuple, List, Union, AnyStr, Iterable, Callable, Generator, Type, Optional, TextIO, IO

import abc
import weakref
import dataclasses
import asyncio

import zmq
import zmq.asyncio

from . import EventFactory
from . import SimpleEventConverter
from . import EventTypeID, Event
from . import EventConsumer



# *** CLASSES ***
class ZmqAbstractConverter(SimpleEventConverter, metaclass=abc.ABCMeta):

    def __init__(self, socket: zmq.Socket):
        ## self.socket = weakref.proxy(socket)
        self.socket = socket


    def __enter__(self):
        pass


    def __exit__(self, exc_type, exc_value, traceback):
        self.socket.close(linger=0)



class ZmqEventConverter(ZmqAbstractConverter):
    """
    Event source used in pull mode.  Blocks until a string has been received,
    then converts it to a :class:`async_nexus.Event` of a specified type.

    Can be used as a context manager (non-async), which closes the socket on exit.

    :ivar event_type:       Event type or class (subclass of :class:`async_nexus.NamedEvent`) to be used when an event is created
    :ivar event_factory:    Object used to create :class:`async_nexus.Event` objects
    """

    def __init__(self, socket: zmq.Socket, *, event_type: EventTypeID, event_factory: Optional[EventFactory]):
        """
        :param event_type:      A numeric or string type ID or a subclass of :class:`async_nexus.NamedEvent` (note: a class not an object), to be used when an event is created
        :param event_factory:   Optional object that subclasses may use to create :class:`async_nexus.Event` objects
        """

        super().__init__(socket)
        self.event_type = event_type
        if event_factory:
            self.event_factory = weakref.proxy(event_factory)
        else:
            self.event_factory = None


    def convert_to_event(self, s: str):
        """
        Make an event with the supplied string as its payload.

        Override if not using ``self.event_factory``
        """

        return self.event_factory.create_event(s, event_type=self.event_type)


    async def obtain_event(self) -> Event:
        """
        Get a string from the socket then convert it to an event.

        Override if needing to use multipart events (for example) or modify the
        string before conversion.
        """

        s = await self.socket.recv_string()
        ## data = await self.socket.recv_multipart()
        return self.convert_to_event(s)



class ZmqEventReceiver(ZmqAbstractConverter):
    """
    Event source used in pull mode.  Blocks until a JSON string representing a
    full :class:`async_nexus.Event` has been received, including ID, then
    converts it.

    Can be used as a context manager (non-async), which closes the socket on exit.
    """

    def __init__(self, socket: zmq.Socket):
        super().__init__(socket)


    async def obtain_event(self) -> Event:
        """
        Get a JSON string from the socket then convert it to an event.
        """

        data: Dict = await self.socket.recv_json()
        return Event(**data)



class ZmqEventSender(EventConsumer):
    """
    Send events over a ZMQ socket as JSON.

    Registered as a handler with :class:`AsyncEventNexus`.
    """

    def __init__(self, socket: zmq.Socket):
        self.socket = socket


    async def handle(self, event: Event, queue: asyncio.Queue) -> None:
        """
        Handle an :class:`async_nexus.Event`.

        :param queue: The caller's queue to which any secondary events should be sent.
        """

        send_event(event, self.socket)



# *** FUNCTIONS ***
def send_event(event: Event, socket: zmq.Socket):
    """Send an event over a ZMQ socket as JSON."""

    socket.send_json(event, default=dataclasses.asdict)
