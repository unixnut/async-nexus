=====
Usage
=====

To use Async Nexus in a project::

    import async_nexus

The first thing you'll need to do in your code is create a
:class:`async_nexus.AsyncEventNexus` object::

    nexus = async_nexus.AsyncEventNexus()

The purpose of this object is direct events to where they need to go.
However, it does nothing without sources of events that it will ingest
and distribute.  These sources are written independently of the handlers
of the events, so they can all be developed in a decoupled manner.

Events are typically obtained from objects created from subclasses of
:class:`async_nexus.EventSource`.  Most of these subclasses in
``async_nexus`` are abstract, because they exist for you to subclass.
That is how you implement the logic that creates
:class:`async_nexus.Event` objects in the way that suits your
application architecture.

(Note that Async Nexus currently does not make use of an event object's
``priority`` field.)

The next step is to create one or more event sources, e.g.::

    timer = async_nexus.Timer(interval=1.5, type=async_nexus.Timer.COUNT_DOWN, count=5, event_type=98, event_factory=nexus)
    nexus.add_producer(timer)

This uses :class:`async_nexus.Timer`, the only event source that is
usable as-is, thanks to its constructor's ``event_factory`` parameter:
:class:`async_nexus.AsyncEventNexus` is able to create events with the
``event_type`` given.  Each event's ``payload`` will be the current
countdown value and the ``id`` will be auto-generated.

A more general example::

    async def teapot(nexus: async_nexus.AsyncEventNexus) -> None:
        await asyncio.sleep(3)
        event = async_nexus.Event(1001, 99, 0, "TEAPOT!")
        await nexus.ingest(event)
    
    teapot_task = asyncio.create_task(teapot(nexus))

This is the simplest kind of event source, one that doesn't use
:class:`async_nexus.EventSource` at all.  It just creates a task that
will send events to the nexus, e.g. by using a loop.  However, it is not
the most convenient, as we will see.
(:class:`async_nexus.EventSource` subclasses are detailed in "Event
Sources" below.)

Then, a way to consume the events must be written, for example::

    async def teapot_handler(event: async_nexus.Event, queue: asyncio.Queue):
        print("teapot ID: ", event.id)
    
    nexus.add_handler(99, teapot_handler)
    nexus.add_handler(-1, lambda e, q: print(e))

See "Event Handlers" below for more information on how events are
handled by :class:`async_nexus.AsyncEventNexus`.

Lastly, either start the nexus in blocking mode::

    nexus.loop_forever()

Or, create a task for it to run in the background::

    nexus_task = nexus.start()
    ...

Event Sources
-------------
To create a simple event source, subclass
:class:`async_nexus.SimpleEventConverter` and override its obtain_event()
method, e.g.::

    class MyEventConverter(async_nexus.SimpleEventConverter):
        """async_nexus.Event source used in pull mode."""

        id = 1000
        
        async def obtain_event(self) -> async_nexus.Event:
            await asyncio.sleep(0.2)
            self.id += 1
            return async_nexus.Event(self.id, 50, 0, "hi")

    nexus.register(MyEventConverter())

Note that a sleep mimics some amount of processing rather than creating
wall-to-wall events as fast as possible.

For a way to use a generator (and thus not have to use object properties
to track state), subclass :class:`async_nexus.EventConverter` and
just override its event_generator() method.

See :class:`DemoEventConverter` in ``demo/async_events.py`` for an
example of how to use :meth:`async_nexus.AsyncEventNexus.next_id`.

Another kind of event source is an :class:`async_nexus.EventProducer`
subclass.  These must have their own "push mode" interface or some kind
of queue logic, which calls the supplied
:meth:`async_nexus.EventProducer.distribute_event` method.  Subclasses should
override the :meth:`async_nexus.EventProducer.start` coroutine and
:meth:`async_nexus.EventSource.close` method.

To register a producer::

    nexus.add_producer(MyEventProducer(event_factory=nexus))

Because it uses the parent constructor's optional ``event_factory``
parameter, it can call ``self.event_factory.create_event(..., event_type=...)``
to create events.

The constructor can allocate resources, but the object shouldn't begin
creating events until :meth:`async_nexus.EventProducer.start` has been
awaited.

Event Handlers
--------------
If any event is ingested by a nexus and not consumed, this is a logic
error and a :class:`async_nexus.errors.UnhandledEvent` exception will be
raised.  To consume events, register filters (callables that take a
:class:`async_nexus.Event` and a :class:`asyncio.Queue` parameter and
return a :class:`bool`) and/or handlers (either callables that take a
:class:`async_nexus.Event` and a :class:`asyncio.Queue` parameter, or
:class:`async_nexus.EventConsumer` subclasses) with a nexus.  These
operate as follows, in this order:

1. A filter function indicates that an event has been consumed,
   i.e. processing should stop, by returning ``True``.  Otherwise
   processing continues.  Use
   :meth:`async_nexus.AsyncEventNexus.add_filter` to register these.
   Filter functions are run in the order they were registered.
2. A regular handler object (of a :class:`async_nexus.EventConsumer`
   subclass) or function will only handle events of a given type.  Use
   :meth:`async_nexus.AsyncEventNexus.add_handler` to register these.
3. A default handler object or function will handle all events not
   already consumed.  Use
   :meth:`async_nexus.AsyncEventNexus.add_handler` with event type
   ``-1`` to register these.

:class:`async_nexus.EventDiscarder` is provided for use as a handler for
useless events.

Ideally, use of filter functions should be kept to a minimum, because
they decide which events to consume based on code rather than letting
:class:`async_nexus.AsyncEventNexus` check the event type as is the case
for handlers.  A bad use case for a filter would be checking if the
event type is in a list; instead, this could be done by registering the
same handler for each event type.  A good use case would be checking if
an event type is in a range*.  Another good use case would be to check
if the event's payload is invalid and discarding it by returning
``True``; valid events will then be consumed by subsequent handlers.

\* Although an event type range should be handled by modifying
:meth:`async_nexus.AsyncEventNexus.add_handler` to allow a ``(start,
end)`` tuple specifying a range

Context Managers
----------------

E.g.::

    with async_nexus.AsyncEventNexus() as nexus

Event buses
-----------
There are several ways to use "publish-subscribe" architecture within an
``async_nexus``-based program.  (Of course, message brokers can be used
outside of it or even within, alongside ``async_nexus``.)  One is to
use an :class:`EventProducer` subclass that is registered with multiple
:class:`async_nexus.AsyncEventNexus` objects.  This approach is probably
only useful when writing plugins, however, because usually a single
nexus is sufficient for a given program.

Another way is to use a special handler called
:class:`async_nexus.EventFanout`, which sequentially sends copies of all
received events to multiple handlers.  This is more simple than creating
a new :class:`async_nexus.AsyncEventNexus`, because it doesn't use
queuing or :class:`asyncio.Task`, for example.

The most complex approach is to use :class:`async_nexus.AsyncEventBoundary`,
which introduces the topic of *event domains*.  This class is ready to
use and acts as both a handler (registered with a nexus in one event domain)
and a producer (for a nexus in another event domain).  This allows only
some events to be distributed from one program component to another.
This approach would probably be used when doing something like creating
an interchangeable logging (or alerting) backend, which has its own
nexus that can receive log events from multiple sources.  This component
would expose an :class:`async_nexus.AsyncEventBoundary` object, which
other components could use as a handler.  That way the component's nexus
would be kept internal.
