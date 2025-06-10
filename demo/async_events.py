#! /usr/bin/python3
# vim: set fileencoding=utf-8 tabstop=4 shiftwidth=4 :
# async_events.py (Python script) -- Demonstrate the async_nexus library
#
# Version:   
# Copyright: (c)2025 Alastair Irvine <alastair@plug.org.au>
# Keywords:  
# Notice:    
# Licence:   This file is released under the GNU General Public License
#
'''Description: Demonstrate the async_nexus library
  
Usage: .venv/bin/python demo/async_events.py

If you haven't already, run this command before running this program:
    python3 -m venv .venv
'''
# Licence details:
#     This program is free software; you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation; either version 2 of the License, or (at
#     your option) any later version.
#
#     See http://www.gnu.org/licenses/gpl-2.0.html for more information.
#
#     You can find the complete text of the GPLv2 in the file
#     /usr/share/common-licenses/GPL-2 on Debian systems.
#     Or see the file COPYING in the same directory as this program.
#
#
# TO-DO:

from typing import Callable

import sys
import getopt
import asyncio
import random
from enum import IntEnum

import async_nexus


# *** DEFINITIONS ***
self="async_events.py"
allowed_options='hd'
allowed_long_options=['help']


# *** CLASSES ***
DemoEventType = IntEnum('DemoEventType', "FIRST SECOND THIRD _MAX")



class DemoEventProducer(async_nexus.EventProducer):
    """
    :ivar task: asyncio.Task
        :type task: asyncio.Task
    """

    async def start(self):
        await super().start()
        self.task = asyncio.create_task(self.create_events())


    async def create_events(self):
        while True:
            type = random.randint(0, DemoEventType._MAX)
            event = self.event_factory.create_event("hello", type=type)
            await self.distribute_event(event)
            await asyncio.sleep(0.5)


class DemoBigEventEmitter(async_nexus.EventEmitter):
    """async_nexus.Event source used in pull mode."""


    def __init__(self, id_fn: Callable):
        super().__init__()
        self.id_fn = id_fn


    async def event_generator(self):
        while True:
            yield async_nexus.Event(self.id_fn(), 60, 0, "hi!!!!")
            await asyncio.sleep(0.4)



class DemoEventEmitter(async_nexus.SimpleEventEmitter):
    """async_nexus.Event source used in pull mode."""


    def __init__(self, id_fn: Callable):
        super().__init__()
        self.id_fn = id_fn


    async def emit(self) -> async_nexus.Event:
        await asyncio.sleep(0.2)
        return async_nexus.Event(self.id_fn(), 50, 0, "hi")



# *** FUNCTIONS ***
def show_help(dest=sys.stdout):
    print(__doc__.rstrip(), file=dest)


def report_error(msg):
    print(self + ": Error: " + msg, file=sys.stderr)


def report_warning(msg):
    print(self + ": Warning: " + msg, file=sys.stderr)


def report_notice(msg):
    print(self + ": Notice: " + msg, file=sys.stderr)


async def teapot(nexus: async_nexus.AsyncEventNexus) -> None:
    await asyncio.sleep(3)
    event = async_nexus.Event(1001, 99, 0, "TEAPOT!")
    await nexus.ingest(event)


async def handler_for_10(event: async_nexus.Event, queue: asyncio.Queue):
    print("[%d] %s" % (event.id, event.payload))


async def special_handler(event: async_nexus.Event, queue: asyncio.Queue):
    print("type=%s [%d] %s" % (DemoEventType(event.type).name, event.id, event.payload))


async def default_handler(event: async_nexus.Event, queue: asyncio.Queue):
    print("type=%d [%d] %s" % (event.type, event.id, event.payload))


async def go():
    nexus = async_nexus.AsyncEventNexus()
    nexus.add_handler(10, handler_for_10)
    nexus.add_handler(DemoEventType.FIRST, special_handler)
    nexus.add_handler(DemoEventType.SECOND, special_handler)
    nexus.add_handler(DemoEventType.THIRD, special_handler)
    nexus.add_handler(-1, default_handler)

    nexus.add_emitter(DemoEventEmitter(nexus.next_id))
    nexus.add_emitter(DemoBigEventEmitter(nexus.next_id))

    # Produces events with random IDs from DemoEventType (not including _MAX)
    nexus.add_producer(DemoEventProducer(event_factory=nexus))

    teapot_task = asyncio.create_task(teapot(nexus))

    await nexus.loop_forever()



# *** MAINLINE ***
if __name__ == '__main__':
    # == Command-line parsing ==
    # -- defaults --
    debug = 0

    # -- option handling --
    try:
        optlist, args = getopt.getopt(sys.argv[1:], allowed_options, allowed_long_options)
    except getopt.GetoptError as e:
        report_error(e)
        sys.exit(1)

    # Create a special dict object that defaults to False for unspecified options
    from collections import defaultdict
    params = defaultdict(bool)

    for option, opt_arg in optlist:
        if option == "-n":
            params["no_fetch"] = True
        elif option == "-d":
            debug += 1
        elif option == "-h" or option == "--help":
            show_help()
            sys.exit(0)

    # -- argument checking --
    ## if len(args) not in (2, 3):
    ##     report_error("Invalid command-line parameters.")
    ##     print("", file=sys.stderr)
    ##     show_help(sys.stderr)
    ##     sys.exit(1)

    # -- argument handling --
    ## if len(args) == 0:


    # == sanity checking ==


    # == preparation ==


    # == processing ==
    asyncio.run(go())
