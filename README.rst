===========
Async Nexus
===========


.. image:: https://img.shields.io/pypi/v/async_nexus.svg
        :target: https://pypi.python.org/pypi/async-nexus

.. image:: https://readthedocs.org/projects/async-nexus/badge/?version=latest
        :target: https://async-nexus.readthedocs.io/en/latest/?version=latest
        :alt: Documentation Status


This is a library to manage the transfer of data using lightweight Event
objects in asynchronous Python programs.  It allows the creation of
loosely-coupled programs using async coroutines and generators to
create/handle events.  This replaces the need for traditional callbacks
and code that blocks waiting for something to happen, both of which
increase coupling between modules (which is bad in medium and large
programs).

The Async Nexus library (henceforth referred to by its package name)
provides convenience classes for common event-related activities such as
:class:`async_nexus.Timer`.  It also provides various abstract
:class:`async_nexus.EventSource` subclasses to allow the creation of
application-specific classes that translate problem-domain events into
:class:`async_nexus.Event` objects, as well as fully usable classes for
interacting with libraries like 0mq (ZeroMQ) and other message brokers.

``async_nexus`` is designed to let you structure your programs and their
interactions in the way that you want.  It uses a pluggable event
architecture with which you can change the way that events are created
and consumed, and add a variety of ultimate sources, without having to
redesign your program as it grows.


* Free software: MIT license
* Documentation: https://async-nexus.readthedocs.io
* Git repository: https://github.com/unixnut/async-nexus


Features
--------

* TODO

Credits
-------

(C)2025 Alastair Irvine <alastair@plug.org.au>

This package was created with Cookiecutter_ and the `unixnut/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`unixnut/cookiecutter-pypackage`: https://github.com/unixnut/cookiecutter-pypackage
