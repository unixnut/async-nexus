===========
Async Nexus
===========


.. image:: https://img.shields.io/pypi/v/async_nexus.svg
        :target: https://pypi.python.org/pypi/async_nexus

.. image:: https://img.shields.io/travis/unixnut/async-nexus.svg
        :target: https://travis-ci.com/unixnut/async-nexus

.. image:: https://readthedocs.org/projects/async-nexus/badge/?version=latest
        :target: https://async-nexus.readthedocs.io/en/latest/?version=latest
        :alt: Documentation Status


Library to manage the transfer of data using lightweight Event objects
in asynchronous Python programs.  Allows the creation of loosely-coupled
programs using async coroutines and generators to create/handle events.
Provides convenience classes for common event-related activities such as
Timer.

It provides various :class:`async_nexus.EventSource` subclasses for
interacting with libraries like 0mq (ZeroMQ) and other message brokers.

``async_nexus`` is designed to let you structure your programs and their
interactions in the way that you want.  It uses a pluggable event
architecture with which you can change the way that events are created
and consumed, and add a variety of ultimate sources, without having to
redesign your program as it grows.


* Free software: MIT license
* Documentation: https://async-nexus.readthedocs.io (pending)
* Git repository: https://github.com/unixnut/async-nexus


Features
--------

* TODO

Credits
-------

This package was created with Cookiecutter_ and the `unixnut/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`unixnut/cookiecutter-pypackage`: https://github.com/unixnut/cookiecutter-pypackage
